#!/usr/bin/env python3
"""
Tests unitaires pour le module database.py

Ce fichier teste toutes les fonctions de manipulation de la base de données
en utilisant une base de données SQLite de test séparée.

Usage:
    python test_database.py
    ou
    python -m unittest test_database.py
"""

import unittest
import os
import tempfile
from werkzeug.security import generate_password_hash

# Importer toutes les fonctions à tester
import database
from database import (
    init_database, set_database_path,
    create_user, get_user_by_username, get_all_users,
    create_deck, get_deck_by_name, get_all_decks, delete_deck,
    create_flashcard, get_flashcards_by_deck, get_flashcard_by_id,
    get_user_progress, update_progress, get_all_user_progress
)


class TestDatabase(unittest.TestCase):
    """Classe de tests pour les fonctions de base de données"""

    @classmethod
    def setUpClass(cls):
        """Exécuté une fois avant tous les tests"""
        print("\n" + "="*60)
        print("DÉBUT DES TESTS DE BASE DE DONNÉES")
        print("="*60)

    @classmethod
    def tearDownClass(cls):
        """Exécuté une fois après tous les tests"""
        print("\n" + "="*60)
        print("FIN DES TESTS DE BASE DE DONNÉES")
        print("="*60 + "\n")

    def setUp(self):
        """Exécuté avant chaque test - Crée une base de données temporaire"""
        # Créer un fichier temporaire pour la base de données de test
        self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')

        # Configurer database.py pour utiliser la DB de test
        set_database_path(self.test_db_path)

        # Initialiser la base de données
        init_database()

    def tearDown(self):
        """Exécuté après chaque test - Nettoie la base de données temporaire"""
        # Fermer et supprimer le fichier temporaire
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)


class TestUsers(TestDatabase):
    """Tests pour les fonctions de gestion des utilisateurs"""

    def test_create_user(self):
        """Test de création d'un utilisateur"""
        password_hash = generate_password_hash("password123")
        user_id = create_user("testuser", password_hash)

        self.assertIsNotNone(user_id)
        self.assertIsInstance(user_id, int)
        self.assertGreater(user_id, 0)

    def test_create_duplicate_user(self):
        """Test que la création d'un utilisateur en double échoue"""
        password_hash = generate_password_hash("password123")
        create_user("testuser", password_hash)

        # Tenter de créer un utilisateur avec le même nom
        with self.assertRaises(Exception):
            create_user("testuser", password_hash)

    def test_get_user_by_username(self):
        """Test de récupération d'un utilisateur par nom"""
        password_hash = generate_password_hash("password123")
        user_id = create_user("testuser", password_hash)

        user = get_user_by_username("testuser")

        self.assertIsNotNone(user)
        self.assertEqual(user['id'], user_id)
        self.assertEqual(user['username'], "testuser")
        self.assertEqual(user['password_hash'], password_hash)

    def test_get_nonexistent_user(self):
        """Test de récupération d'un utilisateur inexistant"""
        user = get_user_by_username("nonexistent")
        self.assertIsNone(user)

    def test_get_all_users(self):
        """Test de récupération de tous les utilisateurs"""
        # Créer plusieurs utilisateurs
        create_user("user1", generate_password_hash("pass1"))
        create_user("user2", generate_password_hash("pass2"))
        create_user("user3", generate_password_hash("pass3"))

        users = get_all_users()

        self.assertEqual(len(users), 3)
        usernames = [user['username'] for user in users]
        self.assertIn("user1", usernames)
        self.assertIn("user2", usernames)
        self.assertIn("user3", usernames)


class TestDecks(TestDatabase):
    """Tests pour les fonctions de gestion des decks"""

    def test_create_deck(self):
        """Test de création d'un deck"""
        deck_id = create_deck("Test Deck")

        self.assertIsNotNone(deck_id)
        self.assertIsInstance(deck_id, int)
        self.assertGreater(deck_id, 0)

    def test_create_duplicate_deck(self):
        """Test que créer un deck en double retourne l'ID existant"""
        deck_id1 = create_deck("Test Deck")
        deck_id2 = create_deck("Test Deck")

        # Devrait retourner le même ID
        self.assertEqual(deck_id1, deck_id2)

    def test_get_deck_by_name(self):
        """Test de récupération d'un deck par nom"""
        deck_id = create_deck("Test Deck")

        deck = get_deck_by_name("Test Deck")

        self.assertIsNotNone(deck)
        self.assertEqual(deck['id'], deck_id)
        self.assertEqual(deck['name'], "Test Deck")

    def test_get_nonexistent_deck(self):
        """Test de récupération d'un deck inexistant"""
        deck = get_deck_by_name("Nonexistent Deck")
        self.assertIsNone(deck)

    def test_get_all_decks(self):
        """Test de récupération de tous les decks"""
        create_deck("Deck 1")
        create_deck("Deck 2")
        create_deck("Deck 3")

        decks = get_all_decks()

        self.assertEqual(len(decks), 3)
        deck_names = [deck['name'] for deck in decks]
        self.assertIn("Deck 1", deck_names)
        self.assertIn("Deck 2", deck_names)
        self.assertIn("Deck 3", deck_names)

    def test_delete_deck(self):
        """Test de suppression d'un deck"""
        deck_id = create_deck("Deck to Delete")

        # Vérifier que le deck existe
        deck = get_deck_by_name("Deck to Delete")
        self.assertIsNotNone(deck)

        # Supprimer le deck
        delete_deck(deck_id)

        # Vérifier que le deck n'existe plus
        deck = get_deck_by_name("Deck to Delete")
        self.assertIsNone(deck)


