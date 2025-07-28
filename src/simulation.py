import numpy as np
from scipy.ndimage import gaussian_filter
from numba import jit, prange
import random
import pygame

from src.constants import *
from src.base import Base
from src.behaviors import get_next_move
from src.pheromone import PheromoneManager

@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def _numba_simulation_step(agent_count, agent_positions, agent_headings, agent_teams, agent_health,
                             vfx_events,
                             logic_grid, object_grid, red_pheromone, blue_pheromone,
                             grid_h, grid_w,
                             r_sens_angle, r_rot_angle, r_sens_dist,
                             b_sens_angle, b_rot_angle, b_sens_dist,
                             combat_chance,
                             frame_count):

    ENEMY_SENSE_RADIUS_SQ = 30**2
    BASE_ATTACK_RADIUS_SQ = 50**2
    AI_UPDATE_INTERVAL = 10 
    
    SPATIAL_GRID_CELL_SIZE = 30
    spatial_grid_w = (grid_w // SPATIAL_GRID_CELL_SIZE) + 1
    spatial_grid_h = (grid_h // SPATIAL_GRID_CELL_SIZE) + 1
    
    spatial_hash_grid = np.full((spatial_grid_h, spatial_grid_w), -1, dtype=np.int32)
    next_agent_in_cell = np.full(agent_count, -1, dtype=np.int32) 

    for i in range(agent_count):
        if agent_health[i] > 0:
            grid_x = int(agent_positions[i, 1] / SPATIAL_GRID_CELL_SIZE)
            grid_y = int(agent_positions[i, 0] / SPATIAL_GRID_CELL_SIZE)
            next_agent_in_cell[i] = spatial_hash_grid[grid_y, grid_x]
            spatial_hash_grid[grid_y, grid_x] = i

    for i in prange(agent_count):
        if agent_health[i] <= 0: continue
        y, x, heading, team_id = agent_positions[i, 0], agent_positions[i, 1], agent_headings[i], agent_teams[i]
        is_red_team = team_id == 0

        if frame_count % AI_UPDATE_INTERVAL == i % AI_UPDATE_INTERVAL:
            target_found = False; target_y, target_x = -1.0, -1.0
            min_dist_sq = ENEMY_SENSE_RADIUS_SQ
            best_target_y, best_target_x = -1.0, -1.0
            
            agent_grid_x = int(x / SPATIAL_GRID_CELL_SIZE)
            agent_grid_y = int(y / SPATIAL_GRID_CELL_SIZE)
            
            for j in range(-1, 2):
                for k in range(-1, 2):
                    check_grid_y, check_grid_x = agent_grid_y + j, agent_grid_x + k
                    if 0 <= check_grid_y < spatial_grid_h and 0 <= check_grid_x < spatial_grid_w:
                        current_agent_idx = spatial_hash_grid[check_grid_y, check_grid_x]
                        while current_agent_idx != -1:
                            if agent_teams[current_agent_idx] != team_id:
                                other_y, other_x = agent_positions[current_agent_idx]
                                dist_sq = (y - other_y)**2 + (x - other_x)**2
                                if dist_sq < min_dist_sq:
                                    min_dist_sq, best_target_y, best_target_x = dist_sq, other_y, other_x
                            current_agent_idx = next_agent_in_cell[current_agent_idx]

            min_armor_dist_sq = BASE_ATTACK_RADIUS_SQ
            best_armor_target_y, best_armor_target_x = -1.0, -1.0
            enemy_base_x = grid_w * 0.2 if is_red_team else grid_w * 0.8
            if (x - enemy_base_x)**2 < BASE_ATTACK_RADIUS_SQ:
                enemy_armor_id = BLUE_BASE_ARMOR if is_red_team else RED_BASE_ARMOR
                for sy in range(int(y) - 50, int(y) + 50):
                    for sx in range(int(x) - 50, int(x) + 50):
                        if 0 <= sy < grid_h and 0 <= sx < grid_w and logic_grid[sy, sx] == enemy_armor_id:
                            dist_sq = (y - sy)**2 + (x - sx)**2
                            if dist_sq < min_armor_dist_sq:
                                min_armor_dist_sq, best_armor_target_y, best_armor_target_x = dist_sq, float(sy), float(sx)
            
            if best_target_y != -1.0 and min_dist_sq < min_armor_dist_sq:
                target_y, target_x, target_found = best_target_y, best_target_x, True
            elif best_armor_target_y != -1.0:
                target_y, target_x, target_found = best_armor_target_y, best_armor_target_x, True

            if target_found:
                heading = np.arctan2(target_y - y, target_x - x)
            else:
                (ny_p, nx_p), heading = get_next_move(y, x, heading, red_pheromone if is_red_team else blue_pheromone, grid_h, grid_w, r_sens_angle if is_red_team else b_sens_angle, r_rot_angle if is_red_team else b_rot_angle, r_sens_dist if is_red_team else b_sens_dist)

        ny, nx = y + np.sin(heading), x + np.cos(heading)
        if ny <= 1 or ny >= grid_h - 2 or nx <= 1 or nx >= grid_w - 2:
            agent_health[i] = 0; continue
        agent_headings[i] = heading
        ny_int, nx_int = int(ny), int(nx)
        
        target_terrain_id, target_object_idx = logic_grid[ny_int, nx_int], object_grid[ny_int, nx_int]
        if target_object_idx != -1 and agent_teams[target_object_idx] != team_id:
            if random.random() < combat_chance: agent_health[target_object_idx] = 0
            if random.random() < combat_chance: agent_health[i] = 0
            vfx_events[i, 0], vfx_events[i, 1], vfx_events[i, 2] = 1, ny_int, nx_int
        elif (is_red_team and target_terrain_id == BLUE_BASE_ARMOR) or ((not is_red_team) and target_terrain_id == RED_BASE_ARMOR):
            agent_health[i] = 0
            logic_grid[ny_int, nx_int] = EMPTY
            vfx_events[i, 0], vfx_events[i, 1], vfx_events[i, 2] = 1, ny_int, nx_int
        elif target_terrain_id == EMPTY:
            agent_positions[i] = [ny, nx]
        else:
            # --- START OF NEW "NATURAL BOUNCE" LOGIC ---
            found_escape = False
            # Try up to 5 times to find a random direction that is not blocked.
            for _ in range(5):
                rand_heading = random.uniform(0, 2 * np.pi)
                
                # Check one step in the new random direction
                check_y = int(y + np.sin(rand_heading))
                check_x = int(x + np.cos(rand_heading))

                # Is the new spot valid and empty?
                if 0 <= check_y < grid_h and 0 <= check_x < grid_w and logic_grid[check_y, check_x] == EMPTY:
                    agent_headings[i] = rand_heading
                    found_escape = True
                    break # Exit the loop once an escape is found
            
            # Fallback: If no escape was found, do the old 180-degree flip to prevent getting stuck.
            if not found_escape:
                agent_headings[i] += np.pi
            # --- END OF NEW "NATURAL BOUNCE" LOGIC ---

    return agent_positions, agent_headings, agent_health, vfx_events, logic_grid

class Simulation:
    # __init__ and all other methods in the Simulation class remain exactly the same.
    def __init__(self, config, vfx_manager, audio_manager):
        self.config, self.vfx_manager, self.audio_manager = config, vfx_manager, audio_manager
        self.frame_count = 0
        self.grid_size = (SIM_HEIGHT, SIM_WIDTH)
        self.red_pheromones = PheromoneManager(self.grid_size, config)
        self.blue_pheromones = PheromoneManager(self.grid_size, config)
        self.red_pheromones.color = COLOR_MAP[RED_BASE_ARMOR][:3]
        self.blue_pheromones.color = COLOR_MAP[BLUE_BASE_ARMOR][:3]
        self.red_pheromone_surface = pygame.Surface((self.grid_size[1], self.grid_size[0]), flags=pygame.SRCALPHA)
        self.blue_pheromone_surface = pygame.Surface((self.grid_size[1], self.grid_size[0]), flags=pygame.SRCALPHA)
        self.team_params_overrides = {'red': {}, 'blue': {}}
        self.max_agents = 10000 
        self.agent_positions = np.zeros((self.max_agents, 2), dtype=np.float32)
        self.agent_headings = np.zeros(self.max_agents, dtype=np.float32)
        self.agent_teams = np.zeros(self.max_agents, dtype=np.int8)
        self.agent_health = np.zeros(self.max_agents, dtype=np.int32)
        self.vfx_events = np.zeros((self.max_agents, 3), dtype=np.int32)
        self.agent_count = 0
        self.render_grid = np.full(self.grid_size, EMPTY, dtype=np.uint8)
        self.object_grid = np.full(self.grid_size, -1, dtype=np.int32)
        self.bases = []
        self._initialize_bases()
        self._compile_team_params()

    def _compile_team_params(self):
        self.params_red = self.get_params_for_team('red')
        self.params_blue = self.get_params_for_team('blue')

    def get_params_for_team(self, team):
        params = { 'sensor_angle_degrees': self.get_param(team, 'sensor_angle_degrees'), 'rotation_angle_degrees': self.get_param(team, 'rotation_angle_degrees'), 'sensor_distance': self.get_param(team, 'sensor_distance'), 'pheromone_deposit_amount': self.get_param(team, 'pheromone_deposit_amount'), 'sensor_angle_rad': np.deg2rad(self.get_param(team, 'sensor_angle_degrees')), 'rotation_angle_rad': np.deg2rad(self.get_param(team, 'rotation_angle_degrees')), }
        return params

    def get_param(self, team, key):
        return self.team_params_overrides.get(team, {}).get(key, getattr(self.config, key))

    def _initialize_bases(self):
        grid_h, grid_w = self.grid_size
        self.bases = [ Base('red', SIM_HEIGHT // 2, int(SIM_WIDTH * 0.8), 'N', self.config, scale=8.0, core_thickness=1, armor_thickness=2, grid_h=grid_h, grid_w=grid_w), Base('blue', SIM_HEIGHT // 2, int(SIM_WIDTH * 0.2), 'Y', self.config, scale=8.0, core_thickness=1, armor_thickness=2, grid_h=grid_h, grid_w=grid_w) ]
        self.draw_bases_to_grid()

    def draw_bases_to_grid(self):
        # Pass 1: Collect all core pixels from all bases. This is for the fusion check.
        all_core_pixels = set()
        for base in self.bases:
            all_core_pixels.update(base.current_core_pixels)

        # Pass 2: Draw all cores and armor from their pre-calculated lists.
        for base in self.bases:
            core_id = RED_BASE_CORE if base.team == 'red' else BLUE_BASE_CORE
            armor_id = RED_BASE_ARMOR if base.team == 'red' else BLUE_BASE_ARMOR
            
            # Draw the core pixels
            for y, x in base.current_core_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH:
                    self.render_grid[y, x] = core_id

            # Draw the (potentially damaged) armor pixels
            for y, x in base.current_armor_pixels:
                 if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH:
                    # The fusion check: only draw armor if the spot is not another base's core.
                    if (y, x) not in all_core_pixels:
                        self.render_grid[y, x] = armor_id

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
        alive_mask = self.agent_health[:self.agent_count] > 0
        return np.sum(self.agent_teams[:self.agent_count][alive_mask] == team_id)

    def get_team_base_health(self, team):
        return np.sum(self.render_grid == (RED_BASE_ARMOR if team == 'red' else BLUE_BASE_ARMOR))

    def step(self, frame_count):
        self.frame_count = frame_count
        
        logic_grid = np.full(self.grid_size, EMPTY, dtype=np.uint8)
        for base in self.bases:
            armor_id = RED_BASE_ARMOR if base.team == 'red' else BLUE_BASE_ARMOR
            core_id = RED_BASE_CORE if base.team == 'red' else BLUE_BASE_CORE
            for y,x in base.current_armor_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: logic_grid[y,x] = armor_id
            for y,x in base.current_core_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: logic_grid[y,x] = core_id

        alive_indices = np.where(self.agent_health[:self.agent_count] > 0)[0]
        self.object_grid.fill(-1)
        for i in alive_indices:
            y, x = int(self.agent_positions[i, 0]), int(self.agent_positions[i, 1])
            if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]:
                self.object_grid[y, x] = i
        
        r_params, b_params = self.params_red, self.params_blue
        self.agent_positions, self.agent_headings, self.agent_health, self.vfx_events, post_combat_grid = _numba_simulation_step(self.agent_count, self.agent_positions, self.agent_headings, self.agent_teams, self.agent_health, self.vfx_events, logic_grid, self.object_grid, self.red_pheromones.grid, self.blue_pheromones.grid, self.grid_size[0], self.grid_size[1], r_params['sensor_angle_rad'], r_params['rotation_angle_rad'], r_params['sensor_distance'], b_params['sensor_angle_rad'], b_params['rotation_angle_rad'], b_params['sensor_distance'], self.config.combat_chance, self.frame_count)
        
        for i in range(self.agent_count):
            event_type = self.vfx_events[i, 0]
            if event_type == 1:
                event_y, event_x = self.vfx_events[i, 1], self.vfx_events[i, 2]
                team_id = self.agent_teams[i]
                color = self.red_pheromones.color if team_id == 0 else self.blue_pheromones.color
                self.vfx_manager.create_explosion(event_y, event_x, color, self.frame_count)
                self.vfx_events[i, 0] = 0
        
        alive_mask = self.agent_health[:self.agent_count] > 0
        red_agent_mask = alive_mask & (self.agent_teams[:self.agent_count] == 0)
        blue_agent_mask = alive_mask & (self.agent_teams[:self.agent_count] == 1)
        if np.any(red_agent_mask): self.red_pheromones.deposit(self.agent_positions[:self.agent_count][red_agent_mask], self.get_param('red', 'pheromone_deposit_amount'))
        if np.any(blue_agent_mask): self.blue_pheromones.deposit(self.agent_positions[:self.agent_count][blue_agent_mask], self.get_param('blue', 'pheromone_deposit_amount'))
        self.red_pheromones.update(self.frame_count)
        self.blue_pheromones.update(self.frame_count)
        if self.frame_count % 2 == 0:
            self.red_pheromone_surface = self.red_pheromones.get_render_surface()
            self.blue_pheromone_surface = self.blue_pheromones.get_render_surface()
        
        new_agent_count = np.sum(alive_mask)
        if new_agent_count < self.agent_count:
            self.agent_positions[:new_agent_count] = self.agent_positions[:self.agent_count][alive_mask]
            self.agent_headings[:new_agent_count] = self.agent_headings[:self.agent_count][alive_mask]
            self.agent_teams[:new_agent_count] = self.agent_teams[:self.agent_count][alive_mask]
            self.agent_health[:new_agent_count] = self.agent_health[:self.agent_count][alive_mask]
        self.agent_count = new_agent_count

        for base in self.bases:
            armor_id = RED_BASE_ARMOR if base.team == 'red' else BLUE_BASE_ARMOR
            base.current_armor_pixels = [(y, x) for y, x in base.current_armor_pixels if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1] and post_combat_grid[y, x] == armor_id]

        self.render_grid.fill(EMPTY)
        self.draw_bases_to_grid()
        for base in self.bases:
            base.update_spawning(self)
        for i in range(self.agent_count):
            y, x = int(self.agent_positions[i, 0]), int(self.agent_positions[i, 1])
            if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]:
                self.render_grid[y, x] = RED_SOLDIER if self.agent_teams[i] == 0 else BLUE_SOLDIER

    # In simulation.py, inside the Simulation class
    def reset_dynamic_state(self):
        """Resets agents and pheromones but preserves the base layout."""
        self.agent_positions.fill(0)
        self.agent_headings.fill(0)
        self.agent_teams.fill(0)
        self.agent_health.fill(0)
        self.agent_count = 0
        self.red_pheromones.grid.fill(0)
        self.blue_pheromones.grid.fill(0)
        self.draw_bases_to_grid() # Redraw the preserved bases onto a clean grid

    def add_new_base(self, team='blue', shape_name='BOX'):
        """Adds a new default base and returns it."""
        grid_h, grid_w = self.grid_size
        new_base = Base(team, grid_h // 2, grid_w // 2, shape_name, self.config, scale=8.0, 
                        core_thickness=1, armor_thickness=2, grid_h=grid_h, grid_w=grid_w)
        self.bases.append(new_base)
        return new_base # Add this return statement

    def delete_base(self, base_to_delete):
        """Removes a selected base."""
        if base_to_delete and base_to_delete in self.bases:
            self.bases.remove(base_to_delete)

    def get_base_at(self, world_y, world_x):
        """Finds which base, if any, occupies a given coordinate."""
        for base in reversed(self.bases):
            if hasattr(base, 'all_base_pixels') and (world_y, world_x) in base.all_base_pixels:
                return base
        return None