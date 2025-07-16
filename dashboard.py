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
        self.config = SimpleNamespace(**config_data['run_settings'], **config_data['engine_settings'], **config_data['spawning_settings'], **config_data['camera_settings'], **config_data['presentation_settings'])
        
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
        self.global_ui_elements, self.selection_ui_elements = {}, {}
        
        self.audio_manager = AudioManager(self.config)
        self.vfx_manager = VFXManager(self.audio_manager)
        self.simulation = Simulation(self.config, self.vfx_manager, self.audio_manager)
        self.renderer = LiveRenderer(self.config)
        
        self.build_ui_layout()
        print("Dashboard initialized.")

    def build_ui_layout(self):
        """Creates all UI panels and buttons using an explicit, robust layout."""
        # --- Right-hand Parameters Panel (This part is correct) ---
        right_panel_rect = pygame.Rect(DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH,
                                    0,
                                    DASHBOARD_RIGHT_PANEL_WIDTH,
                                    DASHBOARD_HEIGHT)
        self.right_params_panel = pygame_gui.elements.UIPanel(
            relative_rect=right_panel_rect, manager=self.ui_manager, object_id='#params_panel'
        )

        # --- Bottom Controls Panel (This part is correct) ---
        bottom_panel_width = DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH
        bottom_panel_rect = pygame.Rect(0,
                                        DASHBOARD_HEIGHT - DASHBOARD_BOTTOM_PANEL_HEIGHT,
                                        bottom_panel_width,
                                        DASHBOARD_BOTTOM_PANEL_HEIGHT)
        self.bottom_controls_panel = pygame_gui.elements.UIPanel(
            relative_rect=bottom_panel_rect, manager=self.ui_manager, object_id='#bottom_panel'
        )

        # --- UI Buttons with Icons ---
        self.play_pause_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 10, 60, 60), text='⏸', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.speed_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(80, 10, 60, 60), text='1x', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.reset_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(150, 10, 60, 60), text='⟲', manager=self.ui_manager, container=self.bottom_controls_panel)

        # --- Global & Selection Panels (INSIDE the right panel) ---
        # THE FIX: We now use explicit sizes and positions for the sub-panels too.
        content_width = DASHBOARD_RIGHT_PANEL_WIDTH - 20 # Width with 10px padding on each side

        # Create the global params container with an explicit size and position
        self.global_params_container = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(10, 10, content_width, 200),
            manager=self.ui_manager,
            container=self.right_params_panel
        )
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="-- GLOBAL SETTINGS --",
                                    manager=self.ui_manager, container=self.global_params_container)
        
        y_offset = 40
        global_params = {'pheromone_decay_rate': (0.95, 1.0), 'pheromone_blur_sigma': (0.0, 2.0), 'combat_win_chance': (0.0, 1.0)}
        for key, (start, end) in global_params.items():
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 220, 25), text=f"{key}:",
                                        manager=self.ui_manager, container=self.global_params_container)
            
            slider_width = content_width - 250 # Calculate slider width to fit
            slider = pygame_gui.elements.UIHorizontalSlider(
                relative_rect=pygame.Rect(230, y_offset, slider_width, 25),
                start_value=getattr(self.config, key), value_range=[start, end],
                manager=self.ui_manager, container=self.global_params_container,
                object_id=f"#{key}_slider"
            )
            self.global_ui_elements[key] = slider
            y_offset += 35

        # Create the selection panel container with an explicit size and position
        self.selection_params_container = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(10, 220, content_width, 400),
            manager=self.ui_manager,
            container=self.right_params_panel
        )
        self.selection_ui_elements['title'] = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="NOTHING SELECTED",
            manager=self.ui_manager, container=self.selection_params_container
        )
        self.selection_params_container.hide()


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
            editable_params = ['spawn_rate', 'units_per_spawn', 'pheromone_deposit_amount', 'pheromone_decay_rate', 'pheromone_blur_sigma']
            for key in editable_params:
                current_value = self.simulation.get_param(base.team, key)
                pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 220, 30), text=f"{key}:", manager=self.ui_manager, container=self.selection_params_container)
                
                entry = pygame_gui.elements.UITextEntryLine(
                    relative_rect=pygame.Rect(230, y_offset, 150, 30), manager=self.ui_manager,
                    container=self.selection_params_container, object_id=f"#base_{key}_entry"
                )
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
                if event.ui_element == self.play_pause_button:
                    self.toggle_pause()
                elif event.ui_element == self.speed_button:
                    self.cycle_speed()
                elif event.ui_element == self.reset_button:
                    self.reset_simulation()
            if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED: self.handle_text_entry(event.ui_element)
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED: self.handle_slider_move(event.ui_element)
            if not ui_consumed_event:
                self.viewport.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    grid_pos = self.viewport.get_grid_pos(event.pos)
                    if grid_pos: self.select_object_at(grid_pos[0], grid_pos[1])
                    elif self.selected_object is not None:
                        self.selected_object = None
                        self.update_selection_panel()
        return time_delta
    
    def toggle_pause(self):
        """Toggles the simulation's paused state."""
        self.is_paused = not self.is_paused
        self.play_pause_button.set_text('▶' if self.is_paused else '⏸')
        print(f"Simulation {'paused' if self.is_paused else 'resumed'}.")

    def cycle_speed(self):
        """Cycles through the available simulation speeds."""
        current_index = self.speed_options.index(self.sim_speed)
        next_index = (current_index + 1) % len(self.speed_options)
        self.sim_speed = self.speed_options[next_index]
        self.speed_button.set_text(f'{self.sim_speed}x')
        print(f"Simulation speed set to {self.sim_speed}x.")

    def reset_simulation(self):
        """Resets the simulation to its initial state."""
        self.simulation = Simulation(self.config, self.vfx_manager, self.audio_manager)
        self.vfx_manager.particles.clear()
        self.selected_object = None
        self.update_selection_panel()
        print("--- Simulation Reset ---")

    def handle_slider_move(self, slider):
        if slider.object_ids[-1].endswith('_slider'):
            key = slider.object_ids[-1].replace('#', '').replace('_slider', '')
            if hasattr(self.config, key):
                setattr(self.config, key, slider.get_current_value())
                if self.selected_object and hasattr(self.selected_object, 'shape_name') and key not in self.selected_object.params:
                    self.update_selection_panel()

    def handle_text_entry(self, entry_line):
        if not self.selected_object or not hasattr(self.selected_object, 'shape_name'): return
        base = self.selected_object
        if entry_line.object_ids[-1].endswith('_entry'):
            key = entry_line.object_ids[-1].replace('#base_', '').replace('_entry', '')
            try:
                new_value = float(entry_line.get_text())
                if key in ['spawn_rate', 'units_per_spawn']: new_value = int(new_value)
                base.params[key] = new_value
                print(f"Set override for {base.team} base: '{key}' to {new_value}")
            except (ValueError, TypeError):
                print(f"Invalid input for '{key}'.")
                self.update_selection_panel()

    def select_object_at(self, world_y, world_x):
        old_selection, clicked_object = self.selected_object, None
        for base in self.simulation.bases:
            if (world_y, world_x) in base.current_core_pixels or (world_y, world_x) in base.current_armor_pixels:
                clicked_object = base; break
        if not clicked_object and 0 <= world_y < SIM_HEIGHT and 0 <= world_x < SIM_WIDTH:
            clicked_object = self.simulation.object_grid[world_y, world_x]
        if old_selection != clicked_object:
            self.selected_object = clicked_object
            self.update_selection_panel()
    
    def update_layout(self):
        """Tells the UI manager the window has resized and updates the viewport rect."""
        screen_w, screen_h = self.screen.get_size()
        self.ui_manager.set_window_resolution((screen_w, screen_h))
        
        # Manually update panel positions and sizes to handle resizing
        self.right_params_panel.set_dimensions((DASHBOARD_RIGHT_PANEL_WIDTH, screen_h))
        self.right_params_panel.set_position((screen_w - DASHBOARD_RIGHT_PANEL_WIDTH, 0))

        bottom_panel_width = screen_w - DASHBOARD_RIGHT_PANEL_WIDTH
        self.bottom_controls_panel.set_dimensions((bottom_panel_width, DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.bottom_controls_panel.set_position((0, screen_h - DASHBOARD_BOTTOM_PANEL_HEIGHT))

        # Calculate viewport rect based on the new, correct absolute positions
        self.viewport.rect.x = 0
        self.viewport.rect.y = 0
        self.viewport.rect.width = self.right_params_panel.get_abs_rect().left
        self.viewport.rect.height = self.bottom_controls_panel.get_abs_rect().top

    def run(self):
        while self.is_running:
            # 1. Process events and get the time since the last frame
            time_delta = self.handle_events()

            # 2. Update all game logic and UI elements
            self.ui_manager.update(time_delta)
            if not self.is_paused:
                for _ in range(self.sim_speed):
                    self.simulation.step()
                    self.vfx_manager.update_effects()

            # 3. Prepare for drawing
            # This calculates the viewport based on the UI panel positions
            self.update_layout() 
            
            # 4. Draw everything in the correct order
            # First, clear the entire screen with a background color
            self.screen.fill((25, 25, 35))
            
            # Second, draw the simulation into its calculated viewport area
            self.renderer.draw(self.screen, self.simulation, self.vfx_manager, self.viewport)
            
            # FINALLY, draw the UI on top of everything else
            self.ui_manager.draw_ui(self.screen)

            # 5. Update the actual display to show the result
            pygame.display.flip()
            
        pygame.quit()
        sys.exit()

if __name__ == '__main__':
    app = Dashboard()
    app.run()