class TestFlashcards(TestDatabase):
    """Tests pour les fonctions de gestion des flashcards"""

    def test_create_flashcard(self):
        """Test de création d'une flashcard"""
        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        self.assertIsNotNone(flashcard_id)
        self.assertIsInstance(flashcard_id, int)
        self.assertGreater(flashcard_id, 0)

    def test_create_duplicate_flashcard(self):
        """Test que créer une flashcard en double retourne l'ID existant"""
        deck_id = create_deck("Test Deck")
        flashcard_id1 = create_flashcard(deck_id, "Question?", "Answer!")
        flashcard_id2 = create_flashcard(deck_id, "Question?", "Different Answer")

        # Devrait retourner le même ID (question unique par deck)
        self.assertEqual(flashcard_id1, flashcard_id2)

    def test_get_flashcard_by_id(self):
        """Test de récupération d'une flashcard par ID"""
        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        flashcard = get_flashcard_by_id(flashcard_id)

        self.assertIsNotNone(flashcard)
        self.assertEqual(flashcard['id'], flashcard_id)
        self.assertEqual(flashcard['question'], "Question?")
        self.assertEqual(flashcard['answer'], "Answer!")
        self.assertEqual(flashcard['deck_id'], deck_id)

    def test_get_flashcards_by_deck(self):
        """Test de récupération de toutes les flashcards d'un deck"""
        deck_id = create_deck("Test Deck")
        create_flashcard(deck_id, "Q1?", "A1")
        create_flashcard(deck_id, "Q2?", "A2")
        create_flashcard(deck_id, "Q3?", "A3")

        flashcards = get_flashcards_by_deck(deck_id)

        self.assertEqual(len(flashcards), 3)
        questions = [fc['question'] for fc in flashcards]
        self.assertIn("Q1?", questions)
        self.assertIn("Q2?", questions)
        self.assertIn("Q3?", questions)

    def test_flashcards_deleted_with_deck(self):
        """Test que les flashcards sont supprimées avec le deck (CASCADE)"""
        deck_id = create_deck("Test Deck")
        create_flashcard(deck_id, "Q1?", "A1")
        create_flashcard(deck_id, "Q2?", "A2")

        # Vérifier que les flashcards existent
        flashcards = get_flashcards_by_deck(deck_id)
        self.assertEqual(len(flashcards), 2)

        # Supprimer le deck
        delete_deck(deck_id)

        # Vérifier que les flashcards n'existent plus
        flashcards = get_flashcards_by_deck(deck_id)
        self.assertEqual(len(flashcards), 0)


class TestUserProgress(TestDatabase):
    """Tests pour les fonctions de gestion de la progression"""

    def test_update_progress(self):
        """Test de mise à jour de la progression"""
        # Créer utilisateur, deck et flashcard
        user_id = create_user("testuser", generate_password_hash("pass"))
        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        # Mettre à jour la progression
        update_progress(user_id, flashcard_id, 3)

        # Vérifier la progression
        progress = get_user_progress(user_id, flashcard_id)
        self.assertIsNotNone(progress)
        self.assertEqual(progress['score'], 3)

    def test_update_existing_progress(self):
        """Test de mise à jour d'une progression existante"""
        user_id = create_user("testuser", generate_password_hash("pass"))
        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        # Première mise à jour
        update_progress(user_id, flashcard_id, 2)

        # Deuxième mise à jour
        update_progress(user_id, flashcard_id, 4)

        # Vérifier que le score a été mis à jour
        progress = get_user_progress(user_id, flashcard_id)
        self.assertEqual(progress['score'], 4)

    def test_get_user_progress_nonexistent(self):
        """Test de récupération d'une progression inexistante"""
        user_id = create_user("testuser", generate_password_hash("pass"))
        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        progress = get_user_progress(user_id, flashcard_id)
        self.assertIsNone(progress)

    def test_get_all_user_progress(self):
        """Test de récupération de toute la progression d'un utilisateur pour un deck"""
        user_id = create_user("testuser", generate_password_hash("pass"))
        deck_id = create_deck("Test Deck")

        fc1 = create_flashcard(deck_id, "Q1?", "A1")
        fc2 = create_flashcard(deck_id, "Q2?", "A2")
        fc3 = create_flashcard(deck_id, "Q3?", "A3")

        # Mettre à jour la progression pour certaines flashcards
        update_progress(user_id, fc1, 3)
        update_progress(user_id, fc3, 5)

        # Récupérer toute la progression
        all_progress = get_all_user_progress(user_id, deck_id)

        # Devrait retourner toutes les flashcards avec leur score
        self.assertEqual(len(all_progress), 3)

        # Vérifier les scores
        progress_dict = {p['id']: p['score'] for p in all_progress}
        self.assertEqual(progress_dict[fc1], 3)
        self.assertEqual(progress_dict[fc2], 0)  # Pas encore révisée
        self.assertEqual(progress_dict[fc3], 5)

    def test_progress_isolated_between_users(self):
        """Test que la progression est isolée entre utilisateurs"""
        # Créer deux utilisateurs
        user1_id = create_user("user1", generate_password_hash("pass1"))
        user2_id = create_user("user2", generate_password_hash("pass2"))

        deck_id = create_deck("Test Deck")
        flashcard_id = create_flashcard(deck_id, "Question?", "Answer!")

        # User1 a un score de 3
        update_progress(user1_id, flashcard_id, 3)

        # User2 a un score de 5
        update_progress(user2_id, flashcard_id, 5)

        # Vérifier que chaque utilisateur a son propre score
        progress1 = get_user_progress(user1_id, flashcard_id)
        progress2 = get_user_progress(user2_id, flashcard_id)

        self.assertEqual(progress1['score'], 3)
        self.assertEqual(progress2['score'], 5)


