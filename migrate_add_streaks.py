import sqlite3
import os
import shutil
from datetime import datetime

# Chemin de la base de données
DB_PATH = 'flashcards.db'

def migrate_add_streaks():
    """Ajoute le système de streaks et le classement à la base de données"""

    # Créer une sauvegarde
    backup_path = f'flashcards_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Sauvegarde créée: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Ajouter les colonnes de streaks à la table users
        print("🔥 Ajout des colonnes de streaks...")
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'streak_count' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN streak_count INTEGER DEFAULT 0')
            print("  ✅ Colonne streak_count ajoutée")
        else:
            print("  ℹ️  Colonne streak_count déjà présente")

        if 'last_streak_date' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN last_streak_date DATE')
            print("  ✅ Colonne last_streak_date ajoutée")
        else:
            print("  ℹ️  Colonne last_streak_date déjà présente")

        if 'show_in_leaderboard' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN show_in_leaderboard INTEGER DEFAULT 1')
            print("  ✅ Colonne show_in_leaderboard ajoutée")
        else:
            print("  ℹ️  Colonne show_in_leaderboard déjà présente")

        # Créer la table d'historique des révisions quotidiennes
        print("📅 Création de la table daily_activity...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                cards_reviewed INTEGER DEFAULT 0,
                cards_due_completed INTEGER DEFAULT 0,
                all_cards_completed INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, date)
            )
        ''')
        print("  ✅ Table daily_activity créée")

        # Créer des index pour améliorer les performances
        print("🔍 Création des index...")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_activity_user
            ON daily_activity(user_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_activity_date
            ON daily_activity(date)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_leaderboard
            ON users(show_in_leaderboard)
        ''')

        conn.commit()
        print("\n✅ Migration terminée avec succès!")
        print("\nNouvelles fonctionnalités:")
        print("  - Système de streaks (séries de jours consécutifs)")
        print("  - Table 'daily_activity' pour l'historique quotidien")
        print("  - Colonne 'show_in_leaderboard' pour le classement")
        print("\n⚠️  N'oubliez pas de redémarrer votre application Flask!")

    except sqlite3.Error as e:
        print(f"\n❌ Erreur lors de la migration: {e}")
        conn.rollback()
        print(f"💾 Vous pouvez restaurer la sauvegarde depuis: {backup_path}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 Début de la migration pour ajouter le système de streaks...\n")
    migrate_add_streaks()
