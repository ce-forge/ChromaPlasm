import numpy as np
from scipy.ndimage import gaussian_filter
from numba import jit, prange

from src.constants import *
from src.base import Base
from src.behaviors import get_next_move

@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def _numba_simulation_step(agent_count, agent_positions, agent_headings, agent_teams, agent_health,
                             render_grid, object_grid, red_pheromone, blue_pheromone,
                             grid_h, grid_w,
                             r_sens_angle, r_rot_angle, r_sens_dist, r_deposit,
                             b_sens_angle, b_rot_angle, b_sens_dist, b_deposit):

    for i in prange(agent_count):
        if agent_health[i] <= 0:
            continue

        y, x = agent_positions[i]
        heading = agent_headings[i]
        team_id = agent_teams[i]

        if team_id == 0:
            pheromone_grid = red_pheromone
            sensor_angle_rad, rotation_angle_rad, sensor_dist = r_sens_angle, r_rot_angle, r_sens_dist
        else:
            pheromone_grid = blue_pheromone
            sensor_angle_rad, rotation_angle_rad, sensor_dist = b_sens_angle, b_rot_angle, b_sens_dist

        (ny, nx), new_heading = get_next_move(y, x, heading, pheromone_grid, grid_h, grid_w,
                                              sensor_angle_rad, rotation_angle_rad, sensor_dist)

        agent_headings[i] = new_heading
        ny = max(0, min(ny, grid_h - 1))
        nx = max(0, min(nx, grid_w - 1))

        target_cell_id = render_grid[ny, nx]
        enemy_soldier_id = BLUE_SOLDIER if team_id == 0 else RED_SOLDIER
        enemy_armor_id = BLUE_BASE_ARMOR if team_id == 0 else RED_BASE_ARMOR

        if target_cell_id == enemy_soldier_id:
            agent_health[i] = 0
            other_soldier_idx = object_grid[ny, nx]
            if other_soldier_idx != -1:
                agent_health[other_soldier_idx] = 0
        elif target_cell_id == enemy_armor_id:
            agent_health[i] = 0
            render_grid[ny, nx] = EMPTY
        else:
            agent_positions[i] = [ny, nx]

    for i in prange(agent_count):
        if agent_health[i] > 0:
            y, x = int(agent_positions[i, 0]), int(agent_positions[i, 1])
            team_id = agent_teams[i]
            if team_id == 0:
                red_pheromone[y,x] += r_deposit
            else:
                blue_pheromone[y,x] += b_deposit

    return agent_positions, agent_headings, agent_health, render_grid

