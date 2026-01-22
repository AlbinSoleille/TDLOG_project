import sqlite3
import os
import shutil
from datetime import datetime

# Chemin de la base de données
DB_PATH = 'flashcards.db'

def migrate_add_folders():
    """Ajoute le système de dossiers (folders) à la base de données"""

    # Créer une sauvegarde
    backup_path = f'flashcards_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Sauvegarde créée: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Créer la table folders
        print("📁 Création de la table folders...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Ajouter la colonne folder_id à la table decks si elle n'existe pas
        print("📦 Ajout de la colonne folder_id à la table decks...")
        cursor.execute("PRAGMA table_info(decks)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'folder_id' not in columns:
            cursor.execute('''
                ALTER TABLE decks
                ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL
            ''')
            print("  ✅ Colonne folder_id ajoutée à decks")
        else:
            print("  ℹ️  Colonne folder_id déjà présente dans decks")

        # Créer des index pour améliorer les performances
        print("🔍 Création des index...")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_folders_user
            ON folders(user_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_folders_parent
            ON folders(parent_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_decks_folder
            ON decks(folder_id)
        ''')

        conn.commit()
        print("\n✅ Migration terminée avec succès!")
        print("\nNouvelles tables et colonnes:")
        print("  - Table 'folders' créée")
        print("  - Colonne 'folder_id' ajoutée à 'decks'")
        print("\n⚠️  N'oubliez pas de redémarrer votre application Flask!")

    except sqlite3.Error as e:
        print(f"\n❌ Erreur lors de la migration: {e}")
        conn.rollback()
        print(f"💾 Vous pouvez restaurer la sauvegarde depuis: {backup_path}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 Début de la migration pour ajouter le système de dossiers...\n")
    migrate_add_folders()
