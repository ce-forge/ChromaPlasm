import numpy as np
from numba import jit, prange
import random
import pygame
import json
from src.constants import *
from src.base import Base
from src.behaviors import get_next_move
from src.pheromone import PheromoneManager

@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def _numba_simulation_step(agent_count, agent_positions, agent_headings, agent_teams, agent_health,
                             vfx_events, base_damage_events, logic_grid, object_grid,
                             all_pheromone_grids, alliance_map, grid_h, grid_w,
                             r_sens_angle, r_rot_angle, r_sens_dist, b_sens_angle, b_rot_angle, b_sens_dist,
                             combat_chance, frame_count,
                             enemy_sense_radius_sq, base_attack_radius_sq, ai_update_interval):
    SPATIAL_GRID_CELL_SIZE = 30
    spatial_grid_w = (grid_w // SPATIAL_GRID_CELL_SIZE) + 1
    spatial_grid_h = (grid_h // SPATIAL_GRID_CELL_SIZE) + 1
    spatial_hash_grid = np.full((spatial_grid_h, spatial_grid_w), -1, dtype=np.int32)
    next_agent_in_cell = np.full(agent_count, -1, dtype=np.int32) 
    for i in range(agent_count):
        if agent_health[i] > 0:
            grid_x = int(agent_positions[i, 1] / SPATIAL_GRID_CELL_SIZE); grid_y = int(agent_positions[i, 0] / SPATIAL_GRID_CELL_SIZE)
            next_agent_in_cell[i] = spatial_hash_grid[grid_y, grid_x]; spatial_hash_grid[grid_y, grid_x] = i
    for i in prange(agent_count):
        if agent_health[i] <= 0: continue
        y, x, heading, team_id = agent_positions[i, 0], agent_positions[i, 1], agent_headings[i], agent_teams[i]
        agent_alliance_id = alliance_map[team_id]
        if frame_count % ai_update_interval == i % ai_update_interval:
            target_found, target_y, target_x = False, -1.0, -1.0
            min_dist_sq, best_target_y, best_target_x = enemy_sense_radius_sq, -1.0, -1.0
            agent_grid_x, agent_grid_y = int(x / SPATIAL_GRID_CELL_SIZE), int(y / SPATIAL_GRID_CELL_SIZE)
            for j in range(-1, 2):
                for k in range(-1, 2):
                    check_grid_y, check_grid_x = agent_grid_y + j, agent_grid_x + k
                    if 0 <= check_grid_y < spatial_grid_h and 0 <= check_grid_x < spatial_grid_w:
                        current_agent_idx = spatial_hash_grid[check_grid_y, check_grid_x]
                        while current_agent_idx != -1:
                            other_team_id = agent_teams[current_agent_idx]
                            if alliance_map[other_team_id] != agent_alliance_id:
                                other_y, other_x = agent_positions[current_agent_idx]
                                dist_sq = (y - other_y)**2 + (x - other_x)**2
                                if dist_sq < min_dist_sq: min_dist_sq, best_target_y, best_target_x = dist_sq, other_y, other_x
                            current_agent_idx = next_agent_in_cell[current_agent_idx]
            min_armor_dist_sq, best_armor_target_y, best_armor_target_x = base_attack_radius_sq, -1.0, -1.0
            for sy in range(int(y) - 50, int(y) + 50):
                for sx in range(int(x) - 50, int(x) + 50):
                    if 0 <= sy < grid_h and 0 <= sx < grid_w:
                        terrain_id = logic_grid[sy, sx]
                        if BASE_ARMOR_OFFSET <= terrain_id < BASE_CORE_OFFSET:
                            base_team_id = terrain_id - BASE_ARMOR_OFFSET
                            if alliance_map[base_team_id] != agent_alliance_id:
                                dist_sq = (y - sy)**2 + (x - sx)**2
                                if dist_sq < min_armor_dist_sq: min_armor_dist_sq, best_armor_target_y, best_armor_target_x = dist_sq, float(sy), float(sx)
            if best_target_y != -1.0 and min_dist_sq < min_armor_dist_sq: target_y, target_x, target_found = best_target_y, best_target_x, True
            elif best_armor_target_y != -1.0: target_y, target_x, target_found = best_armor_target_y, best_armor_target_x, True
            if target_found: heading = np.arctan2(target_y - y, target_x - x)
            else:
                pheromone_grid = all_pheromone_grids[team_id]
                (ny_p, nx_p), heading = get_next_move(y, x, heading, pheromone_grid, grid_h, grid_w, r_sens_angle, r_rot_angle, r_sens_dist)
        ny, nx = y + np.sin(heading), x + np.cos(heading)
        if ny <= 1 or ny >= grid_h - 2 or nx <= 1 or nx >= grid_w - 2: agent_health[i] = 0; continue
        agent_headings[i] = heading; ny_int, nx_int = int(ny), int(nx)
        target_terrain_id, target_object_idx = logic_grid[ny_int, nx_int], object_grid[ny_int, nx_int]
        if target_object_idx != -1 and alliance_map[agent_teams[target_object_idx]] != agent_alliance_id:
            if random.random() < combat_chance: agent_health[target_object_idx] = 0
            if random.random() < combat_chance: agent_health[i] = 0
            vfx_events[i, 0], vfx_events[i, 1], vfx_events[i, 2] = 1, ny_int, nx_int
        elif BASE_ARMOR_OFFSET <= target_terrain_id < BASE_CORE_OFFSET and alliance_map[target_terrain_id - BASE_ARMOR_OFFSET] != agent_alliance_id:
            agent_health[i] = 0; logic_grid[ny_int, nx_int] = EMPTY
            vfx_events[i, 0], vfx_events[i, 1], vfx_events[i, 2] = 1, ny_int, nx_int
            base_team_id = target_terrain_id - BASE_ARMOR_OFFSET
            base_damage_events[i, 0] = 1; base_damage_events[i, 1] = base_team_id; base_damage_events[i, 2] = team_id
        elif target_terrain_id == EMPTY: agent_positions[i] = [ny, nx]
        else:
            found_escape = False
            for _ in range(5):
                rand_heading = random.uniform(0, 2 * np.pi); check_y, check_x = int(y + np.sin(rand_heading)), int(x + np.cos(rand_heading))
                if 0 <= check_y < grid_h and 0 <= check_x < grid_w and logic_grid[check_y, check_x] == EMPTY:
                    agent_headings[i] = rand_heading; found_escape = True; break
            if not found_escape: agent_headings[i] += np.pi
    return agent_positions, agent_headings, agent_health, vfx_events, base_damage_events, logic_grid

class Simulation:
    def __init__(self, config, vfx_manager, audio_manager):
        self.config, self.vfx_manager, self.audio_manager = config, vfx_manager, audio_manager
        self.frame_count = 0; self.grid_size = (SIM_HEIGHT, SIM_WIDTH)
        self.pheromone_managers = { team['id']: PheromoneManager(self.grid_size, config) for team in TEAMS }
        for team in TEAMS: self.pheromone_managers[team['id']].color = team['pheromone_color']
        self.pheromone_surfaces = { team['id']: pygame.Surface((self.grid_size[1], self.grid_size[0]), flags=pygame.SRCALPHA) for team in TEAMS }
        self.alliance_map = np.arange(len(TEAMS)); self.team_params_overrides = {}
        
        self.max_agents = 10000 
        self.agent_positions = np.zeros((self.max_agents, 2), dtype=np.float32)
        
        self.agent_headings = np.zeros(self.max_agents, dtype=np.float32)
        
        self.agent_teams = np.zeros(self.max_agents, dtype=np.int8)
        self.agent_health = np.zeros(self.max_agents, dtype=np.int32)
        self.vfx_events = np.zeros((self.max_agents, 3), dtype=np.int32)
        self.base_damage_events = np.zeros((self.max_agents, 3), dtype=np.int32)
        self.agent_count = 0; self.render_grid = np.full(self.grid_size, EMPTY, dtype=np.uint8)
        self.object_grid = np.full(self.grid_size, -1, dtype=np.int32)
        self.bases = []; self.kill_counts = {team['id']: 0 for team in TEAMS}; self.dead_teams = set()
        self.winner_info = None
        
        self._initialize_bases()
        self._compile_team_params()

    def _compile_team_params(self):
        self.params_red = self.get_params_for_team(1)
        self.params_blue = self.get_params_for_team(0)

    def get_params_for_team(self, team_id):
        return {'sensor_angle_degrees': self.get_param(team_id, 'sensor_angle_degrees'),'rotation_angle_degrees': self.get_param(team_id, 'rotation_angle_degrees'),'sensor_distance': self.get_param(team_id, 'sensor_distance'),'pheromone_deposit_amount': self.get_param(team_id, 'pheromone_deposit_amount'),'sensor_angle_rad': np.deg2rad(self.get_param(team_id, 'sensor_angle_degrees')),'rotation_angle_rad': np.deg2rad(self.get_param(team_id, 'rotation_angle_degrees')),}

    def get_param(self, team_id, key):
        return self.team_params_overrides.get(team_id, {}).get(key, getattr(self.config, key))

    def _initialize_bases(self):
        self.bases = []
        try:
            with open('base_layouts.json', 'r') as f: layout_data = json.load(f)
            for base_config in layout_data.get('initial_layout', []):
                new_base = Base(base_config['team'], base_config['pivot'][0], base_config['pivot'][1], base_config['shape_name'], self.config, self.grid_size[0], self.grid_size[1])
                new_base.scale = base_config.get('scale', new_base.scale)
                new_base.core_thickness = base_config.get('core_thickness', new_base.core_thickness)
                new_base.armor_thickness = base_config.get('armor_thickness', new_base.armor_thickness)
                absolute_ports = base_config.get('exit_ports', []);
                if absolute_ports: new_base._relative_exit_ports = [(p[0] - new_base.pivot[0], p[1] - new_base.pivot[1]) for p in absolute_ports]
                new_base.recalculate_geometry(final_calculation=True, regenerate_ports=False)
                self.bases.append(new_base)
        except (FileNotFoundError, json.JSONDecodeError) as e: print(f"ERROR loading 'base_layouts.json': {e}")

    def draw_bases_to_grid(self):
        all_core_pixels = set()
        for base in self.bases: all_core_pixels.update(base.current_core_pixels)
        for base in self.bases:
            core_id = BASE_CORE_OFFSET + base.team_id; armor_id = BASE_ARMOR_OFFSET + base.team_id
            for y, x in base.current_core_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: self.render_grid[y, x] = core_id
            for y, x in base.current_armor_pixels:
                 if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH and (y, x) not in all_core_pixels: self.render_grid[y, x] = armor_id

    def add_soldier(self, y, x, team_id, heading):
        if self.agent_count < self.max_agents:
            self.agent_positions[self.agent_count] = [y, x]; self.agent_headings[self.agent_count] = heading
            self.agent_teams[self.agent_count] = team_id; self.agent_health[self.agent_count] = 100
            self.agent_count += 1

    def get_team_agent_count(self, team_name):
        team_id = TEAM_NAME_TO_ID.get(team_name.lower())
        if team_id is None or self.agent_count == 0: return 0
        alive_mask = self.agent_health[:self.agent_count] > 0
        return np.sum(self.agent_teams[:self.agent_count][alive_mask] == team_id)

    def get_team_base_health(self, team_name):
        team_id = TEAM_NAME_TO_ID.get(team_name.lower())
        if team_id is None: return 0
        total_health = 0
        for base in self.bases:
            if base.team_id == team_id: total_health += len(base.current_armor_pixels)
        return total_health

    def step(self, frame_count):
        self.frame_count = frame_count
        logic_grid = np.full(self.grid_size, EMPTY, dtype=np.uint8)
        all_core_pixels = set(); [all_core_pixels.update(b.current_core_pixels) for b in self.bases]
        for base in self.bases:
            core_id, armor_id = BASE_CORE_OFFSET + base.team_id, BASE_ARMOR_OFFSET + base.team_id
            for y,x in base.current_core_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH: logic_grid[y,x] = core_id
            for y,x in base.current_armor_pixels:
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH and (y,x) not in all_core_pixels: logic_grid[y,x] = armor_id
        
        self.object_grid.fill(-1)
        alive_indices = np.where(self.agent_health[:self.agent_count] > 0)[0]
        for i in alive_indices:
            y, x = int(self.agent_positions[i, 0]), int(self.agent_positions[i, 1])
            if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]: self.object_grid[y, x] = i
        
        all_phero_grids = np.stack([self.pheromone_managers[i].grid for i in range(len(TEAMS))])
        r_params, b_params = self.params_red, self.params_blue
        self.agent_positions, self.agent_headings, self.agent_health, self.vfx_events, self.base_damage_events, post_combat_grid = _numba_simulation_step(
            self.agent_count, self.agent_positions, self.agent_headings, self.agent_teams, self.agent_health, 
            self.vfx_events, self.base_damage_events, logic_grid, self.object_grid, all_phero_grids, self.alliance_map,
            self.grid_size[0], self.grid_size[1], 
            r_params['sensor_angle_rad'], r_params['rotation_angle_rad'], r_params['sensor_distance'], 
            b_params['sensor_angle_rad'], b_params['rotation_angle_rad'], b_params['sensor_distance'], 
            self.config.combat_chance, self.frame_count, self.config.enemy_sense_radius**2, self.config.base_attack_radius**2, self.config.ai_update_interval)
        
        for i in range(self.agent_count):
            if self.vfx_events[i, 0] == 1:
                event_y, event_x = self.vfx_events[i, 1], self.vfx_events[i, 2]
                self.vfx_manager.create_explosion(event_y, event_x, TEAMS[self.agent_teams[i]]["color"], self.frame_count)
                self.vfx_events[i, 0] = 0
            if self.base_damage_events[i, 0] == 1:
                damaged_team_id, killer_team_id = self.base_damage_events[i, 1], self.base_damage_events[i, 2]
                for base in self.bases:
                    if base.team_id == damaged_team_id: base.last_damage_frame = frame_count
                self.audio_manager.add_sfx(self.frame_count, 'crack')
                if self.frame_count < self.config.total_frames:
                    self.kill_counts[killer_team_id] += 1
                self.base_damage_events[i, 0] = 0

        alive_mask = self.agent_health[:self.agent_count] > 0
        new_agent_count = np.sum(alive_mask)
        if new_agent_count < self.agent_count:
            self.agent_positions[:new_agent_count] = self.agent_positions[:self.agent_count][alive_mask]
            self.agent_headings[:new_agent_count] = self.agent_headings[:self.agent_count][alive_mask]
            self.agent_teams[:new_agent_count] = self.agent_teams[:self.agent_count][alive_mask]
            self.agent_health[:new_agent_count] = self.agent_health[:self.agent_count][alive_mask]
        self.agent_count = new_agent_count
        
        for base in self.bases:
            armor_id = BASE_ARMOR_OFFSET + base.team_id
            base.current_armor_pixels = [(y, x) for y, x in base.current_armor_pixels if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1] and post_combat_grid[y, x] == armor_id]
        
        active_team_ids_in_pheromones = np.unique(self.agent_teams[:self.agent_count])
        for team_id in active_team_ids_in_pheromones:
            manager = self.pheromone_managers[team_id]
            team_agent_mask = (self.agent_teams[:self.agent_count] == team_id)
            if np.any(team_agent_mask): manager.deposit(self.agent_positions[:self.agent_count][team_agent_mask], self.get_param(team_id, 'pheromone_deposit_amount'))
        
        for manager in self.pheromone_managers.values(): manager.update(self.frame_count)
        if self.frame_count % 2 == 0:
            for team_id in active_team_ids_in_pheromones: self.pheromone_surfaces[team_id] = self.pheromone_managers[team_id].get_render_surface()

        self.render_grid.fill(EMPTY)
        self.draw_bases_to_grid()
        for base in self.bases: base.update_spawning(self)

        active_teams_in_scene = {b.team_id for b in self.bases}
        for team_id in active_teams_in_scene:
            team_name = TEAMS[team_id]['name']
            if self.get_team_base_health(team_name) == 0 and team_id not in self.dead_teams:
                self.dead_teams.add(team_id)
        
        # --- NEW: Winner Detection Logic ---
        if self.winner_info is None and self.frame_count > 0:
            # Check for active alliances, not just teams
            active_alliances = {self.alliance_map[b.team_id] for b in self.bases if self.get_team_base_health(TEAMS[b.team_id]['name']) > 0}
            
            # Condition 1: Only one alliance is left standing
            if len(active_alliances) == 1:
                winner_alliance_id = active_alliances.pop()
                # Find a representative team from the winning alliance
                winner_team_id = next(b.team_id for b in self.bases if self.alliance_map[b.team_id] == winner_alliance_id)
                self.winner_info = {'id': winner_team_id, 'reason': 'elimination'}
                self.vfx_manager.create_winner_celebration(winner_team_id, SIM_WIDTH // 2, SIM_HEIGHT // 2)

            # Condition 2: Timer runs out
            elif self.frame_count >= self.config.total_frames:
                if self.kill_counts:
                    winner_team_id = max(self.kill_counts, key=self.kill_counts.get)
                    self.winner_info = {'id': winner_team_id, 'reason': 'kills'}
                    self.vfx_manager.create_winner_celebration(winner_team_id, SIM_WIDTH // 2, SIM_HEIGHT // 2)
                else:
                    self.winner_info = {'id': -1, 'reason': 'draw'}

    def reset_dynamic_state(self):
        self.agent_count = 0
        for manager in self.pheromone_managers.values(): manager.grid.fill(0)
        self.draw_bases_to_grid()
        for surf in self.pheromone_surfaces.values():
            surf.fill((0, 0, 0, 0))
        self.kill_counts = {team['id']: 0 for team in TEAMS}
        self.dead_teams.clear()
        self.winner_info = None # Reset winner info

    def add_new_base(self, team_name='Azure', shape_name='BOX'):
        new_base = Base(team_name, self.grid_size[0]//2, self.grid_size[1]//2, shape_name, self.config, self.grid_size[0], self.grid_size[1])
        self.bases.append(new_base)
        return new_base

    def delete_base(self, base_to_delete):
        if base_to_delete and base_to_delete in self.bases: self.bases.remove(base_to_delete)

    def get_base_at(self, world_y, world_x):
        for base in reversed(self.bases):
            if hasattr(base, 'all_base_pixels') and (world_y, world_x) in base.all_base_pixels: return base
        return None