class Simulation:
    def __init__(self, config, vfx_manager, audio_manager):
        self.config = config
        self.vfx_manager = vfx_manager
        self.audio_manager = audio_manager
        
        self.grid_size = (SIM_HEIGHT, SIM_WIDTH)
        self.team_params_overrides = {'red': {}, 'blue': {}}
        
        self.max_agents = 10000 
        self.agent_positions = np.zeros((self.max_agents, 2), dtype=np.float32)
        self.agent_headings = np.zeros(self.max_agents, dtype=np.float32)
        self.agent_teams = np.zeros(self.max_agents, dtype=np.int8)
        self.agent_health = np.zeros(self.max_agents, dtype=np.int32)
        self.agent_count = 0

        self.render_grid = np.full(self.grid_size, EMPTY, dtype=np.uint8)
        self.object_grid = np.full(self.grid_size, -1, dtype=np.int32)
        self.red_pheromone = np.zeros(self.grid_size, dtype=np.float32)
        self.blue_pheromone = np.zeros(self.grid_size, dtype=np.float32)
        
        self.bases = []
        self._initialize_bases()
        self._compile_team_params()

    def _compile_team_params(self):
        self.params_red = self.get_params_for_team('red')
        self.params_blue = self.get_params_for_team('blue')

    def get_params_for_team(self, team):
        params = {
            'sensor_angle_degrees': self.get_param(team, 'sensor_angle_degrees'),
            'rotation_angle_degrees': self.get_param(team, 'rotation_angle_degrees'),
            'sensor_distance': self.get_param(team, 'sensor_distance'),
            'pheromone_deposit_amount': self.get_param(team, 'pheromone_deposit_amount'),
            'sensor_angle_rad': np.deg2rad(self.get_param(team, 'sensor_angle_degrees')),
            'rotation_angle_rad': np.deg2rad(self.get_param(team, 'rotation_angle_degrees')),
        }
        return params

    def get_param(self, team, key):
        return self.team_params_overrides.get(team, {}).get(key, getattr(self.config, key))

    def _initialize_bases(self):
        self.bases = [
            Base('red', SIM_HEIGHT // 2, int(SIM_WIDTH * 0.8), 'N', self.config, scale=8.0),
            Base('blue', SIM_HEIGHT // 2, int(SIM_WIDTH * 0.2), 'Y', self.config, scale=8.0)
        ]
        self.draw_bases_to_grid()

    def draw_bases_to_grid(self):
        for base in self.bases:
            armor_id = RED_BASE_ARMOR if base.team == 'red' else BLUE_BASE_ARMOR
            for y,x in base.current_armor_pixels:
                 if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: self.render_grid[y,x] = armor_id
            core_id = RED_BASE_CORE if base.team == 'red' else BLUE_BASE_CORE
            for y,x in base.current_core_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: self.render_grid[y,x] = core_id

    def add_soldier(self, y, x, team, heading):
        if self.agent_count < self.max_agents:
            self.agent_positions[self.agent_count] = [y, x]
            self.agent_headings[self.agent_count] = heading
            self.agent_teams[self.agent_count] = 0 if team == 'red' else 1
            self.agent_health[self.agent_count] = 100
            self.agent_count += 1

    def get_team_agent_count(self, team):
        team_id = 0 if team == 'red' else 1
        if self.agent_count == 0: return 0
        active_teams = self.agent_teams[:self.agent_count]
        active_health = self.agent_health[:self.agent_count] > 0
        return np.sum(active_teams[active_health] == team_id)

    def get_team_base_health(self, team):
        for base in self.bases:
            if base.team == team:
                return len(base.current_armor_pixels)
        return 0

    def step(self):
        # Clear previous agent positions from render grid
        alive_indices = np.where(self.agent_health[:self.agent_count] > 0)[0]
        if alive_indices.size > 0:
            active_positions = self.agent_positions[alive_indices].astype(np.int32)
            self.render_grid[active_positions[:, 0], active_positions[:, 1]] = EMPTY
        
        # Pre-populate object grid for collision detection
        self.object_grid.fill(-1)
        for i in alive_indices:
            y, x = int(self.agent_positions[i, 0]), int(self.agent_positions[i, 1])
            self.object_grid[y, x] = i
            
        r_params = self.params_red
        b_params = self.params_blue
        
        # Run the Numba-optimized simulation step
        self.agent_positions, self.agent_headings, self.agent_health, self.render_grid = _numba_simulation_step(
            self.agent_count, self.agent_positions, self.agent_headings, self.agent_teams, self.agent_health,
            self.render_grid, self.object_grid, self.red_pheromone, self.blue_pheromone,
            self.grid_size[0], self.grid_size[1],
            r_params['sensor_angle_rad'], r_params['rotation_angle_rad'], r_params['sensor_distance'], r_params['pheromone_deposit_amount'],
            b_params['sensor_angle_rad'], b_params['rotation_angle_rad'], b_params['sensor_distance'], b_params['pheromone_deposit_amount']
        )
        
        # THE FIX: This is the correct, non-destructive way to remove dead agents.
        # It finds all living agents and copies their data to the start of the array.
        alive_mask = self.agent_health[:self.agent_count] > 0
        new_agent_count = np.sum(alive_mask)
        
        if new_agent_count < self.agent_count:
            self.agent_positions[:new_agent_count] = self.agent_positions[:self.agent_count][alive_mask]
            self.agent_headings[:new_agent_count] = self.agent_headings[:self.agent_count][alive_mask]
            self.agent_teams[:new_agent_count] = self.agent_teams[:self.agent_count][alive_mask]
            self.agent_health[:new_agent_count] = self.agent_health[:self.agent_count][alive_mask]
        
        self.agent_count = new_agent_count

        # Re-populate render grid with agents in their new positions
        for i in range(self.agent_count):
            y, x = int(self.agent_positions[i, 0]), int(self.agent_positions[i, 1])
            team_id = self.agent_teams[i]
            self.render_grid[y, x] = RED_SOLDIER if team_id == 0 else BLUE_SOLDIER
        
        # Decay and Diffuse Pheromones
        decay = self.config.pheromone_decay_rate
        blur = self.config.pheromone_blur_sigma
        if decay < 1.0: self.red_pheromone *= decay; self.blue_pheromone *= decay
        if blur > 0:
            self.red_pheromone = gaussian_filter(self.red_pheromone, sigma=blur)
            self.blue_pheromone = gaussian_filter(self.blue_pheromone, sigma=blur)
            
        for base in self.bases:
            base.update_spawning(self)
        self.draw_bases_to_grid()