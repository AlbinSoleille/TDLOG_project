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
                name TEXT NOT NULL,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

        # Table des prompts personnalisés par utilisateur
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                custom_prompt TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

def create_deck(name, user_id=None):
    """Crée un nouveau deck pour un utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO decks (name, user_id) VALUES (?, ?)', (name, user_id))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Le deck existe déjà, vérifier s'il appartient à cet utilisateur
            if user_id:
                cursor.execute('SELECT id FROM decks WHERE name = ? AND user_id = ?', (name, user_id))
            else:
                cursor.execute('SELECT id FROM decks WHERE name = ?', (name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            # Si le deck existe mais appartient à un autre utilisateur, créer un nom unique
            cursor.execute('INSERT INTO decks (name, user_id) VALUES (?, ?)',
                         (f"{name}_{user_id}", user_id))
            return cursor.lastrowid


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


def get_user_decks(user_id):
    """Récupère tous les decks d'un utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM decks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
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


# --- FONCTIONS POUR LES PROMPTS PERSONNALISÉS ---

def get_user_prompt(user_id):
    """Récupère le prompt personnalisé d'un utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT custom_prompt FROM user_prompts WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result['custom_prompt'] if result else None


def save_user_prompt(user_id, custom_prompt):
    """Sauvegarde ou met à jour le prompt personnalisé d'un utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_prompts (user_id, custom_prompt, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                custom_prompt = excluded.custom_prompt,
                updated_at = datetime('now')
        ''', (user_id, custom_prompt))


# --- FONCTIONS POUR LES STATISTIQUES ---

def get_user_statistics(user_id):
    """Récupère les statistiques complètes d'un utilisateur (style Anki)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Statistiques globales
        cursor.execute('''
            SELECT
                COUNT(DISTINCT d.id) as total_decks,
                COUNT(DISTINCT f.id) as total_cards,
                COUNT(DISTINCT CASE WHEN up.id IS NOT NULL THEN f.id END) as cards_studied,
                COUNT(DISTINCT CASE WHEN up.is_learning = 1 THEN f.id END) as cards_learning,
                COUNT(DISTINCT CASE WHEN up.is_learning = 0 THEN f.id END) as cards_mature,
                COUNT(DISTINCT CASE WHEN up.due_date <= datetime('now') THEN f.id END) as cards_due
            FROM decks d
            LEFT JOIN flashcards f ON d.id = f.deck_id
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ?
        ''', (user_id, user_id))
        global_stats = cursor.fetchone()

        # Cartes révisées aujourd'hui
        cursor.execute('''
            SELECT COUNT(DISTINCT flashcard_id) as cards_today
            FROM user_progress
            WHERE user_id = ?
            AND date(last_reviewed) = date('now')
        ''', (user_id,))
        today_stats = cursor.fetchone()

        # Statistiques par deck
        cursor.execute('''
            SELECT
                d.name as deck_name,
                COUNT(DISTINCT f.id) as total,
                COUNT(DISTINCT CASE WHEN up.id IS NOT NULL THEN f.id END) as studied,
                COUNT(DISTINCT CASE WHEN up.due_date <= datetime('now') THEN f.id END) as due,
                COUNT(DISTINCT CASE WHEN up.is_learning = 1 THEN f.id END) as learning,
                COUNT(DISTINCT CASE WHEN up.is_learning = 0 THEN f.id END) as mature
            FROM decks d
            LEFT JOIN flashcards f ON d.id = f.deck_id
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ?
            GROUP BY d.id, d.name
            ORDER BY d.name
        ''', (user_id, user_id))
        deck_stats = cursor.fetchall()

        # Activité des 30 derniers jours
        cursor.execute('''
            SELECT
                date(last_reviewed) as date,
                COUNT(DISTINCT flashcard_id) as cards_reviewed
            FROM user_progress
            WHERE user_id = ?
            AND date(last_reviewed) >= date('now', '-30 days')
            GROUP BY date(last_reviewed)
            ORDER BY date(last_reviewed)
        ''', (user_id,))
        activity_stats = cursor.fetchall()

        return {
            'global': global_stats,
            'today': today_stats,
            'decks': deck_stats,
            'activity': activity_stats
        }


if __name__ == '__main__':
    # Initialiser la base de données
    init_database()
    print("✅ Base de données créée avec succès!")
