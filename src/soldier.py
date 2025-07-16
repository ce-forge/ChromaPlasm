class Soldier:
    """A simple data container for a single unit."""
    def __init__(self, y, x, team):
        # We will import and assign the behavior in simulation.py to avoid another import cycle
        self.behavior = None 
        self.y = y
        self.x = x
        self.team = team
        self.last_move = (0, 0)
        self.wander_target = None
        self.base_pivot = None