#!/usr/bin/env python3
"""
Script pour exécuter les tests de la base de données

Usage:
    python run_tests.py              # Exécuter tous les tests
    python run_tests.py -v           # Mode verbeux
    python run_tests.py TestUsers    # Exécuter une classe de tests spécifique
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    # Importer le module de tests
    import test_database

    # Exécuter les tests
    success = test_database.run_tests()

    # Quitter avec le code approprié
    sys.exit(0 if success else 1)
