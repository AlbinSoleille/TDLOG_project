"""
Algorithme de répétition espacée SM-2 (SuperMemo 2)
Utilisé par Anki pour optimiser la mémorisation

Références:
- https://www.supermemo.com/en/archives1990-2015/english/ol/sm2
- https://faqs.ankiweb.net/what-spaced-repetition-algorithm.html
"""

from datetime import datetime, timedelta


# Configuration par défaut (similaire à Anki)
DEFAULT_CONFIG = {
    'learning_steps': [1, 10],  # Minutes: 1min, 10min
    'graduating_interval': 1,    # 1 jour pour passer en révision
    'easy_interval': 4,          # 4 jours si "Facile" dès le début
    'starting_ease': 2.5,        # Facteur de facilité initial
    'easy_bonus': 1.3,           # Bonus pour réponse "Facile"
    'interval_modifier': 1.0,    # Modificateur d'intervalle global
    'max_interval': 36500,       # Intervalle max (100 ans)
    'min_ease': 1.3,             # Ease minimum
}


class AnkiCard:
    """
    Représente l'état d'une carte selon l'algorithme Anki
    """
    def __init__(self, ease_factor=None, interval=0, due_date=None,
                 step=0, is_learning=True, repetitions=0):
        self.ease_factor = ease_factor or DEFAULT_CONFIG['starting_ease']
        self.interval = interval  # En jours
        self.due_date = due_date or datetime.now()
        self.step = step  # Étape actuelle dans learning_steps
        self.is_learning = is_learning
        self.repetitions = repetitions

    def to_dict(self):
        """Convertit en dictionnaire pour stockage DB"""
        return {
            'ease_factor': self.ease_factor,
            'interval': self.interval,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'step': self.step,
            'is_learning': 1 if self.is_learning else 0,
            'repetitions': self.repetitions
        }

    @classmethod
    def from_dict(cls, data):
        """Crée depuis un dictionnaire DB"""
        return cls(
            ease_factor=data.get('ease_factor'),
            interval=data.get('interval', 0),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
            step=data.get('step', 0),
            is_learning=bool(data.get('is_learning', 1)),
            repetitions=data.get('repetitions', 0)
        )


def calculate_next_review(card: AnkiCard, rating: int, config: dict = None) -> AnkiCard:
    """
    Calcule le prochain intervalle de révision selon l'algorithme SM-2

    Args:
        card: État actuel de la carte
        rating: Note de l'utilisateur
                0 = Again (Recommencer)
                1 = Hard (Difficile)
                2 = Good (Bon)
                3 = Easy (Facile)
        config: Configuration (utilise DEFAULT_CONFIG si None)

    Returns:
        AnkiCard avec les nouveaux paramètres
    """
    if config is None:
        config = DEFAULT_CONFIG

    new_card = AnkiCard(
        ease_factor=card.ease_factor,
        interval=card.interval,
        step=card.step,
        is_learning=card.is_learning,
        repetitions=card.repetitions
    )

    # Carte en phase d'apprentissage
    if new_card.is_learning:
        if rating == 0:  # Again
            # Recommencer l'apprentissage
            new_card.step = 0
            new_card.due_date = datetime.now() + timedelta(minutes=config['learning_steps'][0])

        elif rating == 1:  # Hard
            # Répéter l'étape actuelle
            minutes = config['learning_steps'][new_card.step]
            new_card.due_date = datetime.now() + timedelta(minutes=minutes)

        elif rating == 2:  # Good
            # Passer à l'étape suivante
            if new_card.step < len(config['learning_steps']) - 1:
                new_card.step += 1
                minutes = config['learning_steps'][new_card.step]
                new_card.due_date = datetime.now() + timedelta(minutes=minutes)
            else:
                # Graduation: passer en révision
                new_card.is_learning = False
                new_card.interval = config['graduating_interval']
                new_card.due_date = datetime.now() + timedelta(days=new_card.interval)
                new_card.repetitions = 1

        elif rating == 3:  # Easy
            # Graduation immédiate avec intervalle "facile"
            new_card.is_learning = False
            new_card.interval = config['easy_interval']
            new_card.due_date = datetime.now() + timedelta(days=new_card.interval)
            new_card.repetitions = 1

    # Carte en phase de révision
    else:
        if rating == 0:  # Again
            # Retour en apprentissage
            new_card.is_learning = True
            new_card.step = 0
            new_card.due_date = datetime.now() + timedelta(minutes=config['learning_steps'][0])
            new_card.repetitions = 0
            # Réduire l'ease factor
            new_card.ease_factor = max(config['min_ease'], new_card.ease_factor - 0.2)

        elif rating == 1:  # Hard
            # Intervalle réduit
            new_card.interval = int(new_card.interval * 1.2)
            new_card.due_date = datetime.now() + timedelta(days=new_card.interval)
            # Réduire légèrement l'ease factor
            new_card.ease_factor = max(config['min_ease'], new_card.ease_factor - 0.15)
            new_card.repetitions += 1

        elif rating == 2:  # Good
            # Intervalle normal selon SM-2
            if new_card.repetitions == 0:
                new_card.interval = 1
            elif new_card.repetitions == 1:
                new_card.interval = 6
            else:
                new_card.interval = int(new_card.interval * new_card.ease_factor * config['interval_modifier'])

            new_card.interval = min(new_card.interval, config['max_interval'])
            new_card.due_date = datetime.now() + timedelta(days=new_card.interval)
            new_card.repetitions += 1

        elif rating == 3:  # Easy
            # Intervalle augmenté avec bonus
            if new_card.repetitions == 0:
                new_card.interval = config['easy_interval']
            else:
                new_card.interval = int(new_card.interval * new_card.ease_factor * config['easy_bonus'] * config['interval_modifier'])

            new_card.interval = min(new_card.interval, config['max_interval'])
            new_card.due_date = datetime.now() + timedelta(days=new_card.interval)
            # Augmenter l'ease factor
            new_card.ease_factor += 0.15
            new_card.repetitions += 1

    return new_card


