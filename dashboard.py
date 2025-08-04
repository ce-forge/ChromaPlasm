import pygame
import pygame_gui
import sys
import json
from types import SimpleNamespace
import numpy as np
from src.constants import *
from src.simulation import Simulation
from src.vfx import VFXManager
from src.audio_manager import AudioManager
from src.live_renderer import LiveRenderer
from src.viewport import Viewport

class Dashboard:
    def __init__(self):
        with open('config.json', 'r') as f: config_data = json.load(f)
        self.config = SimpleNamespace(**config_data['run_settings'], **config_data['engine_settings'], **config_data['spawning_settings'], **config_data['camera_settings'])
        self.presentation_params = SimpleNamespace(**config_data['presentation_settings'])
        
        pygame.init()
        self.screen = pygame.display.set_mode((DASHBOARD_WIDTH, DASHBOARD_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("ChromaPlasm Dashboard")
        self.clock = pygame.time.Clock()
        
        self.frame_count = 0
        self.is_running = True
        self.is_paused = False
        self.sim_speed = 1
        self.speed_options = [1, 2, 4, 8]
        self.show_pheromones = True
        self.shorts_title_text = self.presentation_params.question_text
        
        self.current_mode = 'SIMULATION'
        self.is_editing_spawns = False
        self.editor_port_mode = 'DRAG'
        
        self.selected_object = None
        self.dragged_object = None
        self.drag_type = None
        self.selected_port_index = -1
        self.drag_offset = (0, 0)
        self.drag_update_counter = 0
        self.DRAG_UPDATE_THRESHOLD = 50

        self.ui_manager = pygame_gui.UIManager((DASHBOARD_WIDTH, DASHBOARD_HEIGHT), 'theme.json')
        self.viewport = Viewport(pygame.Rect(0, 0, 1, 1))
        self.ui_elements = {'global': {}, 'selection': {}, 'alliance': {}, 'presentation': {}}
        self.alliance_map = list(range(len(TEAMS)))
        
        self.audio_manager = AudioManager(self.config)
        self.vfx_manager = VFXManager(self.audio_manager)
        self.simulation = Simulation(self.config, self.vfx_manager, self.audio_manager)
        self.renderer = LiveRenderer(self.presentation_params)
        
        self.build_ui_layout()
        self._refresh_dynamic_panels()
        print("Dashboard initialized.")

    def _create_parameter_row(self, parent, y_offset, name, value_range, current_value, is_int=False):
        container_width = parent.get_container().get_rect().width
        label_text = name.replace('_', ' ').title()
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 200, 25), text=label_text, manager=self.ui_manager, container=parent)
        slider = pygame_gui.elements.UIHorizontalSlider(relative_rect=pygame.Rect(210, y_offset, container_width - 290, 25), start_value=current_value, value_range=value_range, manager=self.ui_manager, container=parent, object_id=f"#{name}_slider")
        value_label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(container_width - 70, y_offset, 60, 25), text=str(int(current_value)) if is_int else f"{current_value:.2f}", manager=self.ui_manager, container=parent)
        return slider, value_label

    def build_ui_layout(self):
        self.right_panel = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH, 0, DASHBOARD_RIGHT_PANEL_WIDTH, DASHBOARD_HEIGHT), manager=self.ui_manager, object_id='#params_panel')
        self.bottom_panel = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(0, DASHBOARD_HEIGHT - DASHBOARD_BOTTOM_PANEL_HEIGHT, DASHBOARD_WIDTH - DASHBOARD_RIGHT_PANEL_WIDTH, DASHBOARD_BOTTOM_PANEL_HEIGHT), manager=self.ui_manager, object_id='#bottom_panel')
        content_width = self.right_panel.get_container().get_rect().width

        self.play_pause_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 10, 90, 60), text='PAUSE', manager=self.ui_manager, container=self.bottom_panel)
        self.speed_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(110, 10, 60, 60), text='1x', manager=self.ui_manager, container=self.bottom_panel)
        self.reset_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(180, 10, 90, 60), text='RESET', manager=self.ui_manager, container=self.bottom_panel)
        self.toggle_pheromones_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(280, 10, 180, 30), text='Pheromones: ON', manager=self.ui_manager, container=self.bottom_panel)
        self.toggle_editor_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(280, 40, 180, 30), text='Enter Editor', manager=self.ui_manager, container=self.bottom_panel)
        self.stats_container = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(470, 10, 840, 60), manager=self.ui_manager, container=self.bottom_panel)

        self.sim_ui_group = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 10, content_width, -1), manager=self.ui_manager, container=self.right_panel)
        self.editor_ui_group = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 10, content_width, 270), manager=self.ui_manager, container=self.right_panel)
        self.selection_panel = pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, 440, content_width, 400), manager=self.ui_manager, container=self.right_panel)

        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 5, content_width - 20, 30), text="Scene Editor", manager=self.ui_manager, container=self.editor_ui_group)
        self.editor_add_base_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 40, content_width - 20, 40), text="Add New Base", manager=self.ui_manager, container=self.editor_ui_group)
        self.editor_delete_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 90, content_width - 20, 40), text="Delete Selected Base", manager=self.ui_manager, container=self.editor_ui_group)
        self.save_layout_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, 140, content_width - 20, 40), text="Save Scene Layout", manager=self.ui_manager, container=self.editor_ui_group)
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, 190, content_width - 20, 30), text="Shorts Title:", manager=self.ui_manager, container=self.editor_ui_group)
        self.editor_title_entry = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect(10, 220, content_width - 20, 40), manager=self.ui_manager, container=self.editor_ui_group)
        
        self.toggle_editor_mode(initial=True)

    def _refresh_dynamic_panels(self):
        content_width = self.right_panel.get_container().get_rect().width
        for element in self.sim_ui_group.get_container().elements[:]: element.kill()
        self.ui_elements['alliance'] = {}
        self.ui_elements['global'] = {}
        self.ui_elements['presentation'] = {}
        y_offset = 10
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 30), text="Alliance Settings", manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 35
        self.ui_elements['alliance']['ffa_button'] = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, y_offset, 180, 30), text="Free For All", manager=self.ui_manager, container=self.sim_ui_group)
        self.ui_elements['alliance']['2_teams_button'] = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(200, y_offset, 180, 30), text="Two Teams", manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 40
        
        active_team_ids = sorted(list(set(base.team_id for base in self.simulation.bases)))
        alliance_group_options = [f"Group {i+1}" for i in range(len(TEAMS))]
        for team_id in active_team_ids:
            team = TEAMS[team_id]
            hex_color = '#%02x%02x%02x' % team['color']
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 150, 25), text=team['name'], manager=self.ui_manager, container=self.sim_ui_group, object_id=f'@{hex_color}')
            dropdown = pygame_gui.elements.UIDropDownMenu(options_list=alliance_group_options, starting_option=f"Group {self.alliance_map[team_id] + 1}", relative_rect=pygame.Rect(170, y_offset, 210, 25), manager=self.ui_manager, container=self.sim_ui_group)
            self.ui_elements['alliance'][f'team_{team_id}_dropdown'] = dropdown
            y_offset += 30
        
        y_offset += 10
        pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 2), manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 10
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, content_width-20, 30), text="Global Simulation Parameters", manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 35
        
        sim_params = { 'sensor_angle_degrees': (10.0, 90.0), 'sensor_distance': (2.0, 50.0), 'rotation_angle_degrees': (5.0, 90.0), 'combat_chance': (0.0, 1.0), 'pheromone_decay_rate': (0.8, 1.0), 'pheromone_blur_sigma': (0.0, 5.0), 'pheromone_deposit_amount': (10.0, 300.0), 'enemy_sense_radius': (10.0, 100.0), 'base_attack_radius': (10.0, 150.0), 'ai_update_interval': (1, 30, True) }
        for name, p_range in sim_params.items():
            is_int = len(p_range) == 3 and p_range[2]
            slider, label = self._create_parameter_row(self.sim_ui_group, y_offset, name, (p_range[0], p_range[1]), getattr(self.config, name), is_int)
            self.ui_elements['global'][name] = {'slider': slider, 'label': label, 'is_int': is_int}
            y_offset += 35
        
        y_offset += 10
        pygame_gui.elements.UIPanel(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 2), manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 10
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, content_width-20, 30), text="Presentation Tuning", manager=self.ui_manager, container=self.sim_ui_group)
        y_offset += 35

        presentation_sliders = {'agent_size': (0.5, 3.0), 'glow_intensity': (0, 255, True), 'trail_fade_rate': (0, 50, True)}
        for name, p_range in presentation_sliders.items():
            is_int = len(p_range) == 3 and p_range[2]
            slider, label = self._create_parameter_row(self.sim_ui_group, y_offset, name, (p_range[0], p_range[1]), getattr(self.presentation_params, name), is_int)
            self.ui_elements['presentation'][name] = {'slider': slider, 'label': label, 'is_int': is_int}
            y_offset += 35

        self.sim_ui_group.set_dimensions((content_width, y_offset))
        self.selection_panel.set_relative_position((10, self.sim_ui_group.relative_rect.bottom + 10))

    def _update_simulation_alliances(self):
        self.simulation.alliance_map = np.array(self.alliance_map, dtype=np.int32)
        
    def _update_alliance_dropdowns(self):
        alliance_group_options = [f"Group {i+1}" for i in range(len(TEAMS))]
        for team_id, alliance_id in enumerate(self.alliance_map):
            dropdown = self.ui_elements['alliance'].get(f'team_{team_id}_dropdown')
            if dropdown:
                dropdown.rebuild(alliance_group_options, f"Group {alliance_id + 1}")
    
    def toggle_editor_mode(self, initial=False):
        if not initial:
            if self.current_mode == 'SIMULATION': self.current_mode = 'EDITOR'
            else: self.current_mode = 'SIMULATION'
        if self.current_mode == 'EDITOR':
            self.is_paused = True
            self.play_pause_button.disable()
            self.toggle_editor_button.set_text('Exit Editor')
            self.sim_ui_group.hide()
            self.editor_ui_group.show()
            self.selection_panel.set_relative_position((10, 290))
        else:
            self.play_pause_button.enable()
            self.toggle_editor_button.set_text('Enter Editor')
            self.sim_ui_group.show()
            self.editor_ui_group.hide()
            self._refresh_dynamic_panels()
            self.is_editing_spawns = False
            self.editor_port_mode = 'DRAG'
        self.update_selection_panel()

    def update_selection_panel(self):
        for element in self.selection_panel.get_container().elements[:]: element.kill()
        self.ui_elements['selection'] = {}
        if not self.selected_object:
            self.selection_panel.hide()
            return
        self.selection_panel.show()
        base = self.selected_object
        container = self.selection_panel
        content_width = container.get_container().get_rect().width
        y_offset = 5
        pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 30), text="Selected Base Properties", manager=self.ui_manager, container=container)
        y_offset += 35
        def create_entry(name, value, y_pos):
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_pos, 160, 30), text=name.replace('_', ' ').title(), manager=self.ui_manager, container=container)
            entry = pygame_gui.elements.UITextEntryLine(relative_rect=pygame.Rect(180, y_pos, content_width - 190, 30), manager=self.ui_manager, container=container, object_id=f"#{name}_entry")
            entry.set_text(str(value))
            self.ui_elements['selection'][name] = entry
            return entry
        if self.current_mode == 'EDITOR':
            team_names = [team['name'] for team in TEAMS]
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 160, 30), text="Team", manager=self.ui_manager, container=container)
            self.ui_elements['selection']['team_dropdown'] = pygame_gui.elements.UIDropDownMenu(options_list=team_names, starting_option=base.team_name, relative_rect=pygame.Rect(180, y_offset, content_width - 190, 30), manager=self.ui_manager, container=container)
            y_offset += 40
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 160, 30), text="Shape", manager=self.ui_manager, container=container)
            self.ui_elements['selection']['shape_dropdown'] = pygame_gui.elements.UIDropDownMenu(options_list=['Y', 'N', 'BOX', 'ARROWHEAD'], starting_option=base.shape_name, relative_rect=pygame.Rect(180, y_offset, content_width - 190, 30), manager=self.ui_manager, container=container)
            y_offset += 40
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(10, y_offset, 160, 30), text="Size", manager=self.ui_manager, container=container)
            size_map = {0: 4.0, 1: 6.0, 2: 8.0, 3: 10.0}
            text_map = {0: "50%", 1: "75%", 2: "100%", 3: "125%"}
            val_to_scale = {v: k for k, v in size_map.items()}
            current_val = val_to_scale.get(base.scale, 2)
            slider = pygame_gui.elements.UIHorizontalSlider(relative_rect=pygame.Rect(180, y_offset, content_width - 270, 30), start_value=current_val, value_range=(0, 3), manager=self.ui_manager, container=container, object_id="#size_slider")
            label = pygame_gui.elements.UILabel(relative_rect=pygame.Rect(content_width - 80, y_offset, 70, 30), text=text_map.get(current_val, "Custom"), manager=self.ui_manager, container=container)
            self.ui_elements['selection']['size'] = {'slider': slider, 'label': label, 'map': size_map, 'text_map': text_map}
            y_offset += 40
            create_entry('core_thickness', base.core_thickness, y_offset)
            y_offset += 40
            create_entry('armor_thickness', base.armor_thickness, y_offset)
            y_offset += 50
            btn_text = "Return to Base Edit" if self.is_editing_spawns else "Modify Spawn Ports"
            self.ui_elements['selection']['modify_spawns_button'] = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 40), text=btn_text, manager=self.ui_manager, container=container)
            y_offset += 45
            if self.is_editing_spawns:
                self.ui_elements['selection']['modify_spawns_button'].select()
                button_width = (content_width - 30) // 2
                add_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, y_offset, button_width, 30), text="Add Port", manager=self.ui_manager, container=container)
                del_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(20 + button_width, y_offset, button_width, 30), text="Delete Port", manager=self.ui_manager, container=container)
                self.ui_elements['selection']['add_port_button'] = add_btn
                self.ui_elements['selection']['delete_port_button'] = del_btn
                y_offset += 35
                if self.editor_port_mode == 'ADD': add_btn.select()
                elif self.editor_port_mode == 'DELETE': del_btn.select()
                save_btn = pygame_gui.elements.UIButton(relative_rect=pygame.Rect(10, y_offset, content_width - 20, 30), text=f"Save '{base.shape_name}' Template", manager=self.ui_manager, container=container)
                self.ui_elements['selection']['save_ports_button'] = save_btn
        else:
            create_entry('spawn_rate', self.simulation.get_param(base.team_id, 'spawn_rate'), y_offset)
            y_offset += 40
            create_entry('units_per_spawn', self.simulation.get_param(base.team_id, 'units_per_spawn'), y_offset)

    def handle_events(self):
        time_delta = self.clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            
            ui_consumed_event = self.ui_manager.process_events(event)

            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == self.play_pause_button: self.toggle_pause()
                elif event.ui_element == self.speed_button: self.cycle_speed()
                elif event.ui_element == self.reset_button: self.reset_simulation()
                elif event.ui_element == self.toggle_pheromones_button: self.toggle_pheromone_display()
                elif event.ui_element == self.toggle_editor_button: self.toggle_editor_mode()
                elif event.ui_element == self.save_layout_button: self.save_layout_to_file()
                elif event.ui_element == self.editor_add_base_button:
                    new_base = self.simulation.add_new_base()
                    self.selected_object = new_base
                    self.is_editing_spawns = False
                    self.editor_port_mode = 'DRAG'
                    self.update_selection_panel()
                elif event.ui_element == self.editor_delete_button:
                    self.simulation.delete_base(self.selected_object)
                    self.selected_object = None
                    self.update_selection_panel()
                elif event.ui_element == self.ui_elements['alliance'].get('ffa_button'):
                    self.alliance_map = list(range(len(TEAMS)))
                    self._refresh_dynamic_panels()
                    self._update_simulation_alliances()
                elif event.ui_element == self.ui_elements['alliance'].get('2_teams_button'):
                    self.alliance_map = [i % 2 for i in range(len(TEAMS))]
                    self._refresh_dynamic_panels()
                    self._update_simulation_alliances()                
                
                if self.selected_object:
                    if event.ui_element == self.ui_elements['selection'].get('save_ports_button'): self.save_port_layout_as_default()
                    if event.ui_element == self.ui_elements['selection'].get('modify_spawns_button'):
                        self.is_editing_spawns = not self.is_editing_spawns
                        self.editor_port_mode = 'DRAG'
                        self.update_selection_panel()
                    if self.is_editing_spawns:
                        if event.ui_element == self.ui_elements['selection'].get('add_port_button'):
                            self.editor_port_mode = 'DRAG' if self.editor_port_mode == 'ADD' else 'ADD'
                            self.update_selection_panel()
                        elif event.ui_element == self.ui_elements['selection'].get('delete_port_button'):
                            self.editor_port_mode = 'DRAG' if self.editor_port_mode == 'DELETE' else 'DELETE'
                            self.update_selection_panel()

            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                self.handle_slider_move(event.ui_element)

            if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
                if event.ui_element == self.editor_title_entry:
                    self.shorts_title_text = event.text
                else:
                    self.handle_text_entry(event.ui_element)

            if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                is_alliance_dropdown = False
                for team_id in range(len(TEAMS)):
                    if event.ui_element == self.ui_elements['alliance'].get(f'team_{team_id}_dropdown'):
                        self.alliance_map[team_id] = int(event.text.split(' ')[1]) - 1
                        self._update_simulation_alliances()
                        is_alliance_dropdown = True
                        break
                if not is_alliance_dropdown and self.selected_object:
                    if event.ui_element == self.ui_elements['selection'].get('team_dropdown'):
                        self.selected_object.update_attributes(team_name=event.text)
                    if event.ui_element == self.ui_elements['selection'].get('shape_dropdown'):
                        self.selected_object.update_attributes(shape_name=event.text)
                    self.update_selection_panel()

            if not ui_consumed_event:
                self.viewport.handle_event(event)
                if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
                    if self.current_mode == 'EDITOR':
                        self.handle_editor_mouse_events(event)
                    else:
                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            grid_pos = self.viewport.get_grid_pos(event.pos)
                            self.select_object_at(grid_pos[0], grid_pos[1]) if grid_pos else self.select_object_at(None, None)
        return time_delta

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
            self.renderer.draw(self.screen, self.simulation, self.vfx_manager, self.viewport, self.show_pheromones, self.selected_object, self.is_editing_spawns, self.shorts_title_text)
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
        for base in self.simulation.bases:
            base.recalculate_geometry(final_calculation=True, regenerate_ports=False)
            base.last_damage_frame = -100 
        self.simulation.reset_dynamic_state()
        self.vfx_manager.particles.clear()
        self.frame_count = 0
        if self.current_mode == 'SIMULATION':
            self.is_paused = False
            self.play_pause_button.set_text('PAUSE')
        print("Simulation reset.")

    def update_layout(self):
        screen_w, screen_h = self.screen.get_size()
        self.ui_manager.set_window_resolution((screen_w, screen_h))
        self.right_panel.set_dimensions((DASHBOARD_RIGHT_PANEL_WIDTH, screen_h))
        self.right_panel.set_position((screen_w - DASHBOARD_RIGHT_PANEL_WIDTH, 0))
        bottom_panel_width = screen_w - DASHBOARD_RIGHT_PANEL_WIDTH
        self.bottom_panel.set_dimensions((bottom_panel_width, DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.bottom_panel.set_position((0, screen_h - DASHBOARD_BOTTOM_PANEL_HEIGHT))
        self.viewport.rect.x = 0
        self.viewport.rect.y = 0
        self.viewport.rect.width = self.right_panel.get_abs_rect().left
        self.viewport.rect.height = self.bottom_panel.get_abs_rect().top

    def toggle_pheromone_display(self):
        self.show_pheromones = not self.show_pheromones
        self.toggle_pheromones_button.set_text(f"Pheromones: {'ON' if self.show_pheromones else 'OFF'}")

    def toggle_pause(self):
        if self.current_mode == 'EDITOR':
            return
        self.is_paused = not self.is_paused
        self.play_pause_button.set_text('PLAY' if self.is_paused else 'PAUSE')

    def cycle_speed(self):
        current_index = self.speed_options.index(self.sim_speed)
        next_index = (current_index + 1) % len(self.speed_options)
        self.sim_speed = self.speed_options[next_index]
        self.speed_button.set_text(f'{self.sim_speed}x')

    def handle_slider_move(self, slider):
        slider_id = slider.object_ids[-1].replace('#', '').replace('_slider', '')
        current_value = slider.get_current_value()
        if slider_id in self.ui_elements['global']:
            param = self.ui_elements['global'][slider_id]
            if param['is_int']: param['label'].set_text(str(int(current_value)))
            else: param['label'].set_text(f"{current_value:.2f}")
            if hasattr(self.config, slider_id):
                setattr(self.config, slider_id, current_value)
                self.simulation._compile_team_params()
        elif slider_id in self.ui_elements['presentation']:
            param = self.ui_elements['presentation'][slider_id]
            if param['is_int']: param['label'].set_text(str(int(current_value)))
            else: param['label'].set_text(f"{current_value:.2f}")
            if hasattr(self.presentation_params, slider_id):
                setattr(self.presentation_params, slider_id, current_value)
        elif slider_id == 'size' and self.selected_object:
            param = self.ui_elements['selection']['size']
            size_val = int(current_value)
            new_scale = param['map'].get(size_val, 1.0)
            param['label'].set_text(param['text_map'].get(size_val, "Custom"))
            self.selected_object.scale = new_scale
            self.selected_object.recalculate_geometry(final_calculation=False, regenerate_ports=False)

    def handle_text_entry(self, entry_line):
        if not self.selected_object:
            return
        base = self.selected_object
        entry_id = entry_line.object_ids[-1].replace('#', '').replace('_entry', '')
        try:
            if entry_id in ['spawn_rate', 'units_per_spawn']:
                new_value = int(float(entry_line.get_text()))
                if base.team_id not in self.simulation.team_params_overrides:
                    self.simulation.team_params_overrides[base.team_id] = {}
                self.simulation.team_params_overrides[base.team_id][entry_id] = new_value
                self.simulation._compile_team_params()
            elif entry_id in ['core_thickness', 'armor_thickness']:
                new_value = max(1, int(float(entry_line.get_text())))
                setattr(base, entry_id, new_value)
                base.recalculate_geometry(final_calculation=False, regenerate_ports=False)
        except (ValueError, TypeError):
            self.update_selection_panel()
    
    def update_stats_panel(self):
        for element in self.stats_container.get_container().elements[:]:
            element.kill()
        active_teams = sorted(list(set(base.team_name for base in self.simulation.bases)))
        if not active_teams: return
        num_teams = len(active_teams)
        container_width = self.stats_container.get_container().get_rect().width
        block_width = (container_width - (10 * (num_teams + 1))) / num_teams if num_teams > 0 else container_width - 20
        x_offset = 10
        for team_name in active_teams:
            agent_count = self.simulation.get_team_agent_count(team_name)
            base_health = self.simulation.get_team_base_health(team_name)
            team_color_hex = '#ffffff'
            for team_data in TEAMS:
                if team_data['name'].lower() == team_name.lower():
                    team_color_hex = '#%02x%02x%02x' % team_data['color']
                    break
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 0, block_width, 20), text=f'{team_name.upper()}', manager=self.ui_manager, container=self.stats_container, object_id=f'@{team_color_hex}')
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 20, block_width, 20), text=f'Agents: {agent_count}', manager=self.ui_manager, container=self.stats_container)
            pygame_gui.elements.UILabel(relative_rect=pygame.Rect(x_offset, 40, block_width, 20), text=f'Health: {base_health}', manager=self.ui_manager, container=self.stats_container)
            x_offset += block_width + 10

    def save_layout_to_file(self):
        layout_data = {"initial_layout": []}
        for base in self.simulation.bases:
            base_config = {"team": base.team_name, "shape_name": base.shape_name, "pivot": list(base.pivot), "scale": base.scale, "core_thickness": base.core_thickness, "armor_thickness": base.armor_thickness, "exit_ports": [list(p) for p in base.exit_ports]}
            layout_data["initial_layout"].append(base_config)
        try:
            with open('base_layouts.json', 'w') as f:
                json.dump(layout_data, f, indent=4)
            print("SUCCESS: Current base layout saved as default.")
        except Exception as e:
            print(f"ERROR: Could not save layout to 'base_layouts.json'. {e}")
            
    def save_port_layout_as_default(self):
        if not self.selected_object:
            return
        base = self.selected_object
        shape_name = base.shape_name
        template_data = {"exit_ports": [list(port) for port in base._relative_exit_ports], "scale": base.scale, "core_thickness": base.core_thickness, "armor_thickness": base.armor_thickness}
        try:
            with open('base_layouts.json', 'r+') as f:
                data = json.load(f)
                if 'shape_templates' not in data: data['shape_templates'] = {}
                data['shape_templates'][shape_name] = template_data
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
            print(f"SUCCESS: Default template for shape '{shape_name}' saved.")
        except Exception as e:
            print(f"ERROR: Could not save shape template. {e}")

    def handle_editor_mouse_events(self, event):
        grid_pos = self.viewport.get_grid_pos(event.pos)
        if not grid_pos:
            return
        world_y, world_x = grid_pos

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_editing_spawns and self.selected_object:
                base = self.selected_object
                if self.editor_port_mode == 'DELETE':
                    port_to_delete_idx = -1
                    for i, (port_y, port_x) in enumerate(base.exit_ports):
                        if (world_y - port_y)**2 + (world_x - port_x)**2 < 8**2:
                            port_to_delete_idx = i
                            break
                    if port_to_delete_idx != -1:
                        base._relative_exit_ports.pop(port_to_delete_idx)
                    return
                elif self.editor_port_mode == 'ADD':
                    if (world_y, world_x) not in base.all_base_pixels:
                        rel_y, rel_x = world_y - base.pivot[0], world_x - base.pivot[1]
                        base._relative_exit_ports.append((rel_y, rel_x))
                    return
                
                for i, (port_y, port_x) in enumerate(base.exit_ports):
                    if (world_y - port_y)**2 + (world_x - port_x)**2 < 8**2:
                        self.drag_type = 'spawn_port'
                        self.dragged_object = base
                        self.selected_port_index = i
                        self.drag_offset = (world_y - port_y, world_x - port_x)
                        return

            clicked_base = self.simulation.get_base_at(world_y, world_x)
            if clicked_base:
                if self.selected_object != clicked_base:
                    self.selected_object = clicked_base
                    self.is_editing_spawns = False
                    self.editor_port_mode = 'DRAG'
                    self.update_selection_panel()
                self.drag_type = 'base'
                self.dragged_object = clicked_base
                self.drag_offset = (world_y - clicked_base.pivot[0], world_x - clicked_base.pivot[1])
                self.drag_update_counter = 0 # NEW: Reset counter on new drag
            else:
                if not self.is_editing_spawns:
                    self.selected_object = None
                    self.dragged_object = None
                    self.update_selection_panel()

        if event.type == pygame.MOUSEMOTION and self.dragged_object:
            if self.drag_type == 'base':
                # --- THIS IS THE CORE FIX ---
                # 1. Always update the position for a smooth feel
                new_y, new_x = world_y - self.drag_offset[0], world_x - self.drag_offset[1]
                snapped_y = round(new_y / EDITOR_GRID_SNAP_SIZE) * EDITOR_GRID_SNAP_SIZE
                snapped_x = round(new_x / EDITOR_GRID_SNAP_SIZE) * EDITOR_GRID_SNAP_SIZE
                self.dragged_object.pivot = (int(snapped_y), int(snapped_x))
                
                # 2. Only run the slow recalculation periodically
                self.drag_update_counter += 1
                if self.drag_update_counter >= self.DRAG_UPDATE_THRESHOLD:
                    self.dragged_object.recalculate_preview()
                    self.drag_update_counter = 0 # Reset counter after update
            
            elif self.drag_type == 'spawn_port':
                base = self.dragged_object
                new_port_y, new_port_x = world_y - self.drag_offset[0], world_x - self.drag_offset[1]
                rel_y, rel_x = new_port_y - base.pivot[0], new_port_x - base.pivot[1]
                base._relative_exit_ports[self.selected_port_index] = (int(rel_y), int(rel_x))

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drag_type == 'base' and self.dragged_object:
                # NEW: Perform one final, high-quality update on mouse release
                self.dragged_object.recalculate_geometry(final_calculation=True, regenerate_ports=False)
            self.dragged_object, self.drag_type, self.selected_port_index = None, None, -1


if __name__ == '__main__':
    app = Dashboard()
    app.run()