#!/usr/bin/env python3
"""
Script qui applique toutes les migrations et crée un compte test complet
À exécuter dans votre dossier Windows : python setup_complete_database.py
"""
import sqlite3
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash
import os
import shutil

# Configuration du compte test
TEST_USERNAME = "test_user"
TEST_PASSWORD = "test123"
TEST_SECURITY_QUESTION = "Quelle est votre ville préférée ?"
TEST_SECURITY_ANSWER = "Paris"

# Données de test pour les flashcards
SAMPLE_DECKS = [
    {
        "name": "Vocabulaire Anglais",
        "flashcards": [
            {"question": "Hello", "answer": "Bonjour"},
            {"question": "Goodbye", "answer": "Au revoir"},
            {"question": "Thank you", "answer": "Merci"},
            {"question": "Please", "answer": "S'il vous plaît"},
            {"question": "Sorry", "answer": "Désolé"},
            {"question": "Yes", "answer": "Oui"},
            {"question": "No", "answer": "Non"},
            {"question": "Water", "answer": "Eau"},
            {"question": "Food", "answer": "Nourriture"},
            {"question": "Friend", "answer": "Ami"},
        ]
    },
    {
        "name": "Mathématiques",
        "flashcards": [
            {"question": "Qu'est-ce qu'une dérivée ?", "answer": "Une mesure de la variation instantanée d'une fonction"},
            {"question": "Formule de Pythagore", "answer": "a² + b² = c²"},
            {"question": "Qu'est-ce qu'une intégrale ?", "answer": "L'aire sous la courbe d'une fonction"},
            {"question": "Sin(0)", "answer": "0"},
            {"question": "Cos(0)", "answer": "1"},
            {"question": "Formule d'Euler", "answer": "e^(iπ) + 1 = 0"},
            {"question": "Qu'est-ce qu'une limite ?", "answer": "La valeur vers laquelle tend une fonction"},
            {"question": "Dérivée de x²", "answer": "2x"},
        ]
    },
    {
        "name": "Histoire de France",
        "flashcards": [
            {"question": "Année de la Révolution Française", "answer": "1789"},
            {"question": "Premier Empire de Napoléon", "answer": "1804-1814"},
            {"question": "Louis XIV, le Roi Soleil", "answer": "Règne de 1643 à 1715"},
            {"question": "Bataille de Waterloo", "answer": "1815"},
            {"question": "Guerre de Cent Ans", "answer": "1337-1453"},
            {"question": "Jeanne d'Arc", "answer": "Héroïne française (1412-1431)"},
        ]
    },
    {
        "name": "Python Programming",
        "flashcards": [
            {"question": "Comment créer une liste vide ?", "answer": "[] ou list()"},
            {"question": "Comment créer un dictionnaire ?", "answer": "{} ou dict()"},
            {"question": "Qu'est-ce qu'une list comprehension ?", "answer": "[x for x in range(10)]"},
            {"question": "Comment ouvrir un fichier ?", "answer": "with open('file.txt', 'r') as f:"},
            {"question": "Qu'est-ce qu'un décorateur ?", "answer": "Une fonction qui modifie le comportement d'une autre fonction"},
            {"question": "Comment gérer les exceptions ?", "answer": "try/except/finally"},
            {"question": "Qu'est-ce que __init__ ?", "answer": "Le constructeur d'une classe"},
            {"question": "Comment importer un module ?", "answer": "import module ou from module import fonction"},
            {"question": "Qu'est-ce qu'une lambda ?", "answer": "Une fonction anonyme : lambda x: x + 1"},
            {"question": "Comment créer une classe ?", "answer": "class MyClass: ..."},
        ]
    },
    {
        "name": "Géographie",
        "flashcards": [
            {"question": "Capitale de la France", "answer": "Paris"},
            {"question": "Capitale de l'Allemagne", "answer": "Berlin"},
            {"question": "Capitale du Japon", "answer": "Tokyo"},
            {"question": "Plus long fleuve du monde", "answer": "Le Nil (ou l'Amazone selon les mesures)"},
            {"question": "Plus haut sommet du monde", "answer": "Mont Everest (8849m)"},
            {"question": "Océan le plus grand", "answer": "Océan Pacifique"},
        ]
    }
]


