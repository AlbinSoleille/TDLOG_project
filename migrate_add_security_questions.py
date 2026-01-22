#!/usr/bin/env python3
"""
Migration: Ajouter les colonnes pour les questions de sécurité
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'flashcards.db')

def migrate():
    """Ajoute les colonnes security_question et security_answer_hash à la table users"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Vérifier si les colonnes existent déjà
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        # Ajouter security_question si elle n'existe pas
        if 'security_question' not in columns:
            cursor.execute('''
                ALTER TABLE users
                ADD COLUMN security_question TEXT
            ''')
            print("✅ Colonne 'security_question' ajoutée")
        else:
            print("ℹ️  Colonne 'security_question' existe déjà")

        # Ajouter security_answer_hash si elle n'existe pas
        if 'security_answer_hash' not in columns:
            cursor.execute('''
                ALTER TABLE users
                ADD COLUMN security_answer_hash TEXT
            ''')
            print("✅ Colonne 'security_answer_hash' ajoutée")
        else:
            print("ℹ️  Colonne 'security_answer_hash' existe déjà")

        conn.commit()
        print("✅ Migration terminée avec succès!")

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
