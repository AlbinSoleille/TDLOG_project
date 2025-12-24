import os
import json
import random
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'CHANGE_MOI_POUR_UN_TRUC_SECRET' # Clé obligatoire pour chiffrer les cookies de session
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- DECORATEUR DE SÉCURITÉ ---
# C'est un "vigile" qu'on place devant chaque page
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- GESTION DES DONNÉES UTILISATEURS ---

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

# --- GESTION FLASHCARDS & PROGRESSION ---

def charger_donnees_perso():
    """Charge les cartes et LA progression DE L'UTILISATEUR CONNECTÉ"""
    user = session['user'] # On récupère le nom de l'utilisateur connecté

    # 1. Cartes
    path_cartes = os.path.join(BASE_DIR, 'flashcards.json')
    cartes = []
    if os.path.exists(path_cartes):
        with open(path_cartes, 'r', encoding='utf-8') as f:
            cartes = json.load(f)

    # 2. Progression Globale
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    global_progress = {}
    if os.path.exists(path_progress):
        with open(path_progress, 'r', encoding='utf-8') as f:
            global_progress = json.load(f)
    
    # On ne renvoie que la partie de l'utilisateur (ou vide si nouveau)
    user_progress = global_progress.get(user, {})
    return cartes, user_progress, global_progress

def sauvegarder_progress(question, est_connu):
    user = session['user']
    _, user_progress, global_progress = charger_donnees_perso()
    
    score_actuel = user_progress.get(question, 0)
    
    if est_connu:
        nouveau_score = min(score_actuel + 1, 5)
    else:
        nouveau_score = 0
        
    # Mise à jour locale
    user_progress[question] = nouveau_score
    
    # Mise à jour globale
    global_progress[user] = user_progress
    
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    with open(path_progress, 'w', encoding='utf-8') as f:
        json.dump(global_progress, f, ensure_ascii=False, indent=4)

def piocher_carte_intelligente():
    cartes, user_progress, _ = charger_donnees_perso()
    if not cartes: return None
        
    poids = []
    for c in cartes:
        score = user_progress.get(c['question'], 0)
        poids.append(10 / (score + 1))
        
    carte_choisie = random.choices(cartes, weights=poids, k=1)[0]
    return carte_choisie

# --- ROUTES D'AUTHENTIFICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        action = request.form['action'] # 'login' ou 'register'
        
        users = charger_users()

        if action == 'register':
            if username in users:
                flash("Ce nom d'utilisateur est déjà pris !")
            else:
                users[username] = generate_password_hash(password)
                sauver_users(users)
                session['user'] = username
                return redirect(url_for('cours'))
                
        elif action == 'login':
            if username in users and check_password_hash(users[username], password):
                session['user'] = username
                return redirect(url_for('cours'))
            else:
                flash("Identifiant ou mot de passe incorrect.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- ROUTES PROTÉGÉES (Ajout de @login_required) ---

def gestion_dossier(categorie):
    # (Copie ta fonction gestion_dossier ici, elle ne change pas)
    # ... Je la raccourcis pour la lisibilité, mais garde ton code complet ...
    dossier_org = os.path.join(BASE_DIR, 'static/pdfs', categorie, 'originaux')
    dossier_upl = os.path.join(BASE_DIR, 'static/pdfs', categorie, 'uploads')
    os.makedirs(dossier_org, exist_ok=True)
    os.makedirs(dossier_upl, exist_ok=True)

    if request.method == 'POST':
        if 'fichier_pdf' in request.files:
            file = request.files['fichier_pdf']
            if file and file.filename.lower().endswith('.pdf'):
                file.save(os.path.join(dossier_upl, file.filename))
                return True
    
    liste_org = [f for f in os.listdir(dossier_org) if f.lower().endswith('.pdf')]
    liste_upl = [f for f in os.listdir(dossier_upl) if f.lower().endswith('.pdf')]
    return liste_org, liste_upl


@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('cours'))
    return redirect(url_for('login'))

@app.route('/cours', methods=['GET', 'POST'])
@login_required  # <--- PROTECTION ACTIVE
def cours():
    resultat = gestion_dossier('cours')
    if resultat == True: return redirect(url_for('cours'))
    org, upl = resultat
    return render_template('cours.html', originaux=org, uploads=upl, page='cours')

@app.route('/fiches', methods=['GET', 'POST'])
@login_required  # <--- PROTECTION ACTIVE
def fiches():
    resultat = gestion_dossier('fiches')
    if resultat == True: return redirect(url_for('fiches'))
    org, upl = resultat
    return render_template('fiches.html', originaux=org, uploads=upl, page='fiches')

@app.route('/flashcards')
@login_required  # <--- PROTECTION ACTIVE
def flashcards():
    carte = piocher_carte_intelligente()
    return render_template('flashcards.html', page='flashcards', carte=carte)

@app.route('/flashcards/vote')
@login_required  # <--- PROTECTION ACTIVE
def vote_card():
    question = request.args.get('question')
    resultat = request.args.get('result')
    est_connu = (resultat == 'ok')
    sauvegarder_progress(question, est_connu)
    nouvelle_carte = piocher_carte_intelligente()
    return render_template('card_fragment.html', carte=nouvelle_carte)

# Pas besoin de route pour next_card, c'est vote_card qui fait le travail maintenant
# Mais si tu as gardé un bouton "Suivant" simple :
@app.route('/flashcards/next')
@login_required
def next_card():
    carte = piocher_carte_intelligente()
    return render_template('card_fragment.html', carte=carte)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)