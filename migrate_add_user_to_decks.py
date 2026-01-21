#!/usr/bin/env python3
"""
Script de migration pour ajouter la colonne user_id à la table decks
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = 'flashcards.db'

def migrate():
    """Ajoute la colonne user_id à la table decks"""

    # Backup de la base de données
    backup_path = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if os.path.exists(DB_PATH):
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup créé: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(decks)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'user_id' in columns:
            print("⚠️  La colonne user_id existe déjà dans la table decks")
            return

        print("Ajout de la colonne user_id à la table decks...")

        # Ajouter la colonne user_id (nullable pour les decks existants)
        cursor.execute('ALTER TABLE decks ADD COLUMN user_id INTEGER')

        # Récupérer le premier utilisateur pour l'attribuer aux decks existants
        cursor.execute('SELECT id FROM users LIMIT 1')
        first_user = cursor.fetchone()

        if first_user:
            user_id = first_user[0]
            # Attribuer tous les decks existants au premier utilisateur
            cursor.execute('UPDATE decks SET user_id = ? WHERE user_id IS NULL', (user_id,))
            print(f"✅ Decks existants attribués à l'utilisateur {user_id}")

        conn.commit()
        print("✅ Migration réussie!")

        # Afficher les statistiques
        cursor.execute('SELECT COUNT(*) FROM decks')
        nb_decks = cursor.fetchone()[0]
        print(f"📊 Nombre total de decks: {nb_decks}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur lors de la migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
