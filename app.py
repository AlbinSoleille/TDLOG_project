import os
import csv
import random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader

# Importer la configuration
from config import API_PROVIDER, ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, MODELS

# Importer les fonctions de la base de données
from database import (
    init_database, get_user_by_username, create_user,
    get_all_decks, get_user_decks, get_deck_by_name, create_deck,
    get_flashcards_by_deck, create_flashcard,
    get_all_user_progress, update_progress, get_user_progress,
    get_user_prompt, save_user_prompt, get_user_statistics
)

# Importer l'algorithme Anki
from anki_algorithm import AnkiCard, calculate_next_review
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'CLE_SECRETE_A_CHANGER'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dossier pour les flashcards CSV (pour la génération depuis PDF)
FLASHCARDS_DIR = os.path.join(BASE_DIR, 'flashcards_data')
os.makedirs(FLASHCARDS_DIR, exist_ok=True)

# Initialiser la base de données au démarrage
init_database()

# --- PROMPT PAR DÉFAUT POUR LA GÉNÉRATION DE FLASHCARDS ---
DEFAULT_PROMPT_TEMPLATE = """Tu es un assistant pédagogique. À partir du texte suivant, génère exactement {nb_flashcards} flashcards de qualité pour aider l'étudiant à mémoriser les concepts clés.

Texte du cours:
{texte}

Règles:
- Génère exactement {nb_flashcards} paires question/réponse
- Les questions doivent être claires et précises
- Les réponses doivent être concises mais complètes
- Utilise la notation LaTeX entre $ pour les formules mathématiques (ex: $x^2$)
- Format de réponse: une ligne par flashcard au format: QUESTION;;;REPONSE
- Utilise EXACTEMENT trois points-virgules (;;;) comme séparateur

Exemple de format attendu:
Qu'est-ce qu'une variable aléatoire ?;;;Une fonction qui associe à chaque issue d'une expérience aléatoire un nombre réel
Quelle est la formule de la variance ?;;;$Var(X) = E[(X - E[H])^2] = E[X^2] - (E[X])^2$"""

# --- SECURITE ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- GENERATION FLASHCARDS DEPUIS PDF ---

def extraire_texte_pdf(pdf_path):
    """Extrait le texte d'un fichier PDF"""
    try:
        reader = PdfReader(pdf_path)
        texte_complet = ""
        for page in reader.pages:
            texte_complet += page.extract_text() + "\n"
        return texte_complet
    except Exception as e:
        print(f"Erreur lors de l'extraction du PDF: {e}")
        return None