def check_column_exists(cursor, table_name, column_name):
    """Vérifie si une colonne existe dans une table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def check_table_exists(cursor, table_name):
    """Vérifie si une table existe"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def apply_migrations(conn):
    """Applique toutes les migrations nécessaires"""
    cursor = conn.cursor()
    print("\n🔧 Application des migrations...")

    # Migration 1: Questions de sécurité
    if not check_column_exists(cursor, 'users', 'security_question'):
        print("  📝 Ajout des questions de sécurité...")
        cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
        cursor.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT")
        print("    ✅ Colonnes security_question et security_answer_hash ajoutées")
    else:
        print("  ✓ Questions de sécurité déjà présentes")

    # Migration 2: Système de streaks
    if not check_column_exists(cursor, 'users', 'streak_count'):
        print("  🔥 Ajout du système de streaks...")
        cursor.execute("ALTER TABLE users ADD COLUMN streak_count INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN last_streak_date DATE")
        cursor.execute("ALTER TABLE users ADD COLUMN show_in_leaderboard INTEGER DEFAULT 1")
        print("    ✅ Colonnes de streaks ajoutées")
    else:
        print("  ✓ Système de streaks déjà présent")

    # Table daily_activity
    if not check_table_exists(cursor, 'daily_activity'):
        print("  📅 Création de la table daily_activity...")
        cursor.execute("""
            CREATE TABLE daily_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                cards_reviewed INTEGER DEFAULT 0,
                cards_due_completed INTEGER,
                all_cards_completed INTEGER,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_activity_user ON daily_activity(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_activity_date ON daily_activity(date)")
        print("    ✅ Table daily_activity créée")
    else:
        print("  ✓ Table daily_activity déjà présente")

    # Migration 3: Système de dossiers
    if not check_table_exists(cursor, 'folders'):
        print("  📁 Création de la table folders...")
        cursor.execute("""
            CREATE TABLE folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_user ON folders(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)")
        print("    ✅ Table folders créée")
    else:
        print("  ✓ Table folders déjà présente")

    # Ajout de folder_id à decks
    if not check_column_exists(cursor, 'decks', 'folder_id'):
        print("  📦 Ajout de folder_id à la table decks...")
        cursor.execute("ALTER TABLE decks ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL")
        print("    ✅ Colonne folder_id ajoutée")
    else:
        print("  ✓ Colonne folder_id déjà présente")

    conn.commit()
    print("✅ Toutes les migrations appliquées avec succès!\n")


def create_test_account(conn):
    """Crée un compte test avec des données complètes"""
    cursor = conn.cursor()

    try:
        # 1. Supprimer l'utilisateur test s'il existe déjà
        print("🗑️  Suppression de l'ancien compte test s'il existe...")
        cursor.execute("DELETE FROM users WHERE username = ?", (TEST_USERNAME,))

        # 2. Créer l'utilisateur
        print(f"👤 Création de l'utilisateur '{TEST_USERNAME}'...")
        password_hash = generate_password_hash(TEST_PASSWORD)
        security_answer_hash = generate_password_hash(TEST_SECURITY_ANSWER.lower())

        cursor.execute("""
            INSERT INTO users (username, password_hash, security_question, security_answer_hash,
                             streak_count, last_streak_date, show_in_leaderboard, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (TEST_USERNAME, password_hash, TEST_SECURITY_QUESTION, security_answer_hash,
              15, datetime.now().date(), 1, datetime.now()))

        user_id = cursor.lastrowid
        print(f"✅ Utilisateur créé avec ID: {user_id}")

        # 3. Créer les decks et flashcards
        print("\n📚 Création des decks et flashcards...")
        flashcard_ids = []

        for deck_data in SAMPLE_DECKS:
            # Créer le deck
            cursor.execute("""
                INSERT INTO decks (name, user_id, created_at)
                VALUES (?, ?, ?)
            """, (deck_data["name"], user_id, datetime.now()))

            deck_id = cursor.lastrowid
            print(f"  📖 Deck '{deck_data['name']}' créé")

            # Créer les flashcards
            for card in deck_data["flashcards"]:
                cursor.execute("""
                    INSERT INTO flashcards (deck_id, question, answer, created_at)
                    VALUES (?, ?, ?, ?)
                """, (deck_id, card["question"], card["answer"], datetime.now()))

                flashcard_ids.append(cursor.lastrowid)

            print(f"    ✅ {len(deck_data['flashcards'])} flashcards créées")

        print(f"\n📊 Total: {len(flashcard_ids)} flashcards créées")

        # 4. Simuler des révisions avec l'algorithme Anki
        print("\n🔄 Simulation des révisions...")
        now = datetime.now()

        # Catégoriser les cartes pour une progression réaliste
        num_cards = len(flashcard_ids)

        # 30% de cartes bien apprises (mature, faciles)
        mature_cards = flashcard_ids[:int(num_cards * 0.3)]

        # 40% de cartes en apprentissage (interval moyen)
        learning_cards = flashcard_ids[int(num_cards * 0.3):int(num_cards * 0.7)]

        # 30% de cartes nouvelles ou difficiles
        new_cards = flashcard_ids[int(num_cards * 0.7):]

        # Cartes matures : bon intervalle, bonnes stats
        for card_id in mature_cards:
            ease_factor = random.uniform(2.3, 2.8)
            interval = random.randint(7, 30)
            repetitions = random.randint(5, 15)
            last_reviewed = now - timedelta(days=random.randint(0, 5))
            due_date = last_reviewed + timedelta(days=interval)

            cursor.execute("""
                INSERT INTO user_progress
                (user_id, flashcard_id, ease_factor, interval, due_date,
                 step, is_learning, repetitions, last_reviewed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, card_id, ease_factor, interval, due_date,
                  0, 0, repetitions, last_reviewed))

        # Cartes en apprentissage : interval court-moyen
        for card_id in learning_cards:
            ease_factor = 2.5
            interval = random.randint(1, 6)
            repetitions = random.randint(2, 5)
            is_learning = random.choice([0, 1])
            last_reviewed = now - timedelta(days=random.randint(0, 2))
            due_date = last_reviewed + timedelta(days=interval)

            cursor.execute("""
                INSERT INTO user_progress
                (user_id, flashcard_id, ease_factor, interval, due_date,
                 step, is_learning, repetitions, last_reviewed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, card_id, ease_factor, interval, due_date,
                  random.randint(0, 1), is_learning, repetitions, last_reviewed))

        # Nouvelles cartes : la moitié vient d'être commencée
        for card_id in new_cards[len(new_cards)//2:]:
            ease_factor = 2.5
            interval = 0
            last_reviewed = now - timedelta(minutes=random.randint(1, 60))
            due_date = now + timedelta(minutes=1)

            cursor.execute("""
                INSERT INTO user_progress
                (user_id, flashcard_id, ease_factor, interval, due_date,
                 step, is_learning, repetitions, last_reviewed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, card_id, ease_factor, interval, due_date,
                  random.randint(0, 1), 1, random.randint(0, 2), last_reviewed))

        print(f"  ✅ Progression créée pour {len(mature_cards) + len(learning_cards) + len(new_cards)//2} cartes")

        # 5. Créer l'activité quotidienne pour le streak
        print("\n🔥 Création de l'historique de streak (15 jours)...")
        for i in range(15, 0, -1):
            date = (datetime.now() - timedelta(days=i)).date()
            cards_reviewed = random.randint(10, 30)

            cursor.execute("""
                INSERT INTO daily_activity
                (user_id, date, cards_reviewed, cards_due_completed, all_cards_completed)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, date, cards_reviewed, cards_reviewed, 0))

        # Ajouter l'activité d'aujourd'hui
        cursor.execute("""
            INSERT INTO daily_activity
            (user_id, date, cards_reviewed, cards_due_completed, all_cards_completed)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, datetime.now().date(), 25, 25, 0))

        print("  ✅ Streak de 15 jours créé")

        # 6. Créer un dossier exemple
        print("\n📁 Création d'un dossier...")
        cursor.execute("""
            INSERT INTO folders (name, user_id, created_at)
            VALUES (?, ?, ?)
        """, ("Langues", user_id, datetime.now()))

        folder_id = cursor.lastrowid

        # Déplacer le deck "Vocabulaire Anglais" dans ce dossier
        cursor.execute("""
            UPDATE decks
            SET folder_id = ?
            WHERE name = ? AND user_id = ?
        """, (folder_id, "Vocabulaire Anglais", user_id))

        print("  ✅ Dossier 'Langues' créé avec le deck Anglais")

        conn.commit()
        print("\n" + "="*60)
        print("✨ COMPTE TEST CRÉÉ AVEC SUCCÈS ! ✨")
        print("="*60)
        print(f"\n📝 Identifiants de connexion :")
        print(f"   Username: {TEST_USERNAME}")
        print(f"   Password: {TEST_PASSWORD}")
        print(f"\n🔐 Question de sécurité : {TEST_SECURITY_QUESTION}")
        print(f"   Réponse : {TEST_SECURITY_ANSWER}")
        print(f"\n📊 Statistiques :")
        print(f"   • {len(SAMPLE_DECKS)} decks créés")
        print(f"   • {len(flashcard_ids)} flashcards au total")
        print(f"   • Environ {len(mature_cards)} cartes bien apprises")
        print(f"   • Environ {len(learning_cards)} cartes en apprentissage")
        print(f"   • Environ {len(new_cards)//2} cartes nouvelles à découvrir")
        print(f"   • 🔥 Streak de 15 jours")
        print(f"   • 📁 1 dossier d'organisation")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Erreur lors de la création du compte : {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False


def main():
    """Point d'entrée principal"""
    db_path = 'flashcards.db'

    if not os.path.exists(db_path):
        print(f"❌ Erreur: La base de données '{db_path}' n'existe pas!")
        print(f"   Assurez-vous d'exécuter ce script dans le dossier contenant flashcards.db")
        return

    # Créer une sauvegarde
    backup_path = f"flashcards_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    print(f"💾 Création d'une sauvegarde: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Connexion à la base de données
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')

    try:
        # Appliquer les migrations
        apply_migrations(conn)

        # Créer le compte test
        create_test_account(conn)

        print("\n🎉 Configuration terminée avec succès!")
        print("\n⚠️  N'oubliez pas de REDÉMARRER votre serveur Flask!\n")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
