import numpy as np
from src.behaviors import SlimeMoldBehavior

class Soldier:
    """
    Represents a single agent in the simulation.
    It now uses a heading angle for movement, matching the diagram.
    """
    def __init__(self, y_start, x_start, team):
        self.y = y_start
        self.x = x_start
        self.team = team
        self.health = 100
        
        # Heading is a random angle in radians (0 to 2*PI)
        self.heading = np.random.uniform(0, 2 * np.pi)
        
        # Every soldier uses the same behavior logic.
        self.behavior = SlimeMoldBehavior()
        
    def is_alive(self):
        return self.health > 0