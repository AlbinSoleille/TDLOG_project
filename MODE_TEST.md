# Mode TEST - Génération de flashcards sans API

## 🎯 Fonctionnement

Le système peut fonctionner en **deux modes** :

### 1. Mode TEST (sans clé API)
Si vous n'avez pas configuré de clé API dans `config.py`, le système génère automatiquement **des flashcards d'exemple** pour vous permettre de tester toutes les fonctionnalités :
- 10 flashcards de test sur les probabilités et statistiques
- Sauvegardées dans votre base de données comme des vraies flashcards
- Vous pouvez réviser avec le système Anki normalement

**Avantages** :
- ✅ Aucune configuration requise
- ✅ Testez le système immédiatement
- ✅ Gratuit et illimité

**Inconvénient** :
- ⚠️ Les flashcards ne correspondent pas au contenu de votre PDF (ce sont des exemples génériques)

### 2. Mode PRODUCTION (avec clé API)
Une fois que vous avez configuré une clé API (Gemini gratuit recommandé), le système :
- 📄 Extrait le texte de votre PDF
- 🤖 Génère des flashcards personnalisées basées sur le contenu
- 💾 Sauvegarde dans votre base de données

## 🚀 Comment tester ?

### Option 1 : Mode TEST (immédiat)

1. **Ne faites rien** - laissez `config.py` tel quel
2. Allez dans "Mes Cours" ou "Mes Fiches"
3. Uploadez un PDF (n'importe lequel pour tester)
4. Cliquez sur "⚡ Générer flashcards"
5. Remplissez le formulaire et cliquez sur "Générer"
6. Le message affichera : **"⚠️ MODE TEST: 10 flashcards générées avec succès"**
7. Allez dans l'onglet "Flashcards" → Votre deck apparaît !
8. Cliquez sur "Jouer ➡️" pour réviser

### Option 2 : Mode PRODUCTION (avec API Gemini GRATUITE)

1. **Obtenir une clé API Gemini** (2 minutes) :
   - Allez sur https://makersuite.google.com/app/apikey
   - Connectez-vous avec votre compte Google
   - Cliquez sur "Create API Key"
   - Copiez la clé (commence par `AIza...`)

2. **Configurer** :
   - Ouvrez `config.py`
   - Remplacez `GOOGLE_API_KEY = 'votre-cle-api-gemini-ici'`
   - Par `GOOGLE_API_KEY = 'AIza...'` (votre vraie clé)

3. **Redémarrer Flask** :
   ```bash
   # Arrêtez Flask (Ctrl+C)
   python app.py
   ```

4. **Générer des flashcards réelles** :
   - Uploadez un PDF de cours
   - Cliquez sur "⚡ Générer flashcards"
   - Les flashcards seront générées à partir du contenu du PDF !
   - Message : **"10 flashcards générées avec succès"** (sans ⚠️)

## 📊 Limites Gemini (gratuit)

- **60 requêtes / minute**
- **1500 requêtes / jour**
- Largement suffisant pour un usage personnel !

## 🐛 Débogage

Si la génération échoue, vérifiez les **logs dans le terminal Flask** :

```
🚀 GÉNÉRATION DE FLASHCARDS - Nouvelle requête
👤 User ID: 1
📄 PDF: mon_cours.pdf
📁 Catégorie: cours, Source: uploads
🎴 Nombre demandé: 10
📦 Nom du deck: statistiques_chap1
🔍 Chemin PDF: /chemin/vers/le/pdf
✅ PDF trouvé, extraction du texte...
✅ Texte extrait (12543 caractères)
🤖 Génération des flashcards avec gemini...
📡 Appel API Gemini (gemini-1.5-flash)
✅ Réponse reçue de l'API, parsing des flashcards...
✅ 10 flashcards générées avec succès
💾 Sauvegarde dans la base de données...
✅ Sauvegarde réussie! Deck: statistiques_chap1
```

Les logs vous indiquent exactement où le processus échoue si problème il y a.

## 💡 Conseils

1. **Commencez par le mode TEST** pour vérifier que tout fonctionne
2. **Configurez Gemini** quand vous êtes prêt (c'est gratuit !)
3. **Vérifiez les logs** en cas de problème
4. Si un deck existe déjà avec le même nom, les nouvelles flashcards s'ajouteront au deck existant

## ❓ FAQ

**Q: Pourquoi mes flashcards n'apparaissent pas ?**
R: Vérifiez dans les logs Flask s'il y a une erreur. Le deck devrait apparaître immédiatement dans l'onglet "Flashcards".

**Q: Puis-je utiliser le mode TEST en production ?**
R: Le mode TEST est parfait pour tester le système, mais les flashcards générées ne correspondent pas au contenu de vos PDFs. Pour des vraies flashcards personnalisées, configurez une clé API.

**Q: Combien coûte l'API ?**
R: **Gemini est GRATUIT** (60 req/min). Claude coûte ~$0.001 par génération. OpenAI est plus cher.

**Q: Puis-je changer de provider API ?**
R: Oui ! Dans `config.py`, changez `API_PROVIDER = 'gemini'` en `'claude'` ou `'openai'` et configurez la clé correspondante.
