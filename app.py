import os
import csv
import random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
from openai import OpenAI

# Importer les fonctions de la base de données
from database import (
    init_database, get_user_by_username, create_user,
    get_all_decks, get_deck_by_name, create_deck,
    get_flashcards_by_deck, create_flashcard,
    get_all_user_progress, update_progress
)

app = Flask(__name__)
app.secret_key = 'CLE_SECRETE_A_CHANGER'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dossier pour les flashcards CSV (pour la génération depuis PDF)
FLASHCARDS_DIR = os.path.join(BASE_DIR, 'flashcards_data')
os.makedirs(FLASHCARDS_DIR, exist_ok=True)

# Initialiser la base de données au démarrage
init_database()

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

def generer_flashcards_via_api(texte, nb_flashcards=10, api_key=None):
    """Génère des flashcards à partir du texte extrait en utilisant OpenAI"""
    if not api_key:
        return None, "Clé API OpenAI non configurée"

    try:
        client = OpenAI(api_key=api_key)

        prompt = f"""Tu es un assistant pédagogique. À partir du texte suivant, génère exactement {nb_flashcards} flashcards de qualité pour aider l'étudiant à mémoriser les concepts clés.

Texte du cours:
{texte[:8000]}

Règles:
- Génère exactement {nb_flashcards} paires question/réponse
- Les questions doivent être claires et précises
- Les réponses doivent être concises mais complètes
- Utilise la notation LaTeX entre $ pour les formules mathématiques (ex: $x^2$)
- Format de réponse: une ligne par flashcard au format: QUESTION;;;REPONSE
- Utilise EXACTEMENT trois points-virgules (;;;) comme séparateur

Exemple de format attendu:
Qu'est-ce qu'une variable aléatoire ?;;;Une fonction qui associe à chaque issue d'une expérience aléatoire un nombre réel
Quelle est la formule de la variance ?;;;$Var(X) = E[(X - E[X])^2] = E[X^2] - (E[X])^2$"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un assistant pédagogique expert en création de flashcards."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        contenu = response.choices[0].message.content

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

        return flashcards, None

    except Exception as e:
        return None, f"Erreur lors de la génération: {str(e)}"

def sauvegarder_flashcards_db(flashcards, nom_deck):
    """Sauvegarde les flashcards générées dans la base de données"""
    try:
        # Créer ou récupérer le deck
        deck_id = create_deck(nom_deck)

        # Ajouter les flashcards
        for card in flashcards:
            create_flashcard(deck_id, card['question'], card['reponse'])

        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde dans la DB: {e}")
        return False

# --- GESTION DES FLASHCARDS ---

def piocher_carte(deck_name, user_id):
    """Pioche une carte aléatoire en fonction du score de l'utilisateur"""
    deck = get_deck_by_name(deck_name)
    if not deck:
        return None

    # Récupérer toutes les flashcards avec leur progression
    cartes_progress = get_all_user_progress(user_id, deck['id'])

    if not cartes_progress:
        return None

    # Calculer les poids en fonction du score
    poids = []
    cartes = []

    for carte in cartes_progress:
        score = carte['score']
        # Plus le score est élevé, moins la carte a de chances d'être piochée
        poids.append(10 / (score + 1))
        cartes.append({
            'id': carte['id'],
            'question': carte['question'],
            'reponse': carte['answer']
        })

    # Piocher une carte aléatoire pondérée
    return random.choices(cartes, weights=poids, k=1)[0]

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
    """Affiche la liste des decks"""
    decks = get_all_decks()
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
    # On récupère les infos (Deck + Flashcard ID + Résultat)
    deck_name = request.args.get('deck')
    flashcard_id = request.args.get('flashcard_id')
    resultat = request.args.get('result')
    user_id = session.get('user_id')

    if flashcard_id and deck_name:
        flashcard_id = int(flashcard_id)

        # Récupérer le deck pour obtenir la progression
        deck = get_deck_by_name(deck_name)
        if deck:
            # Récupérer la progression actuelle
            progress_data = get_all_user_progress(user_id, deck['id'])
            current_score = 0

            for p in progress_data:
                if p['id'] == flashcard_id:
                    current_score = p['score']
                    break

            # Calculer le nouveau score
            if resultat == 'ok':
                nouveau_score = min(current_score + 1, 5)
            else:
                nouveau_score = 0

            # Sauvegarder la progression
            update_progress(user_id, flashcard_id, nouveau_score)

    # On pioche la suivante
    nouvelle_carte = piocher_carte(deck_name, user_id)
    return render_template('card_fragment.html', carte=nouvelle_carte, current_deck=deck_name)

# --- ROUTE GENERATION FLASHCARDS DEPUIS PDF ---

@app.route('/api/generer-flashcards', methods=['POST'])
@login_required
def generer_flashcards_from_pdf():
    """Endpoint API pour générer des flashcards à partir d'un PDF"""
    try:
        data = request.get_json()

        # Récupération des paramètres
        pdf_filename = data.get('pdf_filename')
        categorie = data.get('categorie', 'cours')  # 'cours' ou 'fiches'
        source = data.get('source', 'uploads')  # 'uploads' ou 'originaux'
        nb_flashcards = int(data.get('nb_flashcards', 10))
        api_key = data.get('api_key')
        nom_deck = data.get('nom_deck')

        if not pdf_filename or not api_key or not nom_deck:
            return jsonify({
                'success': False,
                'error': 'Paramètres manquants (pdf_filename, api_key, nom_deck requis)'
            }), 400

        # Construction du chemin du PDF
        pdf_path = os.path.join(BASE_DIR, 'static/pdfs', categorie, source, pdf_filename)

        if not os.path.exists(pdf_path):
            return jsonify({
                'success': False,
                'error': f'Fichier PDF non trouvé: {pdf_filename}'
            }), 404

        # Extraction du texte
        texte = extraire_texte_pdf(pdf_path)
        if not texte:
            return jsonify({
                'success': False,
                'error': 'Impossible d\'extraire le texte du PDF'
            }), 500

        # Génération des flashcards
        flashcards, error = generer_flashcards_via_api(texte, nb_flashcards, api_key)
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500

        if not flashcards:
            return jsonify({
                'success': False,
                'error': 'Aucune flashcard générée'
            }), 500

        # Sauvegarde dans la base de données SQLite
        if sauvegarder_flashcards_db(flashcards, nom_deck):
            return jsonify({
                'success': True,
                'message': f'{len(flashcards)} flashcards générées avec succès',
                'deck_name': nom_deck,
                'nb_flashcards': len(flashcards)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erreur lors de la sauvegarde des flashcards'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
