"""
Configuration de l'application - API Keys et paramètres

⚠️ IMPORTANT :
1. Copiez ce fichier en le renommant 'config.py'
2. Remplacez les clés API par vos vraies clés
3. Ne committez JAMAIS config.py (il est dans .gitignore)

Pour obtenir vos clés API, consultez CONFIGURATION_API.md
"""

# === CONFIGURATION API ===
# Choisissez votre provider: 'claude', 'gemini', ou 'openai'
API_PROVIDER = 'gemini'  # Recommandé: Gemini est GRATUIT (60 req/min)

# === CLÉS API ===
# Remplacez par votre vraie clé API

# API Claude (Anthropic) - Très peu cher (~$0.001 par génération)
# Obtenez votre clé sur: https://console.anthropic.com/
ANTHROPIC_API_KEY = 'votre-cle-api-claude-ici'

# API Gemini (Google) - GRATUIT (60 req/min, 1500 req/jour)
# Obtenez votre clé sur: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY = 'votre-cle-api-gemini-ici'

# API OpenAI (optionnel) - Plus cher
# Obtenez votre clé sur: https://platform.openai.com/api-keys
OPENAI_API_KEY = 'votre-cle-api-openai-ici'

# === PARAMÈTRES DE GÉNÉRATION ===
# Modèles à utiliser pour chaque provider
MODELS = {
    'claude': 'claude-3-haiku-20240307',  # Rapide et pas cher
    'gemini': 'gemini-2.0-flash',  # Gratuit jusqu'à un certain quota
    'openai': 'gpt-4o-mini'  # Version économique d'OpenAI
}