def generer_flashcards_via_api(texte, nb_flashcards=10, prompt_template=None):
    """Génère des flashcards à partir du texte extrait en utilisant l'API configurée

    Args:
        texte: Le texte extrait du PDF
        nb_flashcards: Nombre de flashcards à générer
        prompt_template: Template de prompt personnalisé (optionnel)
    """

    print(f"🔍 Début génération de {nb_flashcards} flashcards avec {API_PROVIDER}")

    # Utiliser le prompt template fourni ou le prompt par défaut
    if not prompt_template:
        prompt_template = DEFAULT_PROMPT_TEMPLATE

    # Formatter le prompt avec les variables
    prompt = prompt_template.format(
        nb_flashcards=nb_flashcards,
        texte=texte[:8000]  # Limiter à 8000 caractères pour ne pas dépasser les limites API
    )

    print(f"📝 Utilisation du prompt {'personnalisé' if prompt_template != DEFAULT_PROMPT_TEMPLATE else 'par défaut'}")

    try:
        if API_PROVIDER == 'claude':
            # Utiliser l'API Claude (Anthropic)
            from anthropic import Anthropic

            if ANTHROPIC_API_KEY == 'votre-cle-api-claude-ici':
                print("⚠️  Clé API Claude non configurée - Génération de flashcards d'exemple")
                return generer_flashcards_exemple(nb_flashcards), None

            print(f"📡 Appel API Claude ({MODELS['claude']})")
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=MODELS['claude'],
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            contenu = response.content[0].text

        elif API_PROVIDER == 'gemini':
            # Utiliser l'API Gemini (Google)
            import google.generativeai as genai

            if GOOGLE_API_KEY == 'votre-cle-api-gemini-ici':
                print("⚠️  Clé API Gemini non configurée - Génération de flashcards d'exemple")
                return generer_flashcards_exemple(nb_flashcards), None

            print(f"📡 Appel API Gemini ({MODELS['gemini']})")
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(MODELS['gemini'])
            response = model.generate_content(prompt)
            contenu = response.text

        elif API_PROVIDER == 'openai':
            # Utiliser l'API OpenAI
            from openai import OpenAI

            if OPENAI_API_KEY == 'votre-cle-api-openai-ici':
                print("⚠️  Clé API OpenAI non configurée - Génération de flashcards d'exemple")
                return generer_flashcards_exemple(nb_flashcards), None

            print(f"📡 Appel API OpenAI ({MODELS['openai']})")
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=MODELS['openai'],
                messages=[
                    {"role": "system", "content": "Tu es un assistant pédagogique expert en création de flashcards."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            contenu = response.choices[0].message.content
        else:
            return None, f"Provider API non reconnu: {API_PROVIDER}"

        print(f"✅ Réponse reçue de l'API, parsing des flashcards...")

        # Parser les flashcards
        flashcards = []
        lignes = contenu.strip().split('\n')
        for ligne in lignes:
            if ';;;' in ligne:
                parties = ligne.split(';;;')
                if len(parties) >= 2:
                    question = parties[0].strip()
                    reponse = parties[1].strip()
                    if question and reponse:
                        flashcards.append({'question': question, 'reponse': reponse})

        if not flashcards:
            print(f"❌ Aucune flashcard extraite. Contenu reçu:\n{contenu[:500]}")
            return None, "Aucune flashcard n'a pu être extraite. Format de réponse incorrect."

        print(f"✅ {len(flashcards)} flashcards générées avec succès")
        return flashcards, None

    except Exception as e:
        print(f"❌ Erreur lors de la génération: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Erreur lors de la génération ({API_PROVIDER}): {str(e)}"


def generer_flashcards_exemple(nb_flashcards=10):
    """Génère des flashcards d'exemple pour tester le système (sans API)"""
    exemples = [
        {'question': "Qu'est-ce qu'une variable aléatoire ?",
         'reponse': "Une fonction qui associe à chaque issue d'une expérience aléatoire un nombre réel"},
        {'question': "Quelle est la formule de la variance ?",
         'reponse': "$Var(X) = E[(X - E[X])^2] = E[X^2] - (E[X])^2$"},
        {'question': "Qu'est-ce qu'une loi normale ?",
         'reponse': "Une loi de probabilité continue caractérisée par sa moyenne $\\mu$ et son écart-type $\\sigma$"},
        {'question': "Qu'est-ce que l'espérance mathématique ?",
         'reponse': "La moyenne pondérée des valeurs que peut prendre une variable aléatoire"},
        {'question': "Qu'est-ce qu'un événement ?",
         'reponse': "Un sous-ensemble de l'ensemble des issues possibles d'une expérience aléatoire"},
        {'question': "Qu'est-ce que la probabilité conditionnelle ?",
         'reponse': "La probabilité qu'un événement se produise sachant qu'un autre événement s'est produit"},
        {'question': "Qu'est-ce qu'un échantillon ?",
         'reponse': "Un sous-ensemble d'une population sélectionné pour être étudié"},
        {'question': "Qu'est-ce que l'écart-type ?",
         'reponse': "La racine carrée de la variance, mesure de la dispersion des données"},
        {'question': "Qu'est-ce qu'une loi binomiale ?",
         'reponse': "Loi de probabilité du nombre de succès dans une série d'épreuves indépendantes"},
        {'question': "Qu'est-ce que la médiane ?",
         'reponse': "La valeur qui partage une distribution en deux parties égales"},
    ]

    # Retourner le nombre demandé de flashcards
    return exemples[:min(nb_flashcards, len(exemples))]

def sauvegarder_flashcards_db(flashcards, nom_deck, user_id):
    """Sauvegarde les flashcards générées dans la base de données pour un utilisateur"""
    try:
        # Créer ou récupérer le deck pour cet utilisateur
        deck_id = create_deck(nom_deck, user_id)

        # Ajouter les flashcards
        for card in flashcards:
            create_flashcard(deck_id, card['question'], card['reponse'])

        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde dans la DB: {e}")
        return False

# --- GESTION DES FLASHCARDS ---

def piocher_carte(deck_name, user_id):
    """Pioche une carte selon l'algorithme Anki (cartes dues en priorité)"""
    deck = get_deck_by_name(deck_name)
    if not deck:
        return None

    # Récupérer toutes les flashcards avec leur progression
    cartes_progress = get_all_user_progress(user_id, deck['id'])

    if not cartes_progress:
        return None

    now = datetime.now()

    # Filtrer les cartes à réviser
    cartes_a_reviser = []
    for carte in cartes_progress:
        # Nouvelle carte (pas de progression)
        if carte['due_date'] is None:
            cartes_a_reviser.append((carte, 0))  # Priorité max
        else:
            # Carte existante
            due_date = datetime.fromisoformat(carte['due_date'])
            if due_date <= now:
                # Carte due
                delay = (now - due_date).total_seconds() / 3600  # En heures
                cartes_a_reviser.append((carte, delay))

    # S'il n'y a pas de cartes à réviser, on prend les prochaines cartes
    if not cartes_a_reviser:
        for carte in cartes_progress:
            if carte['due_date'] is not None:
                due_date = datetime.fromisoformat(carte['due_date'])
                delay = -(due_date - now).total_seconds() / 3600  # Négatif = futur
                cartes_a_reviser.append((carte, delay))

    if not cartes_a_reviser:
        return None

    # Trier par priorité (nouvelles cartes d'abord, puis cartes en retard)
    cartes_a_reviser.sort(key=lambda x: x[1], reverse=True)

    # Prendre la carte la plus prioritaire
    carte = cartes_a_reviser[0][0]

    return {
        'id': carte['id'],
        'question': carte['question'],
        'reponse': carte['answer'],
        'ease_factor': carte['ease_factor'],
        'interval': carte['interval'],
        'due_date': carte['due_date'],
        'step': carte['step'],
        'is_learning': carte['is_learning'],
        'repetitions': carte['repetitions']
    }

# --- ROUTES AUTHENTIFICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si déjà connecté, rediriger vers cours
    if 'user' in session:
        return redirect(url_for('cours'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Veuillez remplir tous les champs")
        else:
            user = get_user_by_username(username)

            if user and check_password_hash(user['password_hash'], password):
                session['user'] = username
                session['user_id'] = user['id']
                return redirect(url_for('cours'))
            else:
                flash("Identifiant ou mot de passe incorrect")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Si déjà connecté, rediriger vers cours
    if 'user' in session:
        return redirect(url_for('cours'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validations
        if not username or not password:
            flash("Veuillez remplir tous les champs")
        elif len(username) < 3:
            flash("L'identifiant doit contenir au moins 3 caractères")
        elif len(password) < 4:
            flash("Le mot de passe doit contenir au moins 4 caractères")
        elif password != password_confirm:
            flash("Les mots de passe ne correspondent pas")
        elif get_user_by_username(username):
            flash("Cet identifiant est déjà pris")
        else:
            # Création du compte
            password_hash = generate_password_hash(password)
            user_id = create_user(username, password_hash)
            session['user'] = username
            session['user_id'] = user_id
            return redirect(url_for('cours'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('login' if 'user' not in session else 'cours'))

# --- ROUTES PDFS (COURS / FICHES) ---
def gestion_dossier(categorie):
    # Logique PDF simplifiée pour l'exemple
    dossier_org = os.path.join(BASE_DIR, 'static/pdfs', categorie, 'originaux')
    dossier_upl = os.path.join(BASE_DIR, 'static/pdfs', categorie, 'uploads')
    os.makedirs(dossier_org, exist_ok=True)
    os.makedirs(dossier_upl, exist_ok=True)
    if request.method == 'POST' and 'fichier_pdf' in request.files:
        f = request.files['fichier_pdf']
        if f.filename.endswith('.pdf'): f.save(os.path.join(dossier_upl, f.filename))
        return True
    return [f for f in os.listdir(dossier_org) if f.endswith('.pdf')], [f for f in os.listdir(dossier_upl) if f.endswith('.pdf')]

@app.route('/cours', methods=['GET', 'POST'])
@login_required
def cours():
    res = gestion_dossier('cours')
    if res == True: return redirect(url_for('cours'))
    return render_template('cours.html', originaux=res[0], uploads=res[1], page='cours')

@app.route('/fiches', methods=['GET', 'POST'])
@login_required
def fiches():
    res = gestion_dossier('fiches')
    if res == True: return redirect(url_for('fiches'))
    return render_template('fiches.html', originaux=res[0], uploads=res[1], page='fiches')

# --- ROUTES FLASHCARDS ---

@app.route('/flashcards')
@login_required
def flashcards_menu():
    """Affiche la liste des decks de l'utilisateur"""
    user_id = session.get('user_id')
    decks = get_user_decks(user_id)
    # Convertir les Row en dictionnaires pour le template
    decks_list = [{'id': d['id'], 'name': d['name']} for d in decks]
    return render_template('flashcards_menu.html', decks=decks_list, page='flashcards')

@app.route('/flashcards/play')
@login_required
def flashcards_play():
    """Lance le jeu sur le deck choisi"""
    deck_name = request.args.get('deck')
    # Si aucun deck choisi, retour au menu
    if not deck_name:
        return redirect(url_for('flashcards_menu'))

    user_id = session.get('user_id')
    carte = piocher_carte(deck_name, user_id)
    return render_template('flashcards.html', page='flashcards', carte=carte, current_deck=deck_name)

@app.route('/flashcards/vote')
@login_required
def vote_card():
    """Traite la réponse de l'utilisateur selon l'algorithme Anki"""
    # On récupère les infos
    deck_name = request.args.get('deck')
    flashcard_id = request.args.get('flashcard_id')
    rating = request.args.get('rating')  # 0=Again, 1=Hard, 2=Good, 3=Easy
    user_id = session.get('user_id')

    if flashcard_id and deck_name and rating is not None:
        flashcard_id = int(flashcard_id)
        rating = int(rating)

        # Récupérer la progression actuelle
        progress = get_user_progress(user_id, flashcard_id)

        # Créer l'objet AnkiCard
        if progress:
            card = AnkiCard(
                ease_factor=progress['ease_factor'],
                interval=progress['interval'],
                due_date=datetime.fromisoformat(progress['due_date']) if progress['due_date'] else None,
                step=progress['step'],
                is_learning=bool(progress['is_learning']),
                repetitions=progress['repetitions']
            )
        else:
            # Nouvelle carte
            card = AnkiCard()

        # Calculer le prochain intervalle avec l'algorithme Anki
        new_card = calculate_next_review(card, rating)

        # Sauvegarder la nouvelle progression
        update_progress(
            user_id,
            flashcard_id,
            new_card.ease_factor,
            new_card.interval,
            new_card.due_date.isoformat(),
            new_card.step,
            1 if new_card.is_learning else 0,
            new_card.repetitions
        )

    # Piocher la carte suivante
    nouvelle_carte = piocher_carte(deck_name, user_id)
    return render_template('card_fragment.html', carte=nouvelle_carte, current_deck=deck_name)

# --- ROUTE GENERATION FLASHCARDS DEPUIS PDF ---

@app.route('/api/generer-flashcards', methods=['POST'])
@login_required
def generer_flashcards_from_pdf():
    """Endpoint API pour générer des flashcards à partir d'un PDF"""
    try:
        data = request.get_json()
        print(f"\n{'='*60}")
        print(f"🚀 GÉNÉRATION DE FLASHCARDS - Nouvelle requête")
        print(f"{'='*60}")

        # Récupération de l'utilisateur courant
        user_id = session.get('user_id')
        print(f"👤 User ID: {user_id}")

        # Récupération des paramètres
        pdf_filename = data.get('pdf_filename')
        categorie = data.get('categorie', 'cours')  # 'cours' ou 'fiches'
        source = data.get('source', 'uploads')  # 'uploads' ou 'originaux'
        nb_flashcards = int(data.get('nb_flashcards', 10))
        nom_deck = data.get('nom_deck')
        ephemeral_prompt = data.get('ephemeral_prompt', '').strip()

        print(f"📄 PDF: {pdf_filename}")
        print(f"📁 Catégorie: {categorie}, Source: {source}")
        print(f"🎴 Nombre demandé: {nb_flashcards}")
        print(f"📦 Nom du deck: {nom_deck}")
        if ephemeral_prompt:
            print(f"✨ Prompt éphémère fourni ({len(ephemeral_prompt)} caractères)")

        if not pdf_filename or not nom_deck:
            print("❌ Paramètres manquants")
            return jsonify({
                'success': False,
                'error': 'Paramètres manquants (pdf_filename, nom_deck requis)'
            }), 400

        # Construction du chemin du PDF
        pdf_path = os.path.join(BASE_DIR, 'static/pdfs', categorie, source, pdf_filename)
        print(f"🔍 Chemin PDF: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"❌ Fichier PDF non trouvé: {pdf_path}")
            return jsonify({
                'success': False,
                'error': f'Fichier PDF non trouvé: {pdf_filename}'
            }), 404

        print("✅ PDF trouvé, extraction du texte...")
        # Extraction du texte
        texte = extraire_texte_pdf(pdf_path)
        if not texte:
            print("❌ Impossible d'extraire le texte")
            return jsonify({
                'success': False,
                'error': 'Impossible d\'extraire le texte du PDF'
            }), 500

        print(f"✅ Texte extrait ({len(texte)} caractères)")

        # Déterminer le prompt à utiliser (priorité: éphémère > personnalisé > défaut)
        prompt_template = None
        if ephemeral_prompt:
            prompt_template = ephemeral_prompt
            print("🎨 Utilisation du prompt éphémère")
        else:
            user_custom_prompt = get_user_prompt(user_id)
            if user_custom_prompt:
                prompt_template = user_custom_prompt
                print("👤 Utilisation du prompt personnalisé de l'utilisateur")
            else:
                print("📋 Utilisation du prompt par défaut")

        print(f"🤖 Génération des flashcards avec {API_PROVIDER}...")

        # Génération des flashcards
        flashcards, error = generer_flashcards_via_api(texte, nb_flashcards, prompt_template)
        if error:
            print(f"❌ Erreur de génération: {error}")
            return jsonify({
                'success': False,
                'error': error
            }), 500

        if not flashcards:
            print("❌ Aucune flashcard générée")
            return jsonify({
                'success': False,
                'error': 'Aucune flashcard générée'
            }), 500

        print(f"✅ {len(flashcards)} flashcards générées")
        print(f"💾 Sauvegarde dans la base de données...")

        # Sauvegarde dans la base de données SQLite
        if sauvegarder_flashcards_db(flashcards, nom_deck, user_id):
            print(f"✅ Sauvegarde réussie! Deck: {nom_deck}")
            print(f"{'='*60}\n")

            # Message selon si c'est avec API ou exemples
            if GOOGLE_API_KEY == 'votre-cle-api-gemini-ici' and API_PROVIDER == 'gemini':
                message_prefix = "⚠️ MODE TEST: "
            else:
                message_prefix = ""

            return jsonify({
                'success': True,
                'message': f'{message_prefix}{len(flashcards)} flashcards générées avec succès',
                'deck_name': nom_deck,
                'nb_flashcards': len(flashcards),
                'api_provider': API_PROVIDER
            })
        else:
            print("❌ Erreur lors de la sauvegarde")
            return jsonify({
                'success': False,
                'error': 'Erreur lors de la sauvegarde des flashcards'
            }), 500

    except Exception as e:
        print(f"❌ ERREUR SERVEUR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        }), 500

# --- ROUTES PARAMÈTRES ---

@app.route('/parametres')
@login_required
def parametres():
    """Page de paramètres"""
    return render_template('parametres.html', page='parametres')


@app.route('/parametres/prompt', methods=['GET', 'POST'])
@login_required
def prompt_settings():
    """Page de modification du prompt personnalisé"""
    user_id = session.get('user_id')

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save':
            custom_prompt = request.form.get('custom_prompt', '').strip()
            if custom_prompt:
                save_user_prompt(user_id, custom_prompt)
                flash('Prompt personnalisé sauvegardé avec succès !', 'success')
            else:
                flash('Le prompt ne peut pas être vide.', 'warning')

        elif action == 'reset':
            # Réinitialiser au prompt par défaut
            save_user_prompt(user_id, DEFAULT_PROMPT_TEMPLATE)
            flash('Prompt réinitialisé au prompt par défaut.', 'info')

        return redirect(url_for('prompt_settings'))

    # Récupérer le prompt personnalisé de l'utilisateur ou utiliser le défaut
    custom_prompt = get_user_prompt(user_id)
    if not custom_prompt:
        custom_prompt = DEFAULT_PROMPT_TEMPLATE

    return render_template('prompt.html',
                          custom_prompt=custom_prompt,
                          default_prompt=DEFAULT_PROMPT_TEMPLATE,
                          page='parametres')


@app.route('/parametres/statistiques')
@login_required
def statistics():
    """Page des statistiques de l'utilisateur"""
    user_id = session.get('user_id')
    stats = get_user_statistics(user_id)

    return render_template('statistiques.html',
                          stats=stats,
                          page='parametres')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
