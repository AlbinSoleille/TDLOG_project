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

        # Table des dossiers pour organiser les decks
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

        # Table d'historique quotidien pour les streaks
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

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_folders_user
            ON folders(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_folders_parent
            ON folders(parent_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_activity_user
            ON daily_activity(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_activity_date
            ON daily_activity(date)
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

def get_user_flashcard_counts(user_id):
    """Récupère les compteurs de cartes nouvelles/à réapprendre/à réviser pour un utilisateur"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Cartes nouvelles (jamais étudiées)
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as new_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ? AND up.id IS NULL
        ''', (user_id, user_id))
        new_count = cursor.fetchone()['new_cards']

        # Cartes à réapprendre (en apprentissage et dues)
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as relearn_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ?
            AND up.is_learning = 1
            AND up.due_date <= datetime('now')
        ''', (user_id, user_id))
        relearn_count = cursor.fetchone()['relearn_cards']

        # Cartes à réviser (matures et dues)
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as review_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ?
            AND up.is_learning = 0
            AND up.due_date <= datetime('now')
        ''', (user_id, user_id))
        review_count = cursor.fetchone()['review_cards']

        return {
            'new': new_count,
            'relearn': relearn_count,
            'review': review_count
        }


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


# --- FONCTIONS POUR LES DOSSIERS ---

def create_folder(user_id, name, parent_id=None):
    """Crée un nouveau dossier pour organiser les decks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO folders (user_id, name, parent_id) VALUES (?, ?, ?)',
            (user_id, name, parent_id)
        )
        return cursor.lastrowid


def get_user_folders(user_id, parent_id=None):
    """Récupère les dossiers d'un utilisateur (optionnellement filtrés par parent)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if parent_id is None:
            # Récupérer les dossiers racine (sans parent)
            cursor.execute(
                'SELECT * FROM folders WHERE user_id = ? AND parent_id IS NULL ORDER BY name',
                (user_id,)
            )
        else:
            # Récupérer les sous-dossiers d'un dossier parent
            cursor.execute(
                'SELECT * FROM folders WHERE user_id = ? AND parent_id = ? ORDER BY name',
                (user_id, parent_id)
            )
        return cursor.fetchall()


def get_folder_by_id(folder_id):
    """Récupère un dossier par son ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM folders WHERE id = ?', (folder_id,))
        return cursor.fetchone()


def rename_folder(folder_id, new_name):
    """Renomme un dossier"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE folders SET name = ? WHERE id = ?', (new_name, folder_id))


def delete_folder(folder_id):
    """Supprime un dossier et tous ses sous-dossiers (CASCADE)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))


def move_deck_to_folder(deck_id, folder_id):
    """Déplace un deck dans un dossier"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE decks SET folder_id = ? WHERE id = ?', (folder_id, deck_id))


def get_decks_in_folder(user_id, folder_id=None):
    """Récupère les decks dans un dossier (ou à la racine si folder_id=None)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if folder_id is None:
            cursor.execute(
                'SELECT * FROM decks WHERE user_id = ? AND (folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders)) ORDER BY created_at DESC',
                (user_id,)
            )
        else:
            cursor.execute(
                'SELECT * FROM decks WHERE user_id = ? AND folder_id = ? ORDER BY created_at DESC',
                (user_id, folder_id)
            )
        return cursor.fetchall()


