import numpy as np
import random
from scipy.ndimage import gaussian_filter
from src.assets.layouts import poll_layout
from src.constants import *
from src.behaviors import SlimeMoldBehavior
from src.soldier import Soldier

# --- Main Simulation Engine ---
class Simulation:
    def __init__(self, config, vfx_manager, audio_manager):
        self.config = config
        self.vfx_manager = vfx_manager
        self.audio_manager = audio_manager
        self.grid_size = (SIM_HEIGHT, SIM_WIDTH)
        
        # Pheromone grid setup
        self.red_pheromone = np.zeros(self.grid_size, dtype=np.float32)
        self.blue_pheromone = np.zeros(self.grid_size, dtype=np.float32)
        
        # Object grid for high-speed lookups
        self.object_grid = np.full(self.grid_size, None, dtype=object)
        
        # Render grid for visualization
        self.render_grid, self.bases = poll_layout(self.grid_size, self.config)

        self.red_soldiers = []
        self.blue_soldiers = []
        self.frame_counter = 0

        # Camera state (formerly Director)
        self.peak_red_strength = 1
        self.peak_blue_strength = 1
        self.losing_team_for_camera = None
        self.current_zoom = 1.0
        self.target_zoom = 1.0
        self.current_cam_center_y = SIM_HEIGHT / 2.0
        self.current_cam_center_x = SIM_WIDTH / 2.0
        self.target_cam_center_y = SIM_HEIGHT / 2.0
        self.target_cam_center_x = SIM_WIDTH / 2.0

    def get_param(self, team, key):
        """
        Gets a parameter value. Checks for a team-specific override first,
        then falls back to the global config.
        """
        # Find a base belonging to the team to check for an override
        for base in self.bases:
            if base.team == team:
                # If the base has a specific override for this key, use it
                if key in base.params:
                    return base.params[key]
                break # Found the team's base, no need to check others
        
        # If no override was found, return the global value from the config
        return getattr(self.config, key)

    def add_soldier(self, soldier):
        """Adds a new soldier to the simulation."""
        team_list = self.red_soldiers if soldier.team == 'red' else self.blue_soldiers
        team_list.append(soldier)

    def remove_soldier(self, soldier):
        """Removes a soldier from the simulation and marks it as dead."""
        team_list = self.red_soldiers if soldier.team == 'red' else self.blue_soldiers
        if soldier in team_list:
            team_list.remove(soldier)
        soldier.y = None # Mark as dead to be ignored by other logic this frame


    def _update_pheromones(self):
        """Updates and diffuses the pheromone trails for both teams."""
        
        # We start with a grid of all False values.
        base_mask = np.full(self.grid_size, False, dtype=bool)
        for base in self.bases:
            # Mark all armor and core pixels of this base as True in the mask.
            for y, x in base.current_armor_pixels:
                if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]:
                    base_mask[y, x] = True
            for y, x in base.current_core_pixels:
                if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]:
                    base_mask[y, x] = True

        # 1. Decay everything
        self.red_pheromone *= self.get_param('red', 'pheromone_decay_rate')
        self.blue_pheromone *= self.get_param('blue', 'pheromone_decay_rate')
        
        # 2. Deposit from soldiers
        red_deposit = self.get_param('red', 'pheromone_deposit_amount')
        blue_deposit = self.get_param('blue', 'pheromone_deposit_amount')
        for s in self.red_soldiers:
            if s.y is not None: self.red_pheromone[s.y, s.x] += red_deposit
        for s in self.blue_soldiers:
            if s.y is not None: self.blue_pheromone[s.y, s.x] += blue_deposit

        # 3. Blur (diffuse) the existing pheromone map
        red_blur = self.get_param('red', 'pheromone_blur_sigma')
        blue_blur = self.get_param('blue', 'pheromone_blur_sigma')
        if red_blur > 0: self.red_pheromone = gaussian_filter(self.red_pheromone, sigma=red_blur)
        if blue_blur > 0: self.blue_pheromone = gaussian_filter(self.blue_pheromone, sigma=blue_blur)

        # 4. Pump from bases AFTER blurring
        for base in self.bases:
            pheromone_grid = self.red_pheromone if base.team == 'red' else self.blue_pheromone
            for y, x in base.exit_ports:
                if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]:
                    pheromone_grid[y, x] = self.config.base_pump_amount
        
        # Set pheromone values to 0 wherever a base exists.
        # This prevents bases from becoming "sticky" scent traps.
        self.red_pheromone[base_mask] = 0
        self.blue_pheromone[base_mask] = 0
        
    def _update_soldiers_and_combat(self):
        """Moves all soldiers based on slime mold behavior and handles adjacent combat."""
        all_soldiers = self.red_soldiers + self.blue_soldiers
        random.shuffle(all_soldiers)

        for soldier in all_soldiers:
            if soldier.y is None: continue

            # Assign behavior on first update if it doesn't have one
            if soldier.behavior is None:
                soldier.behavior = SlimeMoldBehavior()

            # Get move from behavior
            old_y, old_x = soldier.y, soldier.x
            target_y, target_x = soldier.behavior.get_next_move(soldier, self)
            
            if self.object_grid[target_y, target_x] is None:
                soldier.y, soldier.x = target_y, target_x
            
            # Combat check against adjacent squares
            for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                ny, nx = soldier.y + dy, soldier.x + dx
                if 0 <= ny < self.grid_size[0] and 0 <= nx < self.grid_size[1]:
                    defender = self.object_grid[ny, nx]
                    if defender and defender.y is not None and defender.team != soldier.team:
                        win_chance = self.get_param(soldier.team, 'combat_win_chance')                        
                        if random.random() < win_chance:
                            vfx_y, vfx_x = defender.y, defender.x
                            vfx_color = COLOR_MAP[RED_SOLDIER if defender.team == 'red' else BLUE_SOLDIER]
                            self.remove_soldier(defender)
                            self.vfx_manager.create_explosion(vfx_y, vfx_x, vfx_color, self.frame_counter)
                        break # One combat check per frame

    def _update_camera(self):
        """Updates camera zoom and pan targets based on army strengths."""
        self.peak_red_strength = max(self.peak_red_strength, len(self.red_soldiers))
        self.peak_blue_strength = max(self.peak_blue_strength, len(self.blue_soldiers))

        self.losing_team_for_camera = None
        if self.frame_counter > self.config.activation_frame:
            red_strength = len(self.red_soldiers) / self.peak_red_strength
            blue_strength = len(self.blue_soldiers) / self.peak_blue_strength
            if red_strength < self.config.strength_threshold_for_zoom and red_strength < blue_strength:
                self.losing_team_for_camera = 'red'
            elif blue_strength < self.config.strength_threshold_for_zoom and blue_strength < red_strength:
                self.losing_team_for_camera = 'blue'

        if self.losing_team_for_camera:
            self.target_zoom = self.config.zoom_level_on_loser
            center_pos = self.get_army_center(self.losing_team_for_camera)
            if center_pos:
                self.target_cam_center_y, self.target_cam_center_x = center_pos
        else:
            self.target_zoom = 1.0
            self.target_cam_center_y, self.target_cam_center_x = SIM_HEIGHT / 2.0, SIM_WIDTH / 2.0
        
        self.current_zoom += (self.target_zoom - self.current_zoom) * self.config.zoom_speed
        self.current_cam_center_y += (self.target_cam_center_y - self.current_cam_center_y) * self.config.pan_speed
        self.current_cam_center_x += (self.target_cam_center_x - self.current_cam_center_x) * self.config.pan_speed

    def get_viewbox(self):
        """Calculates the rendering viewbox based on current camera state."""
        if self.current_zoom < 0.999:
            vh = int(SIM_HEIGHT * self.current_zoom)
            vw = int(SIM_WIDTH * self.current_zoom)
            vy = int(self.current_cam_center_y - vh / 2.0)
            vx = int(self.current_cam_center_x - vw / 2.0)
            vy = max(0, min(vy, SIM_HEIGHT - vh))
            vx = max(0, min(vx, SIM_WIDTH - vw))
            return (vy, vx, vh, vw)
        return None
    
    def get_army_center(self, team):
        soldiers = self.red_soldiers if team == 'red' else self.blue_soldiers
        count = sum(1 for s in soldiers if s.y is not None)
        if count == 0: return None
        avg_y = sum(s.y for s in soldiers if s.y is not None) / count
        avg_x = sum(s.x for s in soldiers if s.x is not None) / count
        return int(avg_y), int(avg_x)

    def update_render_grid(self):
        """Paints the render_grid based on the current state of all objects."""
        self.render_grid.fill(EMPTY)
        
        red_trail_mask = self.red_pheromone > 0.1
        blue_trail_mask = self.blue_pheromone > 0.1
        
        # Use the masks to "paint" the trails onto the grid.
        # We'll use the base armor colors for a dimmer trail effect.
        self.render_grid[red_trail_mask] = RED_BASE_ARMOR
        self.render_grid[blue_trail_mask] = BLUE_BASE_ARMOR

        for base in self.bases:
            armor_val, core_val = (RED_BASE_ARMOR, RED_BASE_CORE) if base.team == 'red' else (BLUE_BASE_ARMOR, BLUE_BASE_CORE)
            for y, x in base.current_armor_pixels:
                if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]: self.render_grid[y, x] = armor_val
            for y, x in base.current_core_pixels:
                if 0 <= y < self.grid_size[0] and 0 <= x < self.grid_size[1]: self.render_grid[y, x] = core_val
        
        # Draw soldiers (this will draw over the trails at their location)
        self.object_grid.fill(None)
        for s in self.red_soldiers:
            if s.y is not None:
                self.render_grid[s.y, s.x] = RED_SOLDIER
                self.object_grid[s.y, s.x] = s
        for s in self.blue_soldiers:
            if s.y is not None:
                self.render_grid[s.y, s.x] = BLUE_SOLDIER
                self.object_grid[s.y, s.x] = s

    def _handle_audio_cues(self):
        """Check for and react to cues from the audio timeline."""
        cues = self.audio_manager.get_cues_for_frame(self.frame_counter)
        for cue in cues:
            if cue['event'] == 'BEAT_DROP':
                print(f"--- FRAME {self.frame_counter}: BEAT_DROP CUE RECEIVED! ---")
                # Placeholder for future logic:
                # - Change pheromone decay rate
                # - Pulse colors
                # - Change combat probability
                self.vfx_manager.create_shockwave(SIM_HEIGHT/2, SIM_WIDTH/2, (255,255,255))

    def step(self):
        """Advances the simulation by one full frame."""
        self.frame_counter += 1
        for base in self.bases: base.update_spawning(self)
        self._update_soldiers_and_combat()
        self._update_pheromones()
        self._update_camera()
        self.update_render_grid()