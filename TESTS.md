# Tests de la Base de Données

Ce document décrit le système de tests mis en place pour valider les fonctions de manipulation de la base de données SQLite.

## Vue d'ensemble

Le système de tests comprend **23 tests unitaires** répartis en 5 catégories :

1. **Tests des Utilisateurs** (5 tests) - Création, récupération, gestion des utilisateurs
2. **Tests des Decks** (6 tests) - Création, récupération, suppression de decks
3. **Tests des Flashcards** (5 tests) - Création, récupération, suppression en cascade
4. **Tests de Progression** (5 tests) - Mise à jour et récupération de la progression
5. **Tests d'Intégration** (2 tests) - Scénarios complets bout-en-bout

## Fichiers de tests

### `test_database.py`
Fichier principal contenant tous les tests unitaires. Utilise le module `unittest` de Python (built-in).

**Classes de tests :**
- `TestUsers` - Tests des fonctions de gestion des utilisateurs
- `TestDecks` - Tests des fonctions de gestion des decks
- `TestFlashcards` - Tests des fonctions de gestion des flashcards
- `TestUserProgress` - Tests des fonctions de progression
- `TestIntegration` - Tests d'intégration complets

### `run_tests.py`
Script simple pour exécuter les tests facilement.

### `database.py` (modifié)
Le module de base de données a été modifié pour :
- Permettre de configurer le chemin de la base de données (fonction `set_database_path()`)
- Activer les contraintes de clés étrangères SQLite (`PRAGMA foreign_keys = ON`)

## Exécution des tests

### Méthode 1 : Script run_tests.py
```bash
python run_tests.py
```

### Méthode 2 : Directement avec test_database.py
```bash
python test_database.py
```

### Méthode 3 : Avec unittest
```bash
python -m unittest test_database.py
```

### Exécuter une classe de tests spécifique
```bash
python -m unittest test_database.TestUsers
```

### Exécuter un test spécifique
```bash
python -m unittest test_database.TestUsers.test_create_user
```

## Base de données de test

Les tests utilisent une **base de données SQLite temporaire** qui est :
- Créée avant chaque test (méthode `setUp()`)
- Supprimée après chaque test (méthode `tearDown()`)
- Isolée de la base de données de production

Cela garantit que :
- Les tests n'affectent pas les données réelles
- Chaque test démarre avec une base vierge
- Les tests sont indépendants les uns des autres

## Structure des tests

### Setup et Teardown

```python
def setUp(self):
    """Exécuté avant chaque test"""
    # Créer une base de données temporaire
    self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
    set_database_path(self.test_db_path)
    init_database()

def tearDown(self):
    """Exécuté après chaque test"""
    # Supprimer la base de données temporaire
    os.close(self.test_db_fd)
    os.unlink(self.test_db_path)
```

### Exemple de test

```python
def test_create_user(self):
    """Test de création d'un utilisateur"""
    password_hash = generate_password_hash("password123")
    user_id = create_user("testuser", password_hash)

    self.assertIsNotNone(user_id)
    self.assertIsInstance(user_id, int)
    self.assertGreater(user_id, 0)
```

## Détail des tests

### 1. Tests des Utilisateurs

| Test | Description |
|------|-------------|
| `test_create_user` | Création d'un utilisateur |
| `test_create_duplicate_user` | Vérification que les doublons sont rejetés |
| `test_get_user_by_username` | Récupération d'un utilisateur par nom |
| `test_get_nonexistent_user` | Récupération d'un utilisateur inexistant |
| `test_get_all_users` | Récupération de tous les utilisateurs |

### 2. Tests des Decks

| Test | Description |
|------|-------------|
| `test_create_deck` | Création d'un deck |
| `test_create_duplicate_deck` | Les decks en double retournent l'ID existant |
| `test_get_deck_by_name` | Récupération d'un deck par nom |
| `test_get_nonexistent_deck` | Récupération d'un deck inexistant |
| `test_get_all_decks` | Récupération de tous les decks |
| `test_delete_deck` | Suppression d'un deck |

### 3. Tests des Flashcards

| Test | Description |
|------|-------------|
| `test_create_flashcard` | Création d'une flashcard |
| `test_create_duplicate_flashcard` | Les flashcards en double retournent l'ID existant |
| `test_get_flashcard_by_id` | Récupération d'une flashcard par ID |
| `test_get_flashcards_by_deck` | Récupération de toutes les flashcards d'un deck |
| `test_flashcards_deleted_with_deck` | Suppression en cascade (ON DELETE CASCADE) |

### 4. Tests de Progression

