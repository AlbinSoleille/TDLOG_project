# Configuration de l'API pour générer des flashcards

## 🆓 Option recommandée : Gemini (Google) - GRATUIT

### Étape 1 : Obtenir une clé API Gemini

1. Allez sur https://makersuite.google.com/app/apikey
2. Connectez-vous avec votre compte Google
3. Cliquez sur "Create API Key"
4. Copiez votre clé (elle commence par `AIza...`)

### Étape 2 : Configurer la clé dans le projet

1. Ouvrez le fichier `config.py`
2. Remplacez cette ligne:
   ```python
   GOOGLE_API_KEY = 'votre-cle-api-gemini-ici'
   ```

   Par votre vraie clé:
   ```python
   GOOGLE_API_KEY = 'AIzaSyC...'  # Votre clé ici
   ```

3. Vérifiez que le provider est bien Gemini:
   ```python
   API_PROVIDER = 'gemini'
   ```

### Étape 3 : Installer les dépendances

Sur Windows PowerShell:
```powershell
pip install -r requirements.txt
```

### Étape 4 : Lancer l'application

```powershell
python app.py
```

C'est tout ! Vous pouvez maintenant générer des flashcards gratuitement.

---

## 💰 Autres options

### Option 2 : Claude (Anthropic) - Très peu cher

**Coût** : ~$0.001 par génération de 10 flashcards

1. Créez un compte sur https://console.anthropic.com/
2. Ajoutez du crédit (minimum $5)
3. Créez une clé API
4. Dans `config.py`:
   ```python
   API_PROVIDER = 'claude'
   ANTHROPIC_API_KEY = 'sk-ant-...'  # Votre clé
   ```

### Option 3 : OpenAI - Payant

**Coût** : Plus cher que Claude

1. Créez un compte sur https://platform.openai.com/
2. Ajoutez du crédit
3. Créez une clé API
4. Dans `config.py`:
   ```python
   API_PROVIDER = 'openai'
   OPENAI_API_KEY = 'sk-proj-...'  # Votre clé
   ```

---

## ⚠️ Limites gratuites de Gemini

- **60 requêtes par minute**
- **1500 requêtes par jour**
- Largement suffisant pour un usage personnel !

Si vous dépassez ces limites, vous recevrez une erreur et devrez attendre quelques minutes.

---

## 🔒 Sécurité

**IMPORTANT** : Ne partagez jamais vos clés API publiquement !

Le fichier `config.py` est dans `.gitignore`, donc vos clés ne seront pas envoyées sur GitHub.
