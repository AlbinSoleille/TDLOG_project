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
    get_user_prompt, save_user_prompt, get_user_statistics,
    get_user_flashcard_counts, create_folder, get_user_folders,
    get_decks_in_folder, move_deck_to_folder, get_folder_statistics,
    get_deck_statistics, rename_folder, delete_folder,
    get_user_streak, update_daily_activity, get_yearly_activity,
    get_leaderboard, toggle_leaderboard_visibility, can_see_leaderboard,
    get_show_in_leaderboard, get_user_security_question, verify_security_answer,
    update_user_password
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

# --- CONTEXT PROCESSOR POUR LE STREAK ---
@app.context_processor
def inject_streak():
    """Injecte le streak dans tous les templates"""
    if 'user_id' in session:
        streak = get_user_streak(session['user_id'])
        return dict(streak=streak)
    return dict(streak=0)

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

FICHE_RESUME_PROMPT_TEMPLATE = """Tu es un assistant pédagogique spécialisé en mathématiques. À partir du texte suivant, crée une fiche résumé structurée et claire.

Texte du cours:
{texte}

Règles strictes:
- Ne fiche que les DÉFINITIONS, PROPRIÉTÉS et EXEMPLES IMPORTANTS
- Structure en sections claires avec des titres markdown
- Utilise la notation LaTeX entre $ pour les formules mathématiques (ex: $x^2$)
- Sois concis mais complet
- Privilégie la clarté et l'organisation
- Utilise des listes à puces quand c'est pertinent
- Mets en évidence les théorèmes et propriétés clés

Format de la fiche:
# Titre du cours

## Définitions
...

## Propriétés principales
...

## Exemples importants
...

## Théorèmes clés
..."""

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

    # Questions de sécurité disponibles
    security_questions = [
        "Quel est le nom de famille de votre mère ?",
        "Quel est le nom de votre premier animal de compagnie ?",
        "Quelle est votre ville de naissance ?",
        "Quel est votre film préféré ?"
    ]

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        security_question = request.form.get('security_question', '')
        security_answer = request.form.get('security_answer', '').strip().lower()

        # Validations
        if not username or not password:
            flash("Veuillez remplir tous les champs")
        elif len(username) < 3:
            flash("L'identifiant doit contenir au moins 3 caractères")
        elif len(password) < 4:
            flash("Le mot de passe doit contenir au moins 4 caractères")
        elif password != password_confirm:
            flash("Les mots de passe ne correspondent pas")
        elif not security_question or not security_answer:
            flash("Veuillez choisir une question de sécurité et y répondre")
        elif get_user_by_username(username):
            flash("Cet identifiant est déjà pris")
        else:
            # Création du compte
            password_hash = generate_password_hash(password)
            # Hash de la réponse de sécurité (en minuscule pour éviter les problèmes de casse)
            security_answer_hash = generate_password_hash(security_answer)
            user_id = create_user(username, password_hash, security_question, security_answer_hash)
            session['user'] = username
            session['user_id'] = user_id
            return redirect(url_for('cours'))

    return render_template('register.html', security_questions=security_questions)

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Page de récupération de mot de passe - Étape 1: demander le nom d'utilisateur"""
    if 'user' in session:
        return redirect(url_for('cours'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()

        if not username:
            flash("Veuillez entrer votre identifiant")
        else:
            user = get_user_by_username(username)
            if not user:
                flash("Aucun compte trouvé avec cet identifiant")
            else:
                # Rediriger vers la page de réponse à la question de sécurité
                return redirect(url_for('reset_password', username=username))

    return render_template('forgot_password.html')

@app.route('/reset-password/<username>', methods=['GET', 'POST'])
def reset_password(username):
    """Page de récupération de mot de passe - Étape 2: répondre à la question et choisir nouveau mot de passe"""
    if 'user' in session:
        return redirect(url_for('cours'))

    user = get_user_by_username(username)
    if not user:
        flash("Utilisateur introuvable")
        return redirect(url_for('forgot_password'))

    security_question = get_user_security_question(username)
    if not security_question:
        flash("Aucune question de sécurité configurée pour ce compte")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        security_answer = request.form.get('security_answer', '').strip().lower()
        new_password = request.form.get('new_password', '')
        new_password_confirm = request.form.get('new_password_confirm', '')

        # Validation
        if not security_answer:
            flash("Veuillez répondre à la question de sécurité")
        elif not new_password:
            flash("Veuillez entrer un nouveau mot de passe")
        elif len(new_password) < 4:
            flash("Le mot de passe doit contenir au moins 4 caractères")
        elif new_password != new_password_confirm:
            flash("Les mots de passe ne correspondent pas")
        else:
            # Vérifier la réponse de sécurité
            if verify_security_answer(username, security_answer):
                # Réponse correcte, mettre à jour le mot de passe
                new_password_hash = generate_password_hash(new_password)
                update_user_password(username, new_password_hash)
                flash("Mot de passe réinitialisé avec succès ! Vous pouvez maintenant vous connecter.")
                return redirect(url_for('login'))
            else:
                flash("Réponse incorrecte à la question de sécurité")

    return render_template('reset_password.html', username=username, security_question=security_question)

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

@app.route('/fiches', methods=['GET'])
@login_required
def fiches():
    """Affiche les fiches résumé générées"""
    from datetime import datetime

    fiches_dir = os.path.join(BASE_DIR, 'static/fiches')
    fiches_list = []

    # Lister tous les fichiers .md dans le dossier fiches
    if os.path.exists(fiches_dir):
        for filename in os.listdir(fiches_dir):
            if filename.endswith('.md') and filename != 'README.md':
                filepath = os.path.join(fiches_dir, filename)
                # Récupérer la date de création
                timestamp = os.path.getctime(filepath)
                date_creation = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M')

                # Nom lisible (enlever .md et remplacer _ par espace)
                name = filename.replace('.md', '').replace('_', ' ').replace('resume ', '').title()

                fiches_list.append({
                    'filename': filename,
                    'name': name,
                    'date': date_creation
                })

    # Trier par date de création (plus récent en premier)
    fiches_list.sort(key=lambda x: x['date'], reverse=True)

    return render_template('fiches.html', fiches=fiches_list, page='fiches')

# --- ROUTES FLASHCARDS ---

def build_folder_tree(user_id, parent_id=None):
    """Construit récursivement l'arborescence des dossiers avec leurs statistiques"""
    folders = get_user_folders(user_id, parent_id)
    result = []

    for folder in folders:
        folder_dict = {
            'id': folder['id'],
            'name': folder['name'],
            'type': 'folder',
            'stats': get_folder_statistics(user_id, folder['id']),
            'children': build_folder_tree(user_id, folder['id']),
            'decks': []
        }

        # Récupérer les decks dans ce dossier
        decks = get_decks_in_folder(user_id, folder['id'])
        for deck in decks:
            folder_dict['decks'].append({
                'id': deck['id'],
                'name': deck['name'],
                'type': 'deck',
                'stats': get_deck_statistics(user_id, deck['id'])
            })

        result.append(folder_dict)

    return result


@app.route('/flashcards')
@login_required
def flashcards_menu():
    """Affiche la liste des decks de l'utilisateur avec arborescence"""
    user_id = session.get('user_id')

    # Construire l'arborescence des dossiers
    folder_tree = build_folder_tree(user_id)

    # Récupérer les decks à la racine (sans dossier)
    root_decks = get_decks_in_folder(user_id, None)
    root_decks_list = []
    for deck in root_decks:
        root_decks_list.append({
            'id': deck['id'],
            'name': deck['name'],
            'type': 'deck',
            'stats': get_deck_statistics(user_id, deck['id'])
        })

    # Récupérer les statistiques globales
    global_stats = get_user_flashcard_counts(user_id)

    return render_template('flashcards_menu.html',
                         folder_tree=folder_tree,
                         root_decks=root_decks_list,
                         stats=global_stats,
                         page='flashcards')


@app.route('/api/folders/create', methods=['POST'])
@login_required
def api_create_folder():
    """API pour créer un nouveau dossier"""
    user_id = session.get('user_id')
    data = request.get_json()
    folder_name = data.get('name')
    parent_id = data.get('parent_id')

    if not folder_name:
        return jsonify({'success': False, 'error': 'Nom du dossier requis'}), 400

    folder_id = create_folder(user_id, folder_name, parent_id)
    return jsonify({'success': True, 'folder_id': folder_id})


@app.route('/api/folders/<int:folder_id>/rename', methods=['POST'])
@login_required
def api_rename_folder(folder_id):
    """API pour renommer un dossier"""
    data = request.get_json()
    new_name = data.get('name')

    if not new_name:
        return jsonify({'success': False, 'error': 'Nouveau nom requis'}), 400

    rename_folder(folder_id, new_name)
    return jsonify({'success': True})


@app.route('/api/folders/<int:folder_id>/delete', methods=['POST'])
@login_required
def api_delete_folder(folder_id):
    """API pour supprimer un dossier"""
    delete_folder(folder_id)
    return jsonify({'success': True})


@app.route('/api/decks/<int:deck_id>/move', methods=['POST'])
@login_required
def api_move_deck(deck_id):
    """API pour déplacer un deck dans un dossier"""
    data = request.get_json()
    folder_id = data.get('folder_id')

    move_deck_to_folder(deck_id, folder_id)
    return jsonify({'success': True})


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

        # Mettre à jour l'activité quotidienne
        # Vérifier si toutes les cartes dues sont terminées
        stats = get_user_flashcard_counts(user_id)
        all_completed = (stats['new'] == 0 and stats['relearn'] == 0 and stats['review'] == 0)
        update_daily_activity(user_id, 1, all_completed)

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
    from datetime import datetime, date, timedelta
    import calendar

    user_id = session.get('user_id')
    stats = get_user_statistics(user_id)

    # Générer le calendrier annuel
    year = datetime.now().year
    activity_dict, max_cards = get_yearly_activity(user_id, year)

    # Construire le calendrier par mois
    calendar_data = []
    for month in range(1, 13):
        month_name = calendar.month_abbr[month]
        # Obtenir le calendrier du mois (liste de semaines)
        month_cal = calendar.monthcalendar(year, month)

        weeks_data = []
        for week in month_cal:
            week_data = []
            for day_num in week:
                if day_num == 0:  # Jour vide
                    week_data.append(None)
                else:
                    day_date = date(year, month, day_num)
                    day_str = day_date.strftime('%Y-%m-%d')

                    # Récupérer l'activité du jour
                    activity = activity_dict.get(day_str, {'cards_reviewed': 0, 'all_completed': 0})
                    cards = activity['cards_reviewed']
                    completed = activity['all_completed']

                    # Déterminer la couleur
                    if cards == 0:
                        color = '#ebedf0'  # Gris clair (aucune révision)
                        status = 'no-activity'
                    elif completed:
                        # Vert avec intensité selon le nombre de cartes
                        intensity = min(cards / max_cards, 1.0)
                        if intensity < 0.25:
                            color = '#9be9a8'
                        elif intensity < 0.5:
                            color = '#40c463'
                        elif intensity < 0.75:
                            color = '#30a14e'
                        else:
                            color = '#216e39'
                        status = 'completed'
                    else:
                        # Bleu avec intensité selon le nombre de cartes
                        intensity = min(cards / max_cards, 1.0)
                        if intensity < 0.25:
                            color = '#c6dbef'
                        elif intensity < 0.5:
                            color = '#9ecae1'
                        elif intensity < 0.75:
                            color = '#6baed6'
                        else:
                            color = '#3182bd'
                        status = 'partial'

                    week_data.append({
                        'date': day_date.strftime('%d/%m/%Y'),
                        'cards': cards,
                        'completed': completed,
                        'color': color,
                        'status': status
                    })

            weeks_data.append(week_data)

        calendar_data.append((month_name, weeks_data))

    year_activity = {
        'year': year,
        'calendar': calendar_data
    }

    return render_template('statistiques.html',
                          stats=stats,
                          year_activity=year_activity,
                          page='parametres')


@app.route('/parametres/classement')
@login_required
def leaderboard():
    """Page du classement des utilisateurs"""
    user_id = session.get('user_id')

    # Vérifier si l'utilisateur peut voir le classement
    can_view = can_see_leaderboard(user_id)

    if can_view:
        # Récupérer le classement
        leaderboard_data = get_leaderboard()
    else:
        leaderboard_data = []

    # Vérifier si l'utilisateur est visible
    show_in_leaderboard = get_show_in_leaderboard(user_id)

    return render_template('leaderboard.html',
                          leaderboard=leaderboard_data,
                          can_view=can_view,
                          show_in_leaderboard=show_in_leaderboard,
                          current_user_id=user_id,
                          page='parametres')


@app.route('/parametres/classement/toggle', methods=['POST'])
@login_required
def toggle_leaderboard_visibility_route():
    """Active/désactive la visibilité de l'utilisateur dans le classement"""
    user_id = session.get('user_id')
    new_value = toggle_leaderboard_visibility(user_id)

    if new_value:
        flash('Vous apparaissez maintenant dans le classement.', 'success')
    else:
        flash('Vous avez été retiré du classement.', 'info')

    return redirect(url_for('leaderboard'))


@app.route('/api/supprimer-fiche', methods=['POST'])
@login_required
def supprimer_fiche():
    """Endpoint API pour supprimer une fiche résumé"""
    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({
                'success': False,
                'error': 'Nom de fichier requis'
            }), 400

        # Vérifier que c'est bien un fichier .md
        if not filename.endswith('.md'):
            return jsonify({
                'success': False,
                'error': 'Seuls les fichiers .md peuvent être supprimés'
            }), 403

        # Construction du chemin de la fiche
        fiche_path = os.path.join(BASE_DIR, 'static/fiches', filename)

        if not os.path.exists(fiche_path):
            return jsonify({
                'success': False,
                'error': f'Fiche non trouvée: {filename}'
            }), 404

        # Supprimer le fichier
        os.remove(fiche_path)
        print(f"✅ Fiche supprimée: {fiche_path}")

        return jsonify({
            'success': True,
            'message': f'Fiche "{filename}" supprimée avec succès'
        })

    except Exception as e:
        print(f"❌ Erreur lors de la suppression de la fiche: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/supprimer-pdf', methods=['POST'])
@login_required
def supprimer_pdf():
    """Endpoint API pour supprimer un PDF uploadé"""
    try:
        data = request.get_json()
        print(f"\n{'='*60}")
        print(f"🗑️  SUPPRESSION DE PDF - Nouvelle requête")
        print(f"{'='*60}")

        # Récupération des paramètres
        filename = data.get('filename')
        categorie = data.get('categorie', 'cours')
        source = data.get('source', 'uploads')

        print(f"📄 Fichier: {filename}")
        print(f"📁 Catégorie: {categorie}, Source: {source}")

        if not filename:
            print("❌ Nom de fichier manquant")
            return jsonify({
                'success': False,
                'error': 'Nom de fichier requis'
            }), 400

        # Vérifier que c'est bien un fichier uploadé (sécurité)
        if source != 'uploads':
            print("❌ Tentative de suppression d'un fichier non-uploadé")
            return jsonify({
                'success': False,
                'error': 'Seuls les fichiers uploadés peuvent être supprimés'
            }), 403

        # Construction du chemin du PDF
        pdf_path = os.path.join(BASE_DIR, 'static/pdfs', categorie, source, filename)
        print(f"🔍 Chemin PDF: {pdf_path}")

        if not os.path.exists(pdf_path):
            print(f"❌ Fichier PDF non trouvé: {pdf_path}")
            return jsonify({
                'success': False,
                'error': f'Fichier PDF non trouvé: {filename}'
            }), 404

        # Supprimer le fichier
        os.remove(pdf_path)
        print(f"✅ Fichier supprimé: {pdf_path}")

        return jsonify({
            'success': True,
            'message': f'PDF "{filename}" supprimé avec succès'
        })

    except Exception as e:
        print(f"❌ Erreur lors de la suppression du PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/generer-fiche', methods=['POST'])
@login_required
def generer_fiche_from_pdf():
    """Endpoint API pour générer une fiche résumé à partir d'un PDF"""
    try:
        data = request.get_json()
        print(f"\n{'='*60}")
        print(f"📝 GÉNÉRATION DE FICHE RÉSUMÉ - Nouvelle requête")
        print(f"{'='*60}")

        # Récupération des paramètres
        pdf_filename = data.get('pdf_filename')
        categorie = data.get('categorie', 'cours')
        source = data.get('source', 'uploads')
        fiche_nom = data.get('fiche_nom')

        print(f"📄 PDF: {pdf_filename}")
        print(f"📁 Catégorie: {categorie}, Source: {source}")
        print(f"📝 Nom de la fiche: {fiche_nom}")

        if not pdf_filename or not fiche_nom:
            print("❌ Paramètres manquants")
            return jsonify({
                'success': False,
                'error': 'Paramètres manquants (pdf_filename, fiche_nom requis)'
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
            print("❌ Impossible d'extraire le texte du PDF")
            return jsonify({
                'success': False,
                'error': 'Impossible d\'extraire le texte du PDF'
            }), 500

        print(f"✅ Texte extrait: {len(texte)} caractères")

        # Génération de la fiche via l'API
        print("🤖 Génération de la fiche résumé via l'API...")
        fiche_content = generer_fiche_via_api(texte)

        if not fiche_content:
            print("❌ Échec de la génération de la fiche")
            return jsonify({
                'success': False,
                'error': 'Échec de la génération de la fiche résumé'
            }), 500

        # Créer le dossier pour les fiches si nécessaire
        fiches_dir = os.path.join(BASE_DIR, 'static/fiches')
        os.makedirs(fiches_dir, exist_ok=True)

        # Sauvegarder la fiche
        fiche_filename = f"{fiche_nom}.md"
        fiche_path = os.path.join(fiches_dir, fiche_filename)

        with open(fiche_path, 'w', encoding='utf-8') as f:
            f.write(fiche_content)

        print(f"✅ Fiche sauvegardée: {fiche_path}")

        return jsonify({
            'success': True,
            'message': 'Fiche résumé générée avec succès',
            'fiche_name': fiche_nom,
            'download_url': url_for('static', filename=f'fiches/{fiche_filename}')
        })

    except Exception as e:
        print(f"❌ Erreur lors de la génération de la fiche: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def generer_fiche_via_api(texte):
    """Génère une fiche résumé à partir du texte extrait en utilisant l'API configurée"""

    print(f"🔍 Génération de fiche résumé avec {API_PROVIDER}")

    # Formatter le prompt
    prompt = FICHE_RESUME_PROMPT_TEMPLATE.format(texte=texte[:8000])

    try:
        if API_PROVIDER == 'claude':
            from anthropic import Anthropic

            if ANTHROPIC_API_KEY == 'votre-cle-api-claude-ici':
                print("⚠️  Clé API Claude non configurée - Génération d'une fiche d'exemple")
                return "# Fiche Résumé - Mode Test\n\nCeci est une fiche d'exemple générée en mode test.\n\n## Note\nConfigurez votre clé API dans config.py pour générer de vraies fiches."

            print(f"📡 Appel API Claude ({MODELS['claude']})")
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=MODELS['claude'],
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            fiche_content = response.content[0].text
            print(f"✅ Fiche générée ({len(fiche_content)} caractères)")
            return fiche_content

        elif API_PROVIDER == 'gemini':
            import google.generativeai as genai

            if GOOGLE_API_KEY == 'votre-cle-api-gemini-ici':
                print("⚠️  Clé API Gemini non configurée - Génération d'une fiche d'exemple")
                return "# Fiche Résumé - Mode Test\n\nCeci est une fiche d'exemple générée en mode test.\n\n## Note\nConfigurez votre clé API dans config.py pour générer de vraies fiches."

            print(f"📡 Appel API Gemini ({MODELS['gemini']})")
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(MODELS['gemini'])
            response = model.generate_content(prompt)
            fiche_content = response.text
            print(f"✅ Fiche générée ({len(fiche_content)} caractères)")
            return fiche_content

        elif API_PROVIDER == 'openai':
            from openai import OpenAI

            if OPENAI_API_KEY == 'votre-cle-api-openai-ici':
                print("⚠️  Clé API OpenAI non configurée - Génération d'une fiche d'exemple")
                return "# Fiche Résumé - Mode Test\n\nCeci est une fiche d'exemple générée en mode test.\n\n## Note\nConfigurez votre clé API dans config.py pour générer de vraies fiches."

            print(f"📡 Appel API OpenAI ({MODELS['openai']})")
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=MODELS['openai'],
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=4000
            )
            fiche_content = response.choices[0].message.content
            print(f"✅ Fiche générée ({len(fiche_content)} caractères)")
            return fiche_content

        else:
            print(f"❌ Provider inconnu: {API_PROVIDER}")
            return None

    except Exception as e:
        print(f"❌ Erreur API: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
