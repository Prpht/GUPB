

class BaseStrategy():

    def __init__(self):
        pass

    def explore(self):
        """
            Fancy name for wandering around...

            Store information about seen parts of the map and go towards the unexplored?
        """
        pass

    def go_to_menhir(self):
        """
            Go to menhir when the mist is approaching
        """

    
class PassiveStrategy(BaseStrategy):
    
    def __init__(self):
        super().__init__()

    def hide(self):
        """
            Analyze the map for safe spots and go to the nearest one 
        """


class AggresiveStrategy(BaseStrategy):

    def __init__(self):
        super().__init__()

    def fight(self):
        """
            Find the target and eliminate it (or run if will die)
        """