class TestIntegration(TestDatabase):
    """Tests d'intégration - scénarios complets"""

    def test_complete_user_workflow(self):
        """Test d'un workflow complet utilisateur"""
        # 1. Créer un utilisateur
        user_id = create_user("student", generate_password_hash("password123"))
        self.assertIsNotNone(user_id)

        # 2. Créer un deck
        deck_id = create_deck("Mathématiques")
        self.assertIsNotNone(deck_id)

        # 3. Ajouter des flashcards
        fc1 = create_flashcard(deck_id, "Qu'est-ce que π?", "≈ 3.14159")
        fc2 = create_flashcard(deck_id, "2 + 2 = ?", "4")
        fc3 = create_flashcard(deck_id, "√16 = ?", "4")

        # 4. Simuler une session de révision
        update_progress(user_id, fc1, 1)  # Première révision
        update_progress(user_id, fc2, 5)  # Complètement maîtrisée
        update_progress(user_id, fc3, 2)  # En cours d'apprentissage

        # 5. Vérifier la progression
        all_progress = get_all_user_progress(user_id, deck_id)
        self.assertEqual(len(all_progress), 3)

        # 6. Vérifier les scores individuels
        progress_dict = {p['question']: p['score'] for p in all_progress}
        self.assertEqual(progress_dict["Qu'est-ce que π?"], 1)
        self.assertEqual(progress_dict["2 + 2 = ?"], 5)
        self.assertEqual(progress_dict["√16 = ?"], 2)

    def test_multiple_users_multiple_decks(self):
        """Test avec plusieurs utilisateurs et plusieurs decks"""
        # Créer des utilisateurs
        alice_id = create_user("alice", generate_password_hash("pass"))
        bob_id = create_user("bob", generate_password_hash("pass"))

        # Créer des decks
        math_deck = create_deck("Maths")
        history_deck = create_deck("Histoire")

        # Ajouter des flashcards
        math_fc = create_flashcard(math_deck, "2+2?", "4")
        history_fc = create_flashcard(history_deck, "1789?", "Révolution")

        # Alice étudie les maths
        update_progress(alice_id, math_fc, 4)

        # Bob étudie l'histoire
        update_progress(bob_id, history_fc, 3)

        # Vérifier que chacun a sa propre progression
        alice_math = get_all_user_progress(alice_id, math_deck)
        alice_history = get_all_user_progress(alice_id, history_deck)
        bob_math = get_all_user_progress(bob_id, math_deck)
        bob_history = get_all_user_progress(bob_id, history_deck)

        # Alice a progressé en maths mais pas en histoire
        self.assertEqual(alice_math[0]['score'], 4)
        self.assertEqual(alice_history[0]['score'], 0)

        # Bob a progressé en histoire mais pas en maths
        self.assertEqual(bob_math[0]['score'], 0)
        self.assertEqual(bob_history[0]['score'], 3)


def run_tests():
    """Fonction principale pour exécuter tous les tests"""
    # Créer une suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Ajouter tous les tests
    suite.addTests(loader.loadTestsFromTestCase(TestUsers))
    suite.addTests(loader.loadTestsFromTestCase(TestDecks))
    suite.addTests(loader.loadTestsFromTestCase(TestFlashcards))
    suite.addTests(loader.loadTestsFromTestCase(TestUserProgress))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Exécuter les tests avec un rapport détaillé
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Afficher un résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)
    print(f"Tests exécutés: {result.testsRun}")
    print(f"Succès: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Échecs: {len(result.failures)}")
    print(f"Erreurs: {len(result.errors)}")
    print("="*60)

    # Retourner True si tous les tests ont réussi
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
