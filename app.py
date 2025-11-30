import os
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAUX_FOLDER = os.path.join(BASE_DIR, 'static/pdfs/originaux')
UPLOADS_FOLDER = os.path.join(BASE_DIR, 'static/pdfs/uploads')

# Création automatique des dossiers si absents
os.makedirs(ORIGINAUX_FOLDER, exist_ok=True)
os.makedirs(UPLOADS_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def home():
    # --- 1. GESTION DE L'UPLOAD (Vers dossier 'uploads' uniquement) ---
    if request.method == 'POST':
        if 'fichier_pdf' not in request.files:
            return redirect(request.url)
        file = request.files['fichier_pdf']
        if file and file.filename.lower().endswith('.pdf'):
            # Sauvegarde dans le dossier UTILISATEUR
            file.save(os.path.join(UPLOADS_FOLDER, file.filename))
            return redirect(url_for('home'))

    # --- 2. RÉCUPÉRATION DES FICHIERS (Séparés) ---
    
    # Liste A : Les Originaux (Admin)
    fichiers_org = [f for f in os.listdir(ORIGINAUX_FOLDER) if f.lower().endswith('.pdf')]
    
    # Liste B : Les Uploads (Utilisateurs)
    fichiers_usr = [f for f in os.listdir(UPLOADS_FOLDER) if f.lower().endswith('.pdf')]
    
    # On envoie les deux listes séparées au HTML
    return render_template('index.html', originaux=fichiers_org, uploads=fichiers_usr)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)