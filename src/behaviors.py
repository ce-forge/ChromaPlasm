import numpy as np
import random
from src.constants import *

class Behavior:
    """Abstract base class for all agent AI strategies."""
    def get_next_move(self, soldier, sim):
        raise NotImplementedError

class SlimeMoldBehavior(Behavior):
    """
    A behavior where agents follow pheromone trails with a degree of randomness
    and forward-facing sensory input, creating more organic trails.
    """
    def get_next_move(self, soldier, sim):
        pheromone_grid = sim.red_pheromone if soldier.team == 'red' else sim.blue_pheromone
        y, x = soldier.y, soldier.x

        # Instead of just 8 neighbors, we sense in a cone in front of the soldier.
        # The direction is based on the soldier's last move (its momentum).
        forward_vec = soldier.last_move
        # Normalize the forward vector to get a clear direction
        norm = np.sqrt(forward_vec[0]**2 + forward_vec[1]**2)
        if norm > 0:
            forward_vec = (forward_vec[0]/norm, forward_vec[1]/norm)
        else: # If no momentum, pick a random direction
            forward_vec = (random.uniform(-1,1), random.uniform(-1,1))

        potential_moves = []
        
        # Sense 3 points: one straight ahead, and two at +/- 45 degrees
        for angle_offset in [-0.6, 0, 0.6]: # Radians for ~45 degrees
            angle = np.arctan2(forward_vec[0], forward_vec[1]) + angle_offset
            
            # Check a few pixels out in that direction
            for distance in [1, 2, 3]:
                ny = int(y + distance * np.sin(angle))
                nx = int(x + distance * np.cos(angle))
                
                if 0 <= ny < sim.grid_size[0] and 0 <= nx < sim.grid_size[1]:
                    scent = pheromone_grid[ny, nx]
                    potential_moves.append(((ny, nx), scent))

        # Also include the 8 neighbors as a fallback to prevent getting stuck
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0: continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < sim.grid_size[0] and 0 <= nx < sim.grid_size[1]:
                    potential_moves.append(((ny, nx), pheromone_grid[ny,nx]))

        if not potential_moves:
            return (y, x)

        # Sort moves by scent
        potential_moves.sort(key=lambda item: item[1], reverse=True)
        
        # Pick randomly from the top 20% of best-scented locations
        # This is the key to creating branching, exploratory paths.
        num_choices = max(1, int(len(potential_moves) * 0.2))
        best_pos = random.choice(potential_moves[:num_choices])[0]

        # Update momentum
        soldier.last_move = (best_pos[0] - y, best_pos[1] - x)
        
        return best_pos