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

        # --- NEW: Steer-ahead and Random Sensing ---
        # Get momentum vector
        forward_vec = soldier.last_move
        if forward_vec == (0,0): # If no momentum, pick random direction
            forward_vec = (random.uniform(-1,1), random.uniform(-1,1))
        
        # Normalize
        norm = np.sqrt(forward_vec[0]**2 + forward_vec[1]**2)
        if norm > 0:
            forward_vec = (forward_vec[0]/norm, forward_vec[1]/norm)

        potential_moves = []
        
        # 1. Main sensor: steer towards this point ahead
        steer_distance = 5
        steer_y = int(y + forward_vec[0] * steer_distance)
        steer_x = int(x + forward_vec[1] * steer_distance)

        # 2. Random sensor: also check a random point nearby to encourage exploration
        rand_y = y + random.randint(-8, 8)
        rand_x = x + random.randint(-8, 8)

        # 3. Sample pheromones at these points and neighbors
        for sy, sx in [(steer_y, steer_x), (rand_y, rand_x)]:
            # Check 3x3 area around the sensor point
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    ny, nx = sy + dy, sx + dx
                    if 0 <= ny < sim.grid_size[0] and 0 <= nx < sim.grid_size[1]:
                        potential_moves.append(((ny,nx), pheromone_grid[ny,nx]))

        if not potential_moves: return (y,x)

        # Find the single best position from all sensed points
        potential_moves.sort(key=lambda item: item[1], reverse=True)
        best_pos = potential_moves[0][0]

        # Move towards the best sensed position, but only one step at a time
        final_move_y = y + np.sign(best_pos[0] - y)
        final_move_x = x + np.sign(best_pos[1] - x)

        # Update momentum
        soldier.last_move = (final_move_y - y, final_move_x - x)

        return (final_move_y, final_move_x)