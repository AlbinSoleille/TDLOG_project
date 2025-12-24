import os
import json
import random
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- GESTION PDFS (Code existant inchangé) ---
def gestion_dossier(categorie):
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

# --- NOUVEAU : GESTION FLASHCARDS INTELLIGENTE ---

def charger_donnees():
    """Charge les questions et le fichier de progression"""
    # 1. Les Cartes
    path_cartes = os.path.join(BASE_DIR, 'flashcards.json')
    cartes = []
    if os.path.exists(path_cartes):
        with open(path_cartes, 'r', encoding='utf-8') as f:
            cartes = json.load(f)

    # 2. Les Scores (Progression)
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    progress = {}
    if os.path.exists(path_progress):
        with open(path_progress, 'r', encoding='utf-8') as f:
            progress = json.load(f)
            
    return cartes, progress

def sauvegarder_progress(question, est_connu):
    """Met à jour le score d'une question dans le JSON"""
    _, progress = charger_donnees()
    path_progress = os.path.join(BASE_DIR, 'user_progress.json')
    
    score_actuel = progress.get(question, 0)
    
    if est_connu:
        # On augmente le score (max 5) -> La carte reviendra moins souvent
        nouveau_score = min(score_actuel + 1, 5)
    else:
        # On remet à 0 -> La carte reviendra très vite
        nouveau_score = 0
        
    progress[question] = nouveau_score
    
    with open(path_progress, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=4)

def piocher_carte_intelligente():
    """Pioche une carte avec probabilité inverse au score"""
    cartes, progress = charger_donnees()
    
    if not cartes:
        return None
        
    # Calcul des poids (Score 0 = Poids 10 / Score 5 = Poids 1.6)
    poids = []
    for c in cartes:
        score = progress.get(c['question'], 0)
        poids.append(10 / (score + 1))
        
    # Tirage pondéré
    carte_choisie = random.choices(cartes, weights=poids, k=1)[0]
    return carte_choisie

# --- ROUTES ---

@app.route('/')
@app.route('/cours', methods=['GET', 'POST'])
def cours():
    resultat = gestion_dossier('cours')
    if resultat == True: return redirect(url_for('cours'))
    org, upl = resultat
    return render_template('cours.html', originaux=org, uploads=upl, page='cours')

@app.route('/fiches', methods=['GET', 'POST'])
def fiches():
    resultat = gestion_dossier('fiches')
    if resultat == True: return redirect(url_for('fiches'))
    org, upl = resultat
    return render_template('fiches.html', originaux=org, uploads=upl, page='fiches')

# --- ROUTES FLASHCARDS MISES A JOUR ---

@app.route('/flashcards')
def flashcards():
    # Page principale
    carte = piocher_carte_intelligente()
    return render_template('flashcards.html', page='flashcards', carte=carte)

@app.route('/flashcards/vote')
def vote_card():
    # Route appelée par les boutons (HTMX)
    question = request.args.get('question')
    resultat = request.args.get('result') # 'ok' ou 'nok'
    
    # 1. On sauvegarde
    est_connu = (resultat == 'ok')
    sauvegarder_progress(question, est_connu)
    
    # 2. On renvoie la prochaine carte
    nouvelle_carte = piocher_carte_intelligente()
    return render_template('card_fragment.html', carte=nouvelle_carte)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)