def get_folder_statistics(user_id, folder_id):
    """Récupère les statistiques d'un dossier (nouvelles/réapprendre/réviser)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Cartes nouvelles dans ce dossier
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as new_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ? AND d.folder_id = ? AND up.id IS NULL
        ''', (user_id, user_id, folder_id))
        new_count = cursor.fetchone()['new_cards']

        # Cartes à réapprendre dans ce dossier
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as relearn_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ? AND d.folder_id = ?
            AND up.is_learning = 1
            AND up.due_date <= datetime('now')
        ''', (user_id, user_id, folder_id))
        relearn_count = cursor.fetchone()['relearn_cards']

        # Cartes à réviser dans ce dossier
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as review_cards
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ? AND d.folder_id = ?
            AND up.is_learning = 0
            AND up.due_date <= datetime('now')
        ''', (user_id, user_id, folder_id))
        review_count = cursor.fetchone()['review_cards']

        return {
            'new': new_count,
            'relearn': relearn_count,
            'review': review_count
        }


def get_deck_statistics(user_id, deck_id):
    """Récupère les statistiques d'un deck (nouvelles/réapprendre/réviser)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Cartes nouvelles dans ce deck
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as new_cards
            FROM flashcards f
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE f.deck_id = ? AND up.id IS NULL
        ''', (user_id, deck_id))
        new_count = cursor.fetchone()['new_cards']

        # Cartes à réapprendre dans ce deck
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as relearn_cards
            FROM flashcards f
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE f.deck_id = ?
            AND up.is_learning = 1
            AND up.due_date <= datetime('now')
        ''', (user_id, deck_id))
        relearn_count = cursor.fetchone()['relearn_cards']

        # Cartes à réviser dans ce deck
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as review_cards
            FROM flashcards f
            INNER JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE f.deck_id = ?
            AND up.is_learning = 0
            AND up.due_date <= datetime('now')
        ''', (user_id, deck_id))
        review_count = cursor.fetchone()['review_cards']

        return {
            'new': new_count,
            'relearn': relearn_count,
            'review': review_count
        }


# --- FONCTIONS POUR LES STREAKS ---

def update_daily_activity(user_id, cards_reviewed, all_completed):
    """Met à jour l'activité quotidienne de l'utilisateur"""
    from datetime import datetime, date

    with get_db_connection() as conn:
        cursor = conn.cursor()
        today = date.today()

        # Récupérer le nombre de cartes dues aujourd'hui
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) as cards_due
            FROM flashcards f
            INNER JOIN decks d ON f.deck_id = d.id
            LEFT JOIN user_progress up ON f.id = up.flashcard_id AND up.user_id = ?
            WHERE d.user_id = ?
            AND (up.due_date IS NULL OR up.due_date <= datetime('now'))
        ''', (user_id, user_id))
        cards_due = cursor.fetchone()['cards_due']

        # Mettre à jour ou créer l'entrée du jour
        cursor.execute('''
            INSERT INTO daily_activity
                (user_id, date, cards_reviewed, cards_due_completed, all_cards_completed)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date)
            DO UPDATE SET
                cards_reviewed = cards_reviewed + ?,
                cards_due_completed = ?,
                all_cards_completed = ?
        ''', (user_id, today, cards_reviewed, cards_due, all_completed,
              cards_reviewed, cards_due, all_completed))

        # Mettre à jour le streak si toutes les cartes sont terminées
        if all_completed:
            update_streak(user_id)


