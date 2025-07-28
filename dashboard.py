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
        self.show_pheromones = True
        
        # --- Editor State & Data ---
        self.current_mode = 'SIMULATION'
        self.is_editing_spawns = False
        self.dragged_object = None
        self.drag_type = None
        self.drag_offset = (0, 0)
        self.selected_port_index = -1
        self.shorts_title_text = self.config.question_text
        
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
        # Panels
        right_panel_rect = pygame.Rect(DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH, 0, DASHBOARD_RIGHT_PANEL_WIDTH, DASHBOARD_HEIGHT)
        self.right_panel = pygame_gui.elements.UIPanel(relative_rect=right_panel_rect, manager=self.ui_manager, object_id='#params_panel')

        bottom_panel_rect = pygame.Rect(0, DASHBOARD_HEIGHT - DASHBOARD_BOTTOM_PANEL_HEIGHT, DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH, DASHBOARD_BOTTOM_PANEL_HEIGHT)
        self.bottom_controls_panel = pygame_gui.elements.UIPanel(relative_rect=bottom_panel_rect, manager=self.ui_manager, object_id='#bottom_panel')

        # Bottom Panel Controls
        self.play_pause_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 10, 60, 60), text='⏸', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.speed_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(80, 10, 60, 60), text='1x', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.reset_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(150, 10, 60, 60), text='⟲', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.toggle_pheromones_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(220, 10, 180, 30), text='Pheromones: ON', manager=self.ui_manager, container=self.bottom_controls_panel)
        self.toggle_editor_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(220, 40, 180, 30), text='Enter Editor', manager=self.ui_manager, container=self.bottom_controls_panel)
        
        # Stats Panel
        stats_panel_rect = pygame.Rect(410, 10, 900, 60)
        self.stats_panel = pygame_gui.elements.UIPanel(relative_rect=stats_panel_rect, manager=self.ui_manager, container=self.bottom_controls_panel)
        x_offset = 10; label_width = 430
        for team_name, team_color in [('blue', '#96b4ff'), ('red', '#ff9696')]:
            self.team_stat_labels[team_name] = {
                'title': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 0, label_width, 20), text=f'{team_name.upper()} TEAM', manager=self.ui_manager, container=self.stats_panel, object_id=f'@{team_color}'),
                'agents': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 20, label_width, 20), text='Agents: 0', manager=self.ui_manager, container=self.stats_panel),
                'health': pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 40, label_width, 20), text='Base Health: 0', manager=self.ui_manager, container=self.stats_panel)
            }
            x_offset += label_width + 10
            
        # Right Panel Layout
        content_width = DASHBOARD_RIGHT_PANEL_WIDTH - 20
        
        # 1. Editor Controls
        self.editor_controls_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 10, content_width, 220), manager=self.ui_manager, container=self.right_panel)
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="-- SCENE EDITOR --", manager=self.ui_manager, container=self.editor_controls_container)
        self.editor_add_base_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 40, content_width - 20, 40), text="Add New Base", manager=self.ui_manager, container=self.editor_controls_container)
        self.editor_delete_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 90, content_width - 20, 40), text="Delete Selected Base", manager=self.ui_manager, container=self.editor_controls_container)
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 140, content_width - 20, 30), text="Shorts Title:", manager=self.ui_manager, container=self.editor_controls_container)
        self.editor_title_entry = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect(10, 170, content_width - 20, 40), manager=self.ui_manager, container=self.editor_controls_container)
        self.editor_title_entry.set_text(self.shorts_title_text)

        # 2. Global Sim Settings
        self.global_params_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 10, content_width, 385), manager=self.ui_manager, container=self.right_panel)
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="-- GLOBAL SETTINGS --", manager=self.ui_manager, container=self.global_params_container)
        y_offset_params = 40
        global_params = {'sensor_angle_degrees': (10.0, 45.0), 'sensor_distance': (2.0, 20.0), 'rotation_angle_degrees': (10.0, 45.0), 'combat_chance': (0.0, 1.0), 'pheromone_decay_rate': (0.8, 1.0), 'pheromone_blur_sigma': (0.0, 3.0), 'pheromone_deposit_amount': (0.1, 200.0)}
        for key, (start, end) in global_params.items():
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset_params, 220, 25), text=f"{key}:", manager=self.ui_manager, container=self.global_params_container)
            slider = pygame_gui.elements.UIHorizontalSlider(relative_rect=pygame.Rect(230, y_offset_params, content_width - 250, 25), start_value=getattr(self.config, key), value_range=[start, end], manager=self.ui_manager, container=self.global_params_container, object_id=f"#{key}_slider")
            self.global_ui_elements[key] = slider
            y_offset_params += 35

        # 3. Contextual Selection Panel
        self.selection_params_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 405, content_width, 400), manager=self.ui_manager, container=self.right_panel)
        
        self.toggle_editor_mode(initial=True)

    def toggle_editor_mode(self, initial=False):
        self.is_editing_spawns = False
        
        if not initial:
            if self.current_mode == 'SIMULATION':
                self.current_mode = 'EDITOR'
            else:
                self.current_mode = 'SIMULATION'

        if self.current_mode == 'EDITOR':
            self.is_paused = True
            self.play_pause_button.disable()
            self.toggle_editor_button.set_text('Exit Editor')
            self.global_params_container.hide()
            self.editor_controls_container.show()
            self.selection_params_container.set_relative_position((10, 240))
        else:
            self.current_mode = 'SIMULATION'
            self.play_pause_button.enable()
            self.toggle_editor_button.set_text('Enter Editor')
            self.global_params_container.show()
            self.editor_controls_container.hide()
            self.selection_params_container.set_relative_position((10, 405))
        
        self.update_selection_panel()

    def update_selection_panel(self):
        if self.selection_params_container and self.selection_params_container.get_container():
            for element in self.selection_params_container.get_container().elements[:]:
                element.kill()
        self.selection_ui_elements = {}
        
        if not self.selected_object:
            self.selection_params_container.hide()
            return
        
        self.selection_params_container.show()
        base = self.selected_object
        content_width = self.selection_params_container.get_container().get_rect().width
        y_offset = 5

        title_text = f"BASE: {base.shape_name} ({base.team.upper()})"
        if self.is_editing_spawns: title_text = f"EDITING SPAWNS for {base.shape_name}"
        self.selection_ui_elements['title'] = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 30), text=title_text, manager=self.ui_manager, container=self.selection_params_container)
        y_offset += 35

        if self.current_mode == 'SIMULATION':
            editable_params = ['spawn_rate', 'units_per_spawn']
            for key in editable_params:
                pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 220, 30), text=f"{key}:", manager=self.ui_manager, container=self.selection_params_container)
                entry = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect(230, y_offset, 150, 30), manager=self.ui_manager, container=self.selection_params_container, object_id=f"#base_{key}_entry")
                entry.set_text(str(self.simulation.get_param(base.team, key)))
                self.selection_ui_elements[key] = entry
                y_offset += 40
        else: # EDITOR Mode
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 100, 30), text="Team:", manager=self.ui_manager, container=self.selection_params_container)
            self.selection_ui_elements['team_dropdown'] = pygame_gui.elements.UIDropDownMenu(options_list=['red', 'blue'], starting_option=base.team, relative_rect=pygame.Rect(120, y_offset, content_width - 130, 30), manager=self.ui_manager, container=self.selection_params_container)
            y_offset += 40

            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 100, 30), text="Shape:", manager=self.ui_manager, container=self.selection_params_container)
            self.selection_ui_elements['shape_dropdown'] = pygame_gui.elements.UIDropDownMenu(options_list=['Y', 'N', 'BOX'], starting_option=base.shape_name, relative_rect=pygame.Rect(120, y_offset, content_width - 130, 30), manager=self.ui_manager, container=self.selection_params_container)
            y_offset += 50
            
            btn_text = "Save Spawns" if self.is_editing_spawns else "Modify Spawns"
            self.selection_ui_elements['modify_spawns_button'] = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 40), text=btn_text, manager=self.ui_manager, container=self.selection_params_container)
            if self.is_editing_spawns:
                self.selection_ui_elements['modify_spawns_button'].select()

    def handle_events(self):
        time_delta = self.clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.is_running = False
            ui_consumed_event = self.ui_manager.process_events(event)
            
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == self.play_pause_button: self.toggle_pause()
                elif event.ui_element == self.speed_button: self.cycle_speed()
                elif event.ui_element == self.reset_button: self.reset_simulation()
                elif event.ui_element == self.toggle_pheromones_button: self.toggle_pheromone_display()
                elif event.ui_element == self.toggle_editor_button: self.toggle_editor_mode()
                elif event.ui_element == self.editor_add_base_button: self.simulation.add_new_base()
                elif event.ui_element == self.editor_delete_button: 
                    self.simulation.delete_base(self.selected_object)
                    self.selected_object = None
                    self.update_selection_panel()
                
                if self.selected_object and 'modify_spawns_button' in self.selection_ui_elements:
                    if event.ui_element == self.selection_ui_elements['modify_spawns_button']:
                        self.is_editing_spawns = not self.is_editing_spawns
                        self.update_selection_panel()

            # --- START: THE CRITICAL FIX ---
            # This logic connects the UI elements to their handler functions.
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                self.handle_slider_move(event.ui_element) # This line was missing

            if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
                if event.ui_element == self.editor_title_entry:
                    self.shorts_title_text = event.text
                else: # Route all other text entries to the parameter handler
                    self.handle_text_entry(event.ui_element) # This line was missing/unreachable
            # --- END: THE CRITICAL FIX ---
            
            if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED and self.selected_object:
                if event.ui_element == self.selection_ui_elements.get('team_dropdown'):
                    self.selected_object.update_attributes(team=event.text)
                if event.ui_element == self.selection_ui_elements.get('shape_dropdown'):
                    self.selected_object.update_attributes(shape_name=event.text)
                self.update_selection_panel()

            if not ui_consumed_event:
                self.viewport.handle_event(event)
                if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
                    if self.current_mode == 'EDITOR':
                        self.handle_editor_mouse_events(event)
                    else: # SIMULATION mode
                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            grid_pos = self.viewport.get_grid_pos(event.pos)
                            self.select_object_at(grid_pos[0], grid_pos[1]) if grid_pos else self.select_object_at(None, None)
        return time_delta

    def handle_editor_mouse_events(self, event):
        grid_pos = self.viewport.get_grid_pos(event.pos)
        if not grid_pos: return
        world_y, world_x = grid_pos

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_editing_spawns and self.selected_object:
                for i, (port_y, port_x) in enumerate(self.selected_object.exit_ports):
                    if (world_y - port_y)**2 + (world_x - port_x)**2 < 8**2:
                        self.drag_type, self.dragged_object, self.selected_port_index = 'spawn_port', self.selected_object, i
                        self.drag_offset = (world_y - port_y, world_x - port_x)
                        return
            
            clicked_base = self.simulation.get_base_at(world_y, world_x)
            if clicked_base:
                if self.selected_object != clicked_base:
                    self.selected_object = clicked_base
                    self.is_editing_spawns = False
                    self.update_selection_panel()
                self.drag_type, self.dragged_object = 'base', clicked_base
                self.drag_offset = (world_y - clicked_base.pivot[0], world_x - clicked_base.pivot[1])
            else:
                if not self.is_editing_spawns:
                    self.selected_object = None
                    self.dragged_object = None
                    self.update_selection_panel()

        if event.type == pygame.MOUSEMOTION and self.dragged_object:
            new_y, new_x = world_y - self.drag_offset[0], world_x - self.drag_offset[1]
            if self.drag_type == 'base':
                snapped_y = round(new_y / EDITOR_GRID_SNAP_SIZE) * EDITOR_GRID_SNAP_SIZE
                snapped_x = round(new_x / EDITOR_GRID_SNAP_SIZE) * EDITOR_GRID_SNAP_SIZE
                self.dragged_object.pivot = (int(snapped_y), int(snapped_x))
                self.dragged_object.recalculate_geometry()
            elif self.drag_type == 'spawn_port':
                self.dragged_object.exit_ports[self.selected_port_index] = (int(new_y), int(new_x))

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragged_object, self.drag_type, self.selected_port_index = None, None, -1

    def run(self):
        while self.is_running:
            time_delta = self.handle_events()
            self.ui_manager.update(time_delta)
            
            self.vfx_manager.update_effects()

            if not self.is_paused:
                for _ in range(self.sim_speed):
                    self.simulation.step(self.frame_count)
                    self.frame_count += 1
            
            if self.current_mode == 'EDITOR':
                self.simulation.render_grid.fill(EMPTY)
                self.simulation.draw_bases_to_grid()
            
            self.update_layout()
            self.update_stats_panel()
            
            self.screen.fill((25, 25, 35))
            self.renderer.draw(self.screen, self.simulation, self.vfx_manager, self.viewport, 
                               self.show_pheromones, self.selected_object, 
                               self.is_editing_spawns, self.shorts_title_text)
            self.ui_manager.draw_ui(self.screen)
            
            pygame.display.flip()
            
        pygame.quit()
        sys.exit()

    def select_object_at(self, world_y, world_x):
        clicked_object = self.simulation.get_base_at(world_y, world_x) if world_y is not None else None
        if self.selected_object != clicked_object:
            self.selected_object = clicked_object
            self.is_editing_spawns = False
            self.update_selection_panel()
            
    def reset_simulation(self):
        self.simulation.reset_dynamic_state()
        self.vfx_manager.particles.clear()
        self.frame_count = 0
        if self.current_mode == 'SIMULATION':
            self.is_paused = False
            self.play_pause_button.set_text('⏸')
        print("Simulation reset. Base layout preserved.")

    def update_layout(self):
        screen_w, screen_h = self.screen.get_size()
        self.ui_manager.set_window_resolution((screen_w, screen_h))
        self.right_panel.set_dimensions((DASHBOARD_RIGHT_PANEL_WIDTH, screen_h))
        self.right_panel.set_position((screen_w - DASHBOARD_RIGHT_PANEL_WIDTH, 0))
        bottom_panel_width = screen_w - DASHBOARD_RIGHT_PANEL_WIDTH
        self.bottom_controls_panel.set_dimensions((bottom_panel_width, DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.bottom_controls_panel.set_position((0, screen_h - DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.viewport.rect.x = 0; self.viewport.rect.y = 0
        self.viewport.rect.width = self.right_panel.get_abs_rect().left
        self.viewport.rect.height = self.bottom_controls_panel.get_abs_rect().top
        
    def toggle_pheromone_display(self):
        self.show_pheromones = not self.show_pheromones
        self.toggle_pheromones_button.set_text(f"Pheromones: {'ON' if self.show_pheromones else 'OFF'}")

    def toggle_pause(self):
        if self.current_mode == 'EDITOR': return
        self.is_paused = not self.is_paused
        self.play_pause_button.set_text('▶' if self.is_paused else '⏸')

    def cycle_speed(self):
        current_index = self.speed_options.index(self.sim_speed)
        next_index = (current_index + 1) % len(self.speed_options)
        self.sim_speed = self.speed_options[next_index]
        self.speed_button.set_text(f'{self.sim_speed}x')

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
                if 'rate' in key or 'spawn' in key: new_value = int(new_value)
                self.simulation.team_params_overrides[base.team][key] = new_value
                self.simulation._compile_team_params()
            except (ValueError, TypeError):
                self.update_selection_panel()
    
    def update_stats_panel(self):
        for team_name, labels in self.team_stat_labels.items():
            agent_count = self.simulation.get_team_agent_count(team_name)
            base_health = self.simulation.get_team_base_health(team_name)
            labels['agents'].set_text(f'Agents: {agent_count}')
            labels['health'].set_text(f'Base Health: {base_health}')

if __name__ == '__main__':
    app = Dashboard()
    app.run()