def get_cards_to_review(cards_with_progress, current_date=None):
    """
    Filtre les cartes qui doivent être révisées

    Args:
        cards_with_progress: Liste de tuples (flashcard, progress_data)
        current_date: Date actuelle (utilise datetime.now() si None)

    Returns:
        Liste des cartes à réviser, triées par priorité
    """
    if current_date is None:
        current_date = datetime.now()

    cards_to_review = []

    for flashcard, progress in cards_with_progress:
        if progress is None:
            # Nouvelle carte
            cards_to_review.append((flashcard, None, 0))  # Priorité 0 (nouveau)
        else:
            due_date = datetime.fromisoformat(progress['due_date']) if progress.get('due_date') else None
            if due_date and due_date <= current_date:
                # Carte en retard
                delay = (current_date - due_date).days
                cards_to_review.append((flashcard, progress, delay))

    # Trier par priorité: nouveau d'abord, puis par retard
    cards_to_review.sort(key=lambda x: (x[1] is not None, -x[2]))

    return [card[0] for card in cards_to_review]


def get_statistics(cards_with_progress):
    """
    Calcule des statistiques sur l'état des cartes

    Returns:
        dict avec new, learning, review counts
    """
    stats = {
        'new': 0,
        'learning': 0,
        'review': 0,
        'due_today': 0,
        'total': len(cards_with_progress)
    }

    now = datetime.now()

    for flashcard, progress in cards_with_progress:
        if progress is None:
            stats['new'] += 1
        elif progress.get('is_learning'):
            stats['learning'] += 1
            if progress.get('due_date'):
                due = datetime.fromisoformat(progress['due_date'])
                if due <= now:
                    stats['due_today'] += 1
        else:
            stats['review'] += 1
            if progress.get('due_date'):
                due = datetime.fromisoformat(progress['due_date'])
                if due <= now:
                    stats['due_today'] += 1

    return stats


if __name__ == '__main__':
    # Test de l'algorithme
    print("=== Test de l'algorithme Anki SM-2 ===\n")

    # Nouvelle carte
    card = AnkiCard()
    print(f"Nouvelle carte: {card.to_dict()}")

    # Simulation d'une session
    print("\n--- Session d'apprentissage ---")
    print("1. Première révision - Good")
    card = calculate_next_review(card, 2)  # Good
    print(f"   Résultat: step={card.step}, due_date={card.due_date}, is_learning={card.is_learning}")

    print("2. Deuxième révision - Good")
    card = calculate_next_review(card, 2)  # Good
    print(f"   Résultat: interval={card.interval} jours, is_learning={card.is_learning}")

    print("3. Première révision (review) - Good")
    card = calculate_next_review(card, 2)  # Good
    print(f"   Résultat: interval={card.interval} jours, ease={card.ease_factor:.2f}")

    print("4. Deuxième révision (review) - Good")
    card = calculate_next_review(card, 2)  # Good
    print(f"   Résultat: interval={card.interval} jours, ease={card.ease_factor:.2f}")

    print("5. Oubliée - Again")
    card = calculate_next_review(card, 0)  # Again
    print(f"   Résultat: is_learning={card.is_learning}, ease={card.ease_factor:.2f}")

    print("\n✅ Tests terminés")
