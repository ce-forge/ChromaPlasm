import numpy as np
import random
from src.constants import *
from numba import jit

@jit(nopython=True, fastmath=True, cache=True)
def get_next_move(y, x, heading, pheromone_grid, grid_h, grid_w, 
                  sensor_angle_rad, rotation_angle_rad, sensor_dist):
    """
    A Numba-optimized function that performs the SENSE->ROTATE->MOVE cycle.
    """
    # 1. SENSE: Check pheromones at three sensor points
    def get_scent_at(angle):
        sensor_y = int(y + sensor_dist * np.sin(angle))
        sensor_x = int(x + sensor_dist * np.cos(angle))
        if 0 <= sensor_y < grid_h and 0 <= sensor_x < grid_w:
            return pheromone_grid[sensor_y, sensor_x]
        return 0.0

    scent_forward = get_scent_at(heading)
    scent_left = get_scent_at(heading - sensor_angle_rad)
    scent_right = get_scent_at(heading + sensor_angle_rad)

    # 2. ROTATE: Adjust heading based on which sensor has the strongest scent.
    forward_bias = 1.2
    if (scent_forward * forward_bias) >= scent_left and (scent_forward * forward_bias) >= scent_right:
        heading += 0.0 # Prefer to go forward
    elif scent_left > scent_right:
        heading -= rotation_angle_rad
    elif scent_right > scent_left:
        heading += rotation_angle_rad
    else: # If scents are equal (and not zero), randomly choose a turn
        heading += random.uniform(-rotation_angle_rad, rotation_angle_rad)

    # 3. MOVE: Calculate the new position one step along the new heading
    final_y = y + np.sin(heading)
    final_x = x + np.cos(heading)

    return (int(round(final_y)), int(round(final_x))), heading


class Behavior:
    """Abstract base class for all agent AI strategies."""
    def get_next_move(self, soldier, sim):
        raise NotImplementedError

class SlimeMoldBehavior(Behavior):
    """
    This class acts as a wrapper, preparing data for the optimized Numba function.
    """
    def get_next_move(self, soldier, sim):
        params = sim.get_params_for_team(soldier.team)
        pheromone_grid = sim.red_pheromone if soldier.team == 'red' else sim.blue_pheromone
        
        sensor_angle_rad = np.deg2rad(params['sensor_angle_degrees'])
        rotation_angle_rad = np.deg2rad(params['rotation_angle_degrees'])
        
        (new_y, new_x), new_heading = get_next_move(
            soldier.y, soldier.x, soldier.heading, pheromone_grid,
            sim.grid_size[0], sim.grid_size[1],
            sensor_angle_rad, rotation_angle_rad,
            params['sensor_distance']
        )
        
        soldier.heading = new_heading
        
        return new_y, new_x