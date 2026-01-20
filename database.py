import sqlite3
import os
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'flashcards.db')

# Variable globale pour permettre de changer la DB (utilisé pour les tests)
_current_db_path = DB_PATH


def set_database_path(path):
    """Change le chemin de la base de données (utilisé pour les tests)"""
    global _current_db_path
    _current_db_path = path


def get_database_path():
    """Retourne le chemin actuel de la base de données"""
    return _current_db_path


@contextmanager
def get_db_connection():
    """Context manager pour gérer les connexions à la base de données"""
    conn = sqlite3.connect(_current_db_path)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
    # Activer les contraintes de clés étrangères (nécessaire pour CASCADE)
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialise la base de données avec les tables nécessaires"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Table des utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table des decks de flashcards
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table des flashcards
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
                UNIQUE(deck_id, question)
            )
        ''')

        # Table de progression des utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                flashcard_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                last_reviewed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE,
                UNIQUE(user_id, flashcard_id)
            )
        ''')

        # Index pour améliorer les performances
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flashcards_deck
            ON flashcards(deck_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_progress_user
            ON user_progress(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_progress_flashcard
            ON user_progress(flashcard_id)
        ''')

        print("✅ Base de données initialisée avec succès")


# --- FONCTIONS POUR LES UTILISATEURS ---

def create_user(username, password_hash):
    """Crée un nouvel utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        return cursor.lastrowid


def get_user_by_username(username):
    """Récupère un utilisateur par son nom"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cursor.fetchone()


def get_all_users():
    """Récupère tous les utilisateurs"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()


# --- FONCTIONS POUR LES DECKS ---

def create_deck(name):
    """Crée un nouveau deck"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO decks (name) VALUES (?)', (name,))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Le deck existe déjà
            cursor.execute('SELECT id FROM decks WHERE name = ?', (name,))
            return cursor.fetchone()[0]


def get_deck_by_name(name):
    """Récupère un deck par son nom"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM decks WHERE name = ?', (name,))
        return cursor.fetchone()


def get_all_decks():
    """Récupère tous les decks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM decks ORDER BY name')
        return cursor.fetchall()


def delete_deck(deck_id):
    """Supprime un deck et toutes ses flashcards"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM decks WHERE id = ?', (deck_id,))


# --- FONCTIONS POUR LES FLASHCARDS ---

def create_flashcard(deck_id, question, answer):
    """Crée une nouvelle flashcard"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO flashcards (deck_id, question, answer) VALUES (?, ?, ?)',
                (deck_id, question, answer)
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # La flashcard existe déjà dans ce deck
            cursor.execute(
                'SELECT id FROM flashcards WHERE deck_id = ? AND question = ?',
                (deck_id, question)
            )
            result = cursor.fetchone()
            return result[0] if result else None


def get_flashcards_by_deck(deck_id):
    """Récupère toutes les flashcards d'un deck"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM flashcards WHERE deck_id = ? ORDER BY id',
            (deck_id,)
        )
        return cursor.fetchall()


def get_flashcard_by_id(flashcard_id):
    """Récupère une flashcard par son ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM flashcards WHERE id = ?', (flashcard_id,))
        return cursor.fetchone()


# --- FONCTIONS POUR LA PROGRESSION ---

def get_user_progress(user_id, flashcard_id):
    """Récupère la progression d'un utilisateur pour une flashcard"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM user_progress WHERE user_id = ? AND flashcard_id = ?',
            (user_id, flashcard_id)
        )
        return cursor.fetchone()


def update_progress(user_id, flashcard_id, ease_factor, interval, due_date,
                   step, is_learning, repetitions):
    """Met à jour ou crée la progression d'un utilisateur (système Anki)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_progress
                (user_id, flashcard_id, ease_factor, interval, due_date,
                 step, is_learning, repetitions, last_reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, flashcard_id)
            DO UPDATE SET
                ease_factor = ?,
                interval = ?,
                due_date = ?,
                step = ?,
                is_learning = ?,
                repetitions = ?,
                last_reviewed = CURRENT_TIMESTAMP
        ''', (user_id, flashcard_id, ease_factor, interval, due_date,
              step, is_learning, repetitions,
              ease_factor, interval, due_date, step, is_learning, repetitions))


def get_all_user_progress(user_id, deck_id):
    """Récupère toute la progression d'un utilisateur pour un deck (système Anki)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                f.id, f.question, f.answer,
                up.ease_factor, up.interval, up.due_date,
                up.step, up.is_learning, up.repetitions
            FROM flashcards f
            LEFT JOIN user_progress up
                ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE f.deck_id = ?
            ORDER BY
                CASE
                    WHEN up.due_date IS NULL THEN 0
                    WHEN up.due_date <= datetime('now') THEN 1
                    ELSE 2
                END,
                up.due_date
        ''', (user_id, deck_id))
        return cursor.fetchall()


if __name__ == '__main__':
    # Initialiser la base de données
    init_database()
    print("✅ Base de données créée avec succès!")
