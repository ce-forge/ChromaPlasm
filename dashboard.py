import pygame
import pygame_gui
import sys
import json
from types import SimpleNamespace

from src.constants import *
from src.simulation import Simulation
from src.vfx import VFXManager
from src.audio_manager import AudioManager
from src.live_renderer import LiveRenderer
from src.viewport import Viewport

class Dashboard:
    def __init__(self):
        with open('config.json', 'r') as f: config_data = json.load(f)
        self.config = SimpleNamespace(**config_data['run_settings'], **config_data['engine_settings'],
                                      **config_data['spawning_settings'], **config_data['camera_settings'],
                                      **config_data['presentation_settings'])
        
        self.frame_count = 0
        self.is_recording = False
        
        # --- NEW: State for toggling pheromone visibility ---
        self.show_pheromones = True
        
        self.is_paused = False
        self.sim_speed = 1
        self.speed_options = [1, 2, 4, 8]
        
        pygame.init()
        self.screen = pygame.display.set_mode((DASHBOARD_WIDTH, DASHBOARD_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("ChromaPlasm Dashboard")
        self.clock = pygame.time.Clock()
        self.is_running = True

        self.ui_manager = pygame_gui.UIManager((DASHBOARD_WIDTH, DASHBOARD_HEIGHT), 'theme.json')
        self.viewport = Viewport(pygame.Rect(0, 0, 1, 1))
        self.selected_object = None
        self.global_ui_elements = {}
        self.selection_ui_elements = {}
        self.team_stat_labels = {}
        
        self.audio_manager = AudioManager(self.config)
        self.vfx_manager = VFXManager(self.audio_manager)
        self.simulation = Simulation(self.config, self.vfx_manager, self.audio_manager)
        self.renderer = LiveRenderer(self.config)
        
        self.build_ui_layout()
        print("Dashboard initialized.")

    def build_ui_layout(self):
        right_panel_rect = pygame.Rect(DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH, 0, DASHBOARD_RIGHT_PANEL_WIDTH, DASHBOARD_HEIGHT)
        self.right_params_panel = pygame_gui.elements.UIPanel(relative_rect=right_panel_rect, manager=self.ui_manager, object_id='#params_panel')

        bottom_panel_width = DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH
        bottom_panel_rect = pygame.Rect(0, DASHBOARD_HEIGHT - DASHBOARD_BOTTOM_PANEL_HEIGHT, bottom_panel_width, DASHBOARD_BOTTOM_PANEL_HEIGHT)
        self.bottom_controls_panel = pygame_gui.elements.UIPanel(relative_rect=bottom_panel_rect, manager=self.ui_manager, object_id='#bottom_panel')

        self.play_pause_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 10, 60, 60), text='⏸', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.speed_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(80, 10, 60, 60), text='1x', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.reset_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(150, 10, 60, 60), text='⟲', manager=self.ui_manager, container=self.bottom_controls_panel)
        
        # --- NEW: Button to toggle pheromone display ---
        self.toggle_pheromones_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(220, 10, 180, 30),
            text='Pheromones: ON', manager=self.ui_manager, container=self.bottom_controls_panel
        )
        
        stats_panel_rect = pygame.Rect(410, 10, 900, 60)
        self.stats_panel = pygame_gui.elements.UIPanel(relative_rect=stats_panel_rect, manager=self.ui_manager, container=self.bottom_controls_panel)
        
        x_offset = 10
        label_width = 430
        for team_name, team_color in [('blue', '#96b4ff'), ('red', '#ff9696')]:
            self.team_stat_labels[team_name] = {
                'title': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 0, label_width, 20), text=f'{team_name.upper()} TEAM', manager=self.ui_manager, container=self.stats_panel, object_id=f'@{team_color}'),
                'agents': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 20, label_width, 15), text='Agents: 0', manager=self.ui_manager, container=self.stats_panel),
                'health': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 35, label_width, 15), text='Base Health: 0', manager=self.ui_manager, container=self.stats_panel)
            }
            x_offset += label_width + 10
            
        content_width = DASHBOARD_RIGHT_PANEL_WIDTH - 20 
        self.global_params_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 10, content_width, 280), manager=self.ui_manager, container=self.right_params_panel)
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="-- GLOBAL SETTINGS --", manager=self.ui_manager, container=self.global_params_container)
        
        y_offset_params = 40
        global_params = {
            'sensor_angle_degrees': (10.0, 45.0), 'sensor_distance': (2.0, 20.0), 
            'rotation_angle_degrees': (10.0, 45.0), 'combat_chance': (0.0, 1.0)
        }
        for key, (start, end) in global_params.items():
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset_params, 220, 25), text=f"{key}:", manager=self.ui_manager, container=self.global_params_container)
            slider_width = content_width - 250
            slider = pygame_gui.elements.UIHorizontalSlider(relative_rect=pygame.Rect(230, y_offset_params, slider_width, 25), start_value=getattr(self.config, key), value_range=[start, end], manager=self.ui_manager, container=self.global_params_container, object_id=f"#{key}_slider")
            self.global_ui_elements[key] = slider
            y_offset_params += 35

        self.selection_params_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 290, content_width, 400), manager=self.ui_manager, container=self.right_params_panel)
        self.selection_ui_elements['title'] = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="NOTHING SELECTED", manager=self.ui_manager, container=self.selection_params_container)
        self.selection_params_container.hide()

    def update_stats_panel(self):
        for team_name, labels in self.team_stat_labels.items():
            agent_count = self.simulation.get_team_agent_count(team_name)
            base_health = self.simulation.get_team_base_health(team_name)
            labels['agents'].set_text(f'Agents: {agent_count}')
            labels['health'].set_text(f'Base Health: {base_health}')

    def update_selection_panel(self):
        """Creates, destroys, or updates UI elements based on the current selection."""
        for key, element in list(self.selection_ui_elements.items()):
            if key != 'title':
                element.kill()
                del self.selection_ui_elements[key]
        
        if self.selected_object and hasattr(self.selected_object, 'shape_name'):
            self.selection_params_container.show()
            base = self.selected_object
            self.selection_ui_elements['title'].set_text(f"BASE: {base.shape_name} ({base.team.upper()})")
            y_offset = 40
            editable_params = [
                'spawn_rate', 'units_per_spawn', 'pheromone_deposit_amount', 
                'sensor_angle_degrees', 'sensor_distance', 'rotation_angle_degrees'
            ]
            for key in editable_params:
                current_value = self.simulation.get_param(base.team, key)
                pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 220, 30), text=f"{key}:", manager=self.ui_manager, container=self.selection_params_container)
                entry = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect(230, y_offset, 150, 30), manager=self.ui_manager, container=self.selection_params_container, object_id=f"#base_{key}_entry")
                entry.set_text(f"{current_value:.3f}" if isinstance(current_value, float) else str(current_value))
                self.selection_ui_elements[key] = entry
                y_offset += 40
        else:
            self.selection_params_container.hide()   

    def handle_events(self):
        time_delta = self.clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.is_running = False
            ui_consumed_event = self.ui_manager.process_events(event)
            
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == self.play_pause_button: self.toggle_pause()
                elif event.ui_element == self.speed_button: self.cycle_speed()
                elif event.ui_element == self.reset_button: self.reset_simulation()
                # --- NEW: Handle clicks on the new button ---
                elif event.ui_element == self.toggle_pheromones_button: self.toggle_pheromone_display()

            if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED: self.handle_text_entry(event.ui_element)
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED: self.handle_slider_move(event.ui_element)
            
            if not ui_consumed_event:
                self.viewport.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    grid_pos = self.viewport.get_grid_pos(event.pos)
                    if grid_pos: self.select_object_at(grid_pos[0], grid_pos[1])
                    else:
                        self.selected_object = None
                        self.update_selection_panel()
        return time_delta
    
    def toggle_pheromone_display(self):
        self.show_pheromones = not self.show_pheromones
        new_text = "Pheromones: ON" if self.show_pheromones else "Pheromones: OFF"
        self.toggle_pheromones_button.set_text(new_text)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.play_pause_button.set_text('▶' if self.is_paused else '⏸')

    def cycle_speed(self):
        current_index = self.speed_options.index(self.sim_speed)
        next_index = (current_index + 1) % len(self.speed_options)
        self.sim_speed = self.speed_options[next_index]
        self.speed_button.set_text(f'{self.sim_speed}x')

    def reset_simulation(self):
        # Re-initialize the simulation object to reset everything
        self.simulation = Simulation(self.config, self.vfx_manager, self.audio_manager)
        self.vfx_manager.particles.clear()
        self.selected_object = None
        self.update_selection_panel()
        self.frame_count = 0 

    def handle_slider_move(self, slider):
        if slider.object_ids[-1].endswith('_slider'):
            key = slider.object_ids[-1].replace('#', '').replace('_slider', '')
            if hasattr(self.config, key):
                setattr(self.config, key, slider.get_current_value())
                self.simulation._compile_team_params()

    def handle_text_entry(self, entry_line):
        if not self.selected_object or not hasattr(self.selected_object, 'shape_name'): return
        base = self.selected_object
        if entry_line.object_ids[-1].endswith('_entry'):
            key = entry_line.object_ids[-1].replace('#base_', '').replace('_entry', '')
            try:
                new_value = float(entry_line.get_text())
                if 'degrees' not in key: new_value = int(new_value)
                self.simulation.team_params_overrides[base.team][key] = new_value
                self.simulation._compile_team_params()
                print(f"Set override for {base.team} base: '{key}' to {new_value}")
            except (ValueError, TypeError):
                self.update_selection_panel()

    def select_object_at(self, world_y, world_x):
        clicked_object = None
        for base in self.simulation.bases:
            if (world_y, world_x) in base.current_core_pixels or (world_y, world_x) in base.current_armor_pixels:
                clicked_object = base; break
        if self.selected_object != clicked_object:
            self.selected_object = clicked_object
            self.update_selection_panel()
    
    def update_layout(self):
        screen_w, screen_h = self.screen.get_size()
        self.ui_manager.set_window_resolution((screen_w, screen_h))
        self.right_params_panel.set_dimensions((DASHBOARD_RIGHT_PANEL_WIDTH, screen_h))
        self.right_params_panel.set_position((screen_w - DASHBOARD_RIGHT_PANEL_WIDTH, 0))
        bottom_panel_width = screen_w - DASHBOARD_RIGHT_PANEL_WIDTH
        self.bottom_controls_panel.set_dimensions((bottom_panel_width, DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.bottom_controls_panel.set_position((0, screen_h - DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.viewport.rect.x = 0
        self.viewport.rect.y = 0
        self.viewport.rect.width = self.right_params_panel.get_abs_rect().left
        self.viewport.rect.height = self.bottom_controls_panel.get_abs_rect().top

    def run(self):
        while self.is_running:
            time_delta = self.handle_events()
            
            if self.is_recording and self.frame_count >= self.config.total_frames:
                self.is_running = False; continue

            self.ui_manager.update(time_delta)
            
            if not self.is_paused:
                for _ in range(self.sim_speed):
                    self.simulation.step()
                    self.vfx_manager.update_effects()
                    self.frame_count += 1
            
            self.update_layout()
            self.update_stats_panel()
            
            self.screen.fill((25, 25, 35))
            # --- MODIFIED: Pass the new state flag to the renderer ---
            self.renderer.draw(self.screen, self.simulation, self.vfx_manager, self.viewport, self.show_pheromones)
            self.ui_manager.draw_ui(self.screen)
            
            pygame.display.flip()
            
        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    app = Dashboard()
    app.run()