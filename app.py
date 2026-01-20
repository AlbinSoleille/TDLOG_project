import os
import json
import csv
import random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
from openai import OpenAI

app = Flask(__name__)
app.secret_key = 'CLE_SECRETE_A_CHANGER'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On définit le dossier où chercher les CSV (theoj.csv, etc.)
FLASHCARDS_DIR = os.path.join(BASE_DIR, 'flashcards_data')
os.makedirs(FLASHCARDS_DIR, exist_ok=True)

# --- SECURITE ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- GESTION UTILISATEURS ---
def charger_users():
    path = os.path.join(BASE_DIR, 'users.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def sauver_users(users):
    path = os.path.join(BASE_DIR, 'users.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)

# --- GESTION FLASHCARDS (MULTI-FICHIERS) ---

def lister_decks():
    """Scan le dossier pour trouver theoj.csv et les autres"""
    if not os.path.exists(FLASHCARDS_DIR):
        return []
    # On ne garde que les fichiers .csv
    files = [f for f in os.listdir(FLASHCARDS_DIR) if f.lower().endswith('.csv')]
    return files

def charger_deck_csv(deck_filename):
    """Lit le contenu d'un fichier CSV spécifique"""
    path = os.path.join(FLASHCARDS_DIR, deck_filename)
    cartes = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8', newline='') as csvfile:
                # Détection automatique du séparateur (virgule ou point-virgule)
                dialect = csv.Sniffer().sniff(csvfile.read(1024))
                csvfile.seek(0)
                reader = csv.reader(csvfile, dialect)
                
                for row in reader:
                    # On prend les lignes qui ont au moins 2 colonnes (Question, Réponse)
                    if len(row) >= 2:
                        cartes.append({'question': row[0], 'reponse': row[1]})
        except Exception as e:
            print(f"Erreur de lecture {deck_filename}: {e}")
    return cartes

def charger_progression(deck_name):
    """Charge les scores de l'utilisateur pour CE fichier précis"""
    user = session['user']
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    
    global_progress = {}
    if os.path.exists(path_progress):
        with open(path_progress, 'r', encoding='utf-8') as f:
            global_progress = json.load(f)
    
    # Structure : { "Yacine": { "theoj.csv": { "Question...": Score } } }
    user_data = global_progress.get(user, {})
    deck_progress = user_data.get(deck_name, {})
    
    return deck_progress, global_progress

def sauvegarder_score_csv(deck_name, question, est_connu):
    user = session['user']
    deck_progress, global_progress = charger_progression(deck_name)
    
    score_actuel = deck_progress.get(question, 0)
    
    if est_connu:
        nouveau_score = min(score_actuel + 1, 5)
    else:
        nouveau_score = 0
        
    # Mise à jour
    deck_progress[question] = nouveau_score
    
    # On sauvegarde tout
    if user not in global_progress:
        global_progress[user] = {}
    global_progress[user][deck_name] = deck_progress
    
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    with open(path_progress, 'w', encoding='utf-8') as f:
        json.dump(global_progress, f, ensure_ascii=False, indent=4)

def piocher_carte_csv(deck_name):
    cartes = charger_deck_csv(deck_name)
    if not cartes: return None

    deck_progress, _ = charger_progression(deck_name)

    poids = []
    for c in cartes:
        score = deck_progress.get(c['question'], 0)
        poids.append(10 / (score + 1))

    return random.choices(cartes, weights=poids, k=1)[0]

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

def sauvegarder_flashcards_csv(flashcards, nom_fichier):
    """Sauvegarde les flashcards générées dans un fichier CSV"""
    try:
        path = os.path.join(FLASHCARDS_DIR, nom_fichier)
        with open(path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            for card in flashcards:
                writer.writerow([card['question'], card['reponse']])
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du CSV: {e}")
        return False

# --- ROUTES AUTHENTIFICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si déjà connecté, rediriger vers cours
    if 'user' in session:
        return redirect(url_for('cours'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        users = charger_users()
        
        if not username or not password:
            flash("Veuillez remplir tous les champs")
        elif username in users and check_password_hash(users[username], password):
            session['user'] = username
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
        users = charger_users()
        
        # Validations
        if not username or not password:
            flash("Veuillez remplir tous les champs")
        elif len(username) < 3:
            flash("L'identifiant doit contenir au moins 3 caractères")
        elif len(password) < 4:
            flash("Le mot de passe doit contenir au moins 4 caractères")
        elif password != password_confirm:
            flash("Les mots de passe ne correspondent pas")
        elif username in users:
            flash("Cet identifiant est déjà pris")
        else:
            # Création du compte
            users[username] = generate_password_hash(password)
            sauver_users(users)
            session['user'] = username
            return redirect(url_for('cours'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
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
    """Affiche la liste des decks (dont theoj.csv)"""
    decks = lister_decks()
    return render_template('flashcards_menu.html', decks=decks, page='flashcards')

@app.route('/flashcards/play')
@login_required
def flashcards_play():
    """Lance le jeu sur le fichier choisi"""
    deck_name = request.args.get('deck')
    # Si aucun deck choisi, retour au menu
    if not deck_name:
        return redirect(url_for('flashcards_menu'))
        
    carte = piocher_carte_csv(deck_name)
    return render_template('flashcards.html', page='flashcards', carte=carte, current_deck=deck_name)

@app.route('/flashcards/vote')
@login_required
def vote_card():
    # On récupère les infos (Deck + Question + Résultat)
    deck_name = request.args.get('deck')
    question = request.args.get('question')
    resultat = request.args.get('result')

    # On sauvegarde
    sauvegarder_score_csv(deck_name, question, (resultat == 'ok'))

    # On pioche la suivante
    nouvelle_carte = piocher_carte_csv(deck_name)
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

        # Sauvegarde dans un fichier CSV
        nom_fichier_csv = nom_deck if nom_deck.endswith('.csv') else f"{nom_deck}.csv"
        if sauvegarder_flashcards_csv(flashcards, nom_fichier_csv):
            return jsonify({
                'success': True,
                'message': f'{len(flashcards)} flashcards générées avec succès',
                'deck_name': nom_fichier_csv,
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
