# Application de Flashcards avec Génération automatique depuis PDF

Application Flask pour gérer des cours PDF et générer automatiquement des flashcards à partir de documents PDF uploadés.

## Fonctionnalités

- Authentification utilisateur (login/register)
- Gestion de cours et fiches PDF
- Système de flashcards avec répétition espacée
- **Génération automatique de flashcards depuis PDF via API OpenAI**

## Installation

1. Installer les dépendances:
```bash
pip install -r requirements.txt
```

2. Lancer l'application:
```bash
python app.py
```

L'application sera accessible sur `http://localhost:5000`

## Nouvelle fonctionnalité: Génération de flashcards depuis PDF

### Comment ça marche?

1. **Uploadez un PDF** sur la page "Cours" ou "Fiches"
2. **Cliquez sur "⚡ Générer flashcards"** à côté du PDF uploadé
3. Dans la modal qui s'ouvre, configurez:
   - **Nom du deck**: Un nom unique pour identifier vos flashcards
   - **Nombre de flashcards**: Entre 5 et 30 (par défaut: 10)
   - **Clé API OpenAI**: Votre clé API (non sauvegardée)
4. **Cliquez sur "Générer"**

### Configuration de l'API OpenAI

Pour utiliser la génération de flashcards, vous avez besoin d'une clé API OpenAI:

1. Créez un compte sur [OpenAI Platform](https://platform.openai.com/)
2. Allez dans [API Keys](https://platform.openai.com/api-keys)
3. Créez une nouvelle clé API
4. Copiez la clé (format: `sk-...`)
5. Utilisez cette clé dans le formulaire de génération

**Note**: La clé n'est pas sauvegardée par l'application pour des raisons de sécurité.

### Modèle utilisé

L'application utilise le modèle `gpt-4o-mini` d'OpenAI, qui offre un excellent rapport qualité/prix pour la génération de flashcards.

### Format des flashcards générées

- Questions claires et précises basées sur le contenu du PDF
- Réponses concises mais complètes
- Support des formules mathématiques en LaTeX (format: `$formule$`)
- Sauvegarde automatique dans un fichier CSV dans `flashcards_data/`

### Exemple d'utilisation

1. Uploadez un cours de statistiques (`stats_chap1.pdf`)
2. Cliquez sur "⚡ Générer flashcards"
3. Nom du deck: `statistiques_chapitre1`
4. Nombre de flashcards: `15`
5. Entrez votre clé API OpenAI
6. Cliquez sur "Générer"
7. Allez dans le menu "Flashcards" pour réviser votre nouveau deck

### API Endpoint

Pour les développeurs, l'endpoint API est accessible via:

```
POST /api/generer-flashcards
Content-Type: application/json

{
  "pdf_filename": "mon_cours.pdf",
  "categorie": "cours",
  "source": "uploads",
  "nb_flashcards": 10,
  "api_key": "sk-...",
  "nom_deck": "mon_deck"
}
```

Réponse en cas de succès:
```json
{
  "success": true,
  "message": "10 flashcards générées avec succès",
  "deck_name": "mon_deck.csv",
  "nb_flashcards": 10
}
```

## Structure du projet

```
TDLOG_project/
├── app.py                  # Application Flask principale
├── requirements.txt        # Dépendances Python
├── users.json             # Données utilisateurs (hashées)
├── user_progress.json     # Progression des flashcards
├── flashcards_data/       # Decks de flashcards (CSV)
├── templates/             # Templates HTML
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── cours.html
│   ├── fiches.html
│   ├── flashcards_menu.html
│   ├── flashcards.html
│   └── card_fragment.html
└── static/
    └── pdfs/
        ├── cours/
        │   ├── originaux/
        │   └── uploads/
        └── fiches/
            ├── originaux/
            └── uploads/
```

## Sécurité

- Mots de passe hashés avec scrypt
- Session utilisateur sécurisée
- Clé API OpenAI non sauvegardée
- Validation des fichiers PDF uniquement

## Technologies utilisées

- **Backend**: Flask 3.1.2
- **Frontend**: Bootstrap 5.3, Alpine.js, HTMX
- **PDF**: PyPDF2 3.0.1
- **IA**: OpenAI API (gpt-4o-mini)
- **Math**: MathJax 3
