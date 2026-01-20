#!/usr/bin/env python3
"""
Script de migration des données JSON vers SQLite
"""

import json
import os
import csv
from database import (
    init_database, create_user, create_deck, create_flashcard,
    update_progress, get_user_by_username, get_deck_by_name
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FLASHCARDS_DIR = os.path.join(BASE_DIR, 'flashcards_data')


def migrate_users():
    """Migre les utilisateurs depuis users.json"""
    users_path = os.path.join(BASE_DIR, 'users.json')

    if not os.path.exists(users_path):
        print("⚠️  Aucun fichier users.json trouvé")
        return {}

    print("\n📥 Migration des utilisateurs...")
    with open(users_path, 'r', encoding='utf-8') as f:
        users_data = json.load(f)

    user_mapping = {}  # username -> user_id
    for username, password_hash in users_data.items():
        try:
            user_id = create_user(username, password_hash)
            user_mapping[username] = user_id
            print(f"  ✅ Utilisateur migré: {username} (ID: {user_id})")
        except Exception as e:
            print(f"  ❌ Erreur pour {username}: {e}")

    print(f"✅ {len(user_mapping)} utilisateurs migrés")
    return user_mapping


def migrate_flashcards():
    """Migre les flashcards depuis les fichiers CSV"""
    if not os.path.exists(FLASHCARDS_DIR):
        print("⚠️  Aucun dossier flashcards_data trouvé")
        return {}

    print("\n📥 Migration des flashcards...")
    csv_files = [f for f in os.listdir(FLASHCARDS_DIR) if f.endswith('.csv')]

    if not csv_files:
        print("⚠️  Aucun fichier CSV trouvé")
        return {}

    deck_mapping = {}  # deck_name -> {deck_id, flashcard_mapping}

    for csv_file in csv_files:
        print(f"\n  📂 Migration du deck: {csv_file}")

        # Créer le deck
        deck_id = create_deck(csv_file)
        flashcard_mapping = {}  # question -> flashcard_id

        # Lire et migrer les flashcards
        csv_path = os.path.join(FLASHCARDS_DIR, csv_file)
        try:
            with open(csv_path, 'r', encoding='utf-8', newline='') as csvfile:
                # Détection du séparateur
                sample = csvfile.read(1024)
                csvfile.seek(0)

                delimiter = ';' if ';' in sample else ','
                reader = csv.reader(csvfile, delimiter=delimiter)

                count = 0
                for row in reader:
                    if len(row) >= 2:
                        question = row[0].strip()
                        answer = row[1].strip()

                        if question and answer:
                            flashcard_id = create_flashcard(deck_id, question, answer)
                            flashcard_mapping[question] = flashcard_id
                            count += 1

                print(f"    ✅ {count} flashcards migrées")
                deck_mapping[csv_file] = {
                    'deck_id': deck_id,
                    'flashcard_mapping': flashcard_mapping
                }

        except Exception as e:
            print(f"    ❌ Erreur lors de la migration de {csv_file}: {e}")

    print(f"\n✅ {len(deck_mapping)} decks migrés")
    return deck_mapping


def migrate_progress(user_mapping, deck_mapping):
    """Migre la progression des utilisateurs depuis user_progress.json"""
    progress_path = os.path.join(BASE_DIR, 'user_progress.json')

    if not os.path.exists(progress_path):
        print("⚠️  Aucun fichier user_progress.json trouvé")
        return

    print("\n📥 Migration de la progression...")
    with open(progress_path, 'r', encoding='utf-8') as f:
        progress_data = json.load(f)

    total_migrated = 0
    for username, user_decks in progress_data.items():
        if username not in user_mapping:
            print(f"  ⚠️  Utilisateur {username} non trouvé, progression ignorée")
            continue

        user_id = user_mapping[username]

        for deck_name, deck_progress in user_decks.items():
            if deck_name not in deck_mapping:
                print(f"  ⚠️  Deck {deck_name} non trouvé, progression ignorée")
                continue

            flashcard_mapping = deck_mapping[deck_name]['flashcard_mapping']

            for question, score in deck_progress.items():
                if question in flashcard_mapping:
                    flashcard_id = flashcard_mapping[question]
                    try:
                        update_progress(user_id, flashcard_id, score)
                        total_migrated += 1
                    except Exception as e:
                        print(f"  ❌ Erreur pour {username}/{deck_name}/{question[:30]}...: {e}")

    print(f"✅ {total_migrated} entrées de progression migrées")


def backup_json_files():
    """Crée une sauvegarde des fichiers JSON"""
    print("\n💾 Sauvegarde des fichiers JSON...")

    files_to_backup = ['users.json', 'user_progress.json']
    backup_dir = os.path.join(BASE_DIR, 'json_backup')
    os.makedirs(backup_dir, exist_ok=True)

    for filename in files_to_backup:
        source = os.path.join(BASE_DIR, filename)
        if os.path.exists(source):
            dest = os.path.join(backup_dir, filename)
            import shutil
            shutil.copy2(source, dest)
            print(f"  ✅ Sauvegarde: {filename}")

    print(f"✅ Sauvegarde créée dans {backup_dir}")


def main():
    print("=" * 60)
    print("🔄 MIGRATION JSON → SQLite")
    print("=" * 60)

    # Initialiser la base de données
    print("\n📊 Initialisation de la base de données...")
    init_database()

    # Sauvegarder les fichiers JSON
    backup_json_files()

    # Migrer les données
    user_mapping = migrate_users()
    deck_mapping = migrate_flashcards()
    migrate_progress(user_mapping, deck_mapping)

    print("\n" + "=" * 60)
    print("✅ MIGRATION TERMINÉE AVEC SUCCÈS!")
    print("=" * 60)
    print(f"\n📊 Résumé:")
    print(f"  - Utilisateurs: {len(user_mapping)}")
    print(f"  - Decks: {len(deck_mapping)}")
    print(f"\n💡 Les fichiers JSON ont été sauvegardés dans json_backup/")
    print(f"💡 La base de données SQLite est: flashcards.db")


if __name__ == '__main__':
    main()
