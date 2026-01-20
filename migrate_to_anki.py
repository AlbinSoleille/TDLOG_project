#!/usr/bin/env python3
"""
Script de migration pour passer au système de répétition espacée Anki (SM-2)

Ce script:
1. Ajoute les nouveaux champs à la table user_progress
2. Migre les données existantes (score -> état Anki)
3. Crée une sauvegarde de la base avant migration
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'flashcards.db')


def backup_database():
    """Crée une sauvegarde de la base de données"""
    if not os.path.exists(DB_PATH):
        print("⚠️  Base de données non trouvée")
        return False

    backup_path = DB_PATH + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Sauvegarde créée: {backup_path}")
    return True


def migrate_schema():
    """Migre le schéma de la base de données"""
    print("\n📊 Migration du schéma...")

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    try:
        # Créer une nouvelle table avec les champs Anki
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                flashcard_id INTEGER NOT NULL,
                ease_factor REAL DEFAULT 2.5,
                interval INTEGER DEFAULT 0,
                due_date TEXT,
                step INTEGER DEFAULT 0,
                is_learning INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                last_reviewed TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE,
                UNIQUE(user_id, flashcard_id)
            )
        ''')

        # Copier les données existantes avec conversion
        cursor.execute('''
            INSERT INTO user_progress_new
                (id, user_id, flashcard_id, ease_factor, interval, due_date,
                 step, is_learning, repetitions, last_reviewed)
            SELECT
                id,
                user_id,
                flashcard_id,
                CASE
                    WHEN score >= 4 THEN 2.7
                    WHEN score >= 2 THEN 2.5
                    ELSE 2.3
                END as ease_factor,
                CASE
                    WHEN score >= 5 THEN 30
                    WHEN score >= 4 THEN 7
                    WHEN score >= 3 THEN 3
                    WHEN score >= 2 THEN 1
                    ELSE 0
                END as interval,
                CASE
                    WHEN score >= 2 THEN datetime('now', '+' ||
                        CASE
                            WHEN score >= 5 THEN 30
                            WHEN score >= 4 THEN 7
                            WHEN score >= 3 THEN 3
                            ELSE 1
                        END || ' days')
                    ELSE datetime('now', '+1 minutes')
                END as due_date,
                0 as step,
                CASE WHEN score < 2 THEN 1 ELSE 0 END as is_learning,
                CASE WHEN score >= 2 THEN score - 1 ELSE 0 END as repetitions,
                last_reviewed
            FROM user_progress
        ''')

        # Supprimer l'ancienne table et renommer la nouvelle
        cursor.execute('DROP TABLE user_progress')
        cursor.execute('ALTER TABLE user_progress_new RENAME TO user_progress')

        # Recréer les index
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_progress_user
            ON user_progress(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_progress_flashcard
            ON user_progress(flashcard_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_progress_due
            ON user_progress(due_date)
        ''')

        conn.commit()
        print("✅ Schéma migré avec succès")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la migration: {e}")
        return False

    finally:
        conn.close()


def verify_migration():
    """Vérifie que la migration s'est bien passée"""
    print("\n🔍 Vérification de la migration...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Vérifier que les nouveaux champs existent
        cursor.execute("PRAGMA table_info(user_progress)")
        columns = [col[1] for col in cursor.fetchall()]

        required_columns = ['ease_factor', 'interval', 'due_date', 'step',
                          'is_learning', 'repetitions']

        missing_columns = [col for col in required_columns if col not in columns]

        if missing_columns:
            print(f"❌ Colonnes manquantes: {missing_columns}")
            return False

        # Compter les enregistrements
        cursor.execute("SELECT COUNT(*) FROM user_progress")
        count = cursor.fetchone()[0]
        print(f"✅ {count} enregistrements de progression trouvés")

        # Afficher quelques exemples
        cursor.execute("""
            SELECT ease_factor, interval, is_learning, repetitions
            FROM user_progress
            LIMIT 3
        """)
        examples = cursor.fetchall()

        if examples:
            print("\n📋 Exemples de données migrées:")
            for ex in examples:
                print(f"   ease={ex[0]:.2f}, interval={ex[1]}j, learning={ex[2]}, reps={ex[3]}")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")
        return False

    finally:
        conn.close()


def main():
    print("=" * 60)
    print("🔄 MIGRATION VERS LE SYSTÈME ANKI (SM-2)")
    print("=" * 60)

    # Vérifier que la base existe
    if not os.path.exists(DB_PATH):
        print("\n❌ Base de données non trouvée!")
        print(f"   Attendu: {DB_PATH}")
        return False

    # Sauvegarder
    if not backup_database():
        print("\n❌ Impossible de créer la sauvegarde")
        return False

    # Migrer
    if not migrate_schema():
        print("\n❌ Migration échouée")
        return False

    # Vérifier
    if not verify_migration():
        print("\n❌ Vérification échouée")
        return False

    print("\n" + "=" * 60)
    print("✅ MIGRATION TERMINÉE AVEC SUCCÈS!")
    print("=" * 60)
    print("\n💡 Nouveau système:")
    print("   - Algorithme SM-2 (utilisé par Anki)")
    print("   - Intervalles adaptatifs basés sur la performance")
    print("   - 4 boutons: Again, Hard, Good, Easy")
    print("   - Optimisation de la mémorisation à long terme")
    print("\n💡 Les anciennes données ont été converties:")
    print("   - Score 0-1 → En apprentissage")
    print("   - Score 2-3 → Intervalle court (1-3 jours)")
    print("   - Score 4 → Intervalle moyen (7 jours)")
    print("   - Score 5 → Intervalle long (30 jours)")

    return True


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