def update_streak(user_id):
    """Met à jour le streak de l'utilisateur"""
    from datetime import datetime, date, timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()
        today = date.today()

        # Récupérer les infos actuelles de streak
        cursor.execute(
            'SELECT streak_count, last_streak_date FROM users WHERE id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        current_streak = result['streak_count'] or 0
        last_date = result['last_streak_date']

        # Si c'est le premier streak ou si last_date est None
        if not last_date:
            cursor.execute(
                'UPDATE users SET streak_count = 1, last_streak_date = ? WHERE id = ?',
                (today, user_id)
            )
            return 1

        # Convertir last_date en objet date
        if isinstance(last_date, str):
            last_date = datetime.strptime(last_date, '%Y-%m-%d').date()

        # Si c'était hier, on incrémente
        if last_date == today - timedelta(days=1):
            new_streak = current_streak + 1
            cursor.execute(
                'UPDATE users SET streak_count = ?, last_streak_date = ? WHERE id = ?',
                (new_streak, today, user_id)
            )
            return new_streak
        # Si c'est aujourd'hui, on garde le même
        elif last_date == today:
            return current_streak
        # Sinon, le streak est cassé, on recommence à 1
        else:
            cursor.execute(
                'UPDATE users SET streak_count = 1, last_streak_date = ? WHERE id = ?',
                (today, user_id)
            )
            return 1


def get_user_streak(user_id):
    """Récupère le streak actuel de l'utilisateur"""
    from datetime import date, timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT streak_count, last_streak_date FROM users WHERE id = ?',
            (user_id,)
        )
        result = cursor.fetchone()

        if not result:
            return 0

        streak = result['streak_count'] or 0
        last_date = result['last_streak_date']

        # Si pas de date ou si la dernière date est trop ancienne (> 1 jour), streak = 0
        if not last_date:
            return 0

        from datetime import datetime
        if isinstance(last_date, str):
            last_date = datetime.strptime(last_date, '%Y-%m-%d').date()

        # Si la dernière date n'est pas aujourd'hui ou hier, le streak est cassé
        today = date.today()
        if last_date < today - timedelta(days=1):
            # Réinitialiser le streak
            cursor.execute(
                'UPDATE users SET streak_count = 0 WHERE id = ?',
                (user_id,)
            )
            return 0

        return streak


def get_yearly_activity(user_id, year=None):
    """Récupère l'activité de l'utilisateur pour une année complète"""
    from datetime import datetime, date

    if year is None:
        year = date.today().year

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Récupérer toutes les activités de l'année
        cursor.execute('''
            SELECT date, cards_reviewed, all_cards_completed
            FROM daily_activity
            WHERE user_id = ?
            AND strftime('%Y', date) = ?
            ORDER BY date
        ''', (user_id, str(year)))

        activities = cursor.fetchall()

        # Créer un dictionnaire pour un accès facile
        activity_dict = {}
        max_cards = 1  # Pour éviter la division par zéro

        for activity in activities:
            activity_dict[activity['date']] = {
                'cards_reviewed': activity['cards_reviewed'],
                'all_completed': activity['all_cards_completed']
            }
            if activity['cards_reviewed'] > max_cards:
                max_cards = activity['cards_reviewed']

        return activity_dict, max_cards


def get_leaderboard():
    """Récupère le classement des utilisateurs"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Calculer le score (cartes révisées totales × streak)
        cursor.execute('''
            SELECT
                u.id,
                u.username,
                u.streak_count,
                COALESCE(SUM(da.cards_reviewed), 0) as total_cards,
                (COALESCE(SUM(da.cards_reviewed), 0) * COALESCE(u.streak_count, 0)) as score
            FROM users u
            LEFT JOIN daily_activity da ON u.id = da.user_id
            WHERE u.show_in_leaderboard = 1
            GROUP BY u.id, u.username, u.streak_count
            ORDER BY score DESC, u.streak_count DESC
            LIMIT 100
        ''')

        return cursor.fetchall()


def toggle_leaderboard_visibility(user_id):
    """Active/désactive la visibilité de l'utilisateur dans le classement"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Récupérer l'état actuel
        cursor.execute(
            'SELECT show_in_leaderboard FROM users WHERE id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        current = result['show_in_leaderboard'] if result else 1

        # Inverser
        new_value = 0 if current else 1
        cursor.execute(
            'UPDATE users SET show_in_leaderboard = ? WHERE id = ?',
            (new_value, user_id)
        )

        return new_value


def can_see_leaderboard(user_id):
    """Vérifie si l'utilisateur peut voir le classement"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT show_in_leaderboard FROM users WHERE id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        return result['show_in_leaderboard'] == 1 if result else False


def get_show_in_leaderboard(user_id):
    """Récupère l'état de visibilité de l'utilisateur dans le classement"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT show_in_leaderboard FROM users WHERE id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        return result['show_in_leaderboard'] if result else 0


if __name__ == '__main__':
    # Initialiser la base de données
    init_database()
    print("✅ Base de données créée avec succès!")
