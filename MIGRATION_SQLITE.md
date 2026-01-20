# Migration vers SQLite

## Changements apportés

L'application a été migrée d'un système de stockage JSON vers une base de données SQLite pour une meilleure performance et une gestion plus robuste des données.

### Avant (JSON)
- `users.json` - Stockait les utilisateurs et mots de passe
- `user_progress.json` - Stockait la progression de chaque utilisateur
- Fichiers CSV dans `flashcards_data/` - Stockaient les flashcards

### Après (SQLite)
- `flashcards.db` - Base de données SQLite unique contenant toutes les données
- Structure avec 4 tables :
  - `users` - Utilisateurs et leurs mots de passe hashés
  - `decks` - Decks de flashcards
  - `flashcards` - Questions et réponses
  - `user_progress` - Progression de chaque utilisateur pour chaque flashcard

## Avantages de SQLite

1. **Performance** : Requêtes SQL optimisées et indexées
2. **Intégrité** : Contraintes de clés étrangères et transactions ACID
3. **Scalabilité** : Gestion plus efficace d'un grand nombre d'utilisateurs et de flashcards
4. **Concurrent** : Meilleure gestion des accès simultanés
5. **Structure** : Schéma de données clairement défini

## Scripts fournis

### `database.py`
Module contenant toutes les fonctions d'accès à la base de données :
- Gestion des utilisateurs
- Gestion des decks
- Gestion des flashcards
- Gestion de la progression

### `migrate_to_sqlite.py`
Script de migration pour transférer les données JSON existantes vers SQLite :
```bash
python migrate_to_sqlite.py
```

Ce script :
1. Crée la base de données SQLite
2. Sauvegarde les fichiers JSON dans `json_backup/`
3. Migre les utilisateurs
4. Migre les flashcards depuis les CSV
5. Migre la progression des utilisateurs

## Installation et démarrage

### Première installation (nouveau projet)
```bash
# Installer les dépendances
pip install -r requirements.txt

# La base de données sera créée automatiquement au premier lancement
python app.py
```

### Migration depuis JSON (projet existant)
```bash
# 1. Exécuter le script de migration
python migrate_to_sqlite.py

# 2. Lancer l'application
python app.py
```

## Structure de la base de données

### Table `users`
| Colonne        | Type      | Description                  |
|----------------|-----------|------------------------------|
| id             | INTEGER   | Clé primaire                 |
| username       | TEXT      | Nom d'utilisateur (unique)   |
| password_hash  | TEXT      | Mot de passe hashé           |
| created_at     | TIMESTAMP | Date de création             |

### Table `decks`
| Colonne    | Type      | Description      |
|------------|-----------|------------------|
| id         | INTEGER   | Clé primaire     |
| name       | TEXT      | Nom du deck      |
| created_at | TIMESTAMP | Date de création |

### Table `flashcards`
| Colonne    | Type      | Description               |
|------------|-----------|---------------------------|
| id         | INTEGER   | Clé primaire              |
| deck_id    | INTEGER   | Référence au deck         |
| question   | TEXT      | Question de la flashcard  |
| answer     | TEXT      | Réponse de la flashcard   |
| created_at | TIMESTAMP | Date de création          |

### Table `user_progress`
| Colonne       | Type      | Description                    |
|---------------|-----------|--------------------------------|
| id            | INTEGER   | Clé primaire                   |
| user_id       | INTEGER   | Référence à l'utilisateur      |
| flashcard_id  | INTEGER   | Référence à la flashcard       |
| score         | INTEGER   | Score (0-5)                    |
| last_reviewed | TIMESTAMP | Dernière révision              |

## Notes importantes

- La base de données `flashcards.db` est exclue du contrôle de version (`.gitignore`)
- Les fichiers JSON originaux sont sauvegardés dans `json_backup/` lors de la migration
- Le dossier `flashcards_data/` est conservé pour la rétrocompatibilité
- Le système d'algorithme de répétition espacée reste inchangé

## Migration vers MongoDB (optionnel)

Si vous souhaitez utiliser MongoDB au lieu de SQLite, il faudrait :
1. Créer un nouveau module `mongodb.py` similaire à `database.py`
2. Adapter les fonctions pour utiliser PyMongo
3. Modifier les imports dans `app.py`

MongoDB serait préférable pour :
- Applications avec des millions d'utilisateurs
- Besoins de réplication et haute disponibilité
- Schéma de données très flexible

SQLite est suffisant pour :
- Applications avec < 100,000 utilisateurs
- Déploiement simple
- Environnement de développement/test