| Test | Description |
|------|-------------|
| `test_update_progress` | Mise à jour de la progression |
| `test_update_existing_progress` | Mise à jour d'une progression existante |
| `test_get_user_progress_nonexistent` | Progression inexistante retourne None |
| `test_get_all_user_progress` | Récupération de toute la progression d'un deck |
| `test_progress_isolated_between_users` | Isolation de la progression entre utilisateurs |

### 5. Tests d'Intégration

| Test | Description |
|------|-------------|
| `test_complete_user_workflow` | Workflow complet : utilisateur → deck → flashcards → progression |
| `test_multiple_users_multiple_decks` | Plusieurs utilisateurs avec plusieurs decks |

## Résultats attendus

Lors de l'exécution, vous devriez voir :

```
============================================================
DÉBUT DES TESTS DE BASE DE DONNÉES
============================================================
test_create_user (__main__.TestUsers.test_create_user)
Test de création d'un utilisateur ... ok
[...]

----------------------------------------------------------------------
Ran 23 tests in 4.432s

OK

============================================================
RÉSUMÉ DES TESTS
============================================================
Tests exécutés: 23
Succès: 23
Échecs: 0
Erreurs: 0
============================================================
```

## Bonnes pratiques

### Tests indépendants
Chaque test doit être indépendant et pouvoir s'exécuter seul :
```bash
python -m unittest test_database.TestUsers.test_create_user
```

### Assertions claires
Utiliser des assertions descriptives :
```python
self.assertEqual(user['username'], "testuser")
self.assertIsNotNone(user_id)
self.assertGreater(score, 0)
```

### Nommage explicite
Les noms de tests décrivent ce qui est testé :
- `test_create_user` - Test de création
- `test_get_nonexistent_user` - Cas d'erreur
- `test_progress_isolated_between_users` - Comportement spécifique

## Couverture des tests

Les tests couvrent toutes les fonctions principales de `database.py` :

✅ Gestion des utilisateurs
- `create_user()`
- `get_user_by_username()`
- `get_all_users()`

✅ Gestion des decks
- `create_deck()`
- `get_deck_by_name()`
- `get_all_decks()`
- `delete_deck()`

✅ Gestion des flashcards
- `create_flashcard()`
- `get_flashcard_by_id()`
- `get_flashcards_by_deck()`

✅ Gestion de la progression
- `update_progress()`
- `get_user_progress()`
- `get_all_user_progress()`

✅ Contraintes d'intégrité
- Clés uniques (utilisateurs, decks)
- Clés étrangères
- Suppression en cascade

## Ajouter de nouveaux tests

Pour ajouter un nouveau test :

1. Créer une nouvelle méthode dans une classe de tests :
```python
def test_nouvelle_fonctionnalite(self):
    """Description du test"""
    # Arrange (Préparer)
    user_id = create_user("test", "hash")

    # Act (Agir)
    result = ma_nouvelle_fonction(user_id)

    # Assert (Vérifier)
    self.assertEqual(result, valeur_attendue)
```

2. Exécuter le nouveau test :
```bash
python -m unittest test_database.TestUsers.test_nouvelle_fonctionnalite
```

## Intégration Continue

Ces tests peuvent être intégrés dans un pipeline CI/CD :

```yaml
# Exemple GitHub Actions
- name: Run tests
  run: python run_tests.py
```

## Dépendances

Les tests n'ont pas de dépendances externes :
- `unittest` - Built-in Python
- `sqlite3` - Built-in Python
- `tempfile` - Built-in Python
- `werkzeug.security` - Déjà dans requirements.txt

## Notes importantes

1. **Foreign Keys** : Les contraintes de clés étrangères sont activées via `PRAGMA foreign_keys = ON`
2. **Isolation** : Chaque test utilise une base de données temporaire unique
3. **Performance** : Les 23 tests s'exécutent en environ 4-5 secondes
4. **Couverture** : Tous les cas d'usage principaux sont couverts

## Dépannage

### Les tests échouent
1. Vérifier que toutes les dépendances sont installées : `pip install -r requirements.txt`
2. Vérifier que `database.py` n'a pas été modifié
3. Exécuter les tests en mode verbeux : `python -m unittest -v test_database.py`

### Un test spécifique échoue
1. Exécuter uniquement ce test : `python -m unittest test_database.TestUsers.test_create_user`
2. Vérifier le message d'erreur
3. Utiliser `print()` pour déboguer

### Base de données verrouillée
Si vous voyez "database is locked", cela signifie qu'une connexion n'est pas fermée correctement. Vérifier que tous les tests utilisent bien le context manager `with get_db_connection()`.
