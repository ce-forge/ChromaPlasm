from collections import deque
import numpy as np
import random
from src.constants import *
import json
import pygame

class Base:
    def __init__(self, team_name, pivot_y, pivot_x, shape_name, config, grid_h, grid_w):
        if team_name.lower() == 'red': team_name = 'Crimson'
        elif team_name.lower() == 'blue': team_name = 'Azure'
        self.team_name = team_name
        self.team_id = TEAM_NAME_TO_ID.get(team_name.lower())
        if self.team_id is None:
            self.team_name = TEAM_ID_TO_NAME.get(0, "Default"); self.team_id = 0
        
        self.pivot = (pivot_y, pivot_x); self.shape_name = shape_name; self.config = config
        self.id = f"{self.team_name}_{shape_name}_{pivot_y}_{pivot_x}"; self.grid_h, self.grid_w = grid_h, grid_w
        self.scale = 8.0; self.core_thickness, self.armor_thickness = 1, 2
        self._relative_exit_ports = []; self.last_damage_frame = -100
        
        self.shape_type = 'lines' if shape_name in ['Y', 'N'] else 'polygon'
        self.core_template = self._get_shape_template(shape_name)
        self.current_armor_pixels, self.current_core_pixels = [], []; self.rim_pixels = set()
        
        self._load_template()
        self.recalculate_geometry(final_calculation=True, regenerate_ports=not self._relative_exit_ports)
        self.spawn_cooldown = 0

    @property
    def exit_ports(self):
        return [(self.pivot[0] + dy, self.pivot[1] + dx) for dy, dx in self._relative_exit_ports]

    def _bresenham_line(self, y1, x1, y2, x2):
        dx, dy = abs(x2 - x1), abs(y2 - y1); sx, sy = 1 if x1 < x2 else -1, 1 if y1 < y2 else -1; err = dx - dy
        while True:
            yield (y1, x1)
            if y1 == y2 and x1 == x2: break
            e2 = 2 * err
            if e2 > -dy: err -= dy; x1 += sx
            if e2 < dx: err += dx; y1 += sy

    def _get_shape_template(self, name):
        if name == 'Y': return [ ((-1, 0), (4, 0)), ((-1, 0), (-4, -3)), ((-1, 0), (-4, 3)) ]
        if name == 'N': return [ ((4, -2), (-4, -2)), ((-4, 2), (4, 2)), ((-4, -2), (4, 2)) ]
        if name == 'ARROWHEAD': return [ (-2, 4), (4, 0), (-2, -4) ]
        return [ (-4,-4), (4,-4), (4,4), (-4,4) ]

    def _find_exterior_pixels(self, core_pixels_local, grid_h, grid_w):
        q = deque()
        visited = set()
        corners = [(0, 0), (0, grid_w - 1), (grid_h - 1, 0), (grid_h - 1, grid_w - 1)]
        for c in corners:
            if c not in visited and 0 <= c[0] < grid_h and 0 <= c[1] < grid_w:
                q.append(c); visited.add(c)

        exterior_pixels = set()
        while q:
            y, x = q.popleft()
            if (y,x) in core_pixels_local: continue
            exterior_pixels.add((y,x))
            for dy, dx in [(0,1), (0,-1), (1,0), (-1,0)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < grid_h and 0 <= nx < grid_w and (ny, nx) not in visited:
                    visited.add((ny, nx)); q.append((ny, nx))
        return exterior_pixels

    def recalculate_preview(self):
        thin_line_pixels = set()
        if self.shape_type == 'lines':
            for p1, p2 in self.core_template:
                y1, x1, y2, x2 = int(p1[0] * self.scale), int(p1[1] * self.scale), int(p2[0] * self.scale), int(p2[1] * self.scale)
                abs_y1, abs_x1, abs_y2, abs_x2 = self.pivot[0] + y1, self.pivot[1] + x1, self.pivot[0] + y2, self.pivot[1] + x2
                for y, x in self._bresenham_line(abs_y1, abs_x1, abs_y2, abs_x2): thin_line_pixels.add((y, x))
        else:
            points = [(self.pivot[1] + p[1]*self.scale, self.pivot[0] + p[0]*self.scale) for p in self.core_template]
            temp_surf = pygame.Surface((self.grid_w, self.grid_h))
            if len(points) > 2: pygame.draw.polygon(temp_surf, (255,255,255), points)
            px_array_2d = pygame.surfarray.pixels2d(temp_surf)
            indices = np.nonzero(px_array_2d)
            thin_line_pixels.update(zip(indices[1], indices[0]))
            del px_array_2d

        core_set = set()
        for y, x in thin_line_pixels:
            for dy in range(-self.core_thickness, self.core_thickness + 1):
                for dx in range(-self.core_thickness, self.core_thickness + 1):
                    core_set.add((y + dy, x + dx))
        
        self.current_core_pixels = list(core_set)
        self.all_base_pixels = core_set
        self.current_armor_pixels = []

    def recalculate_geometry(self, final_calculation=True, regenerate_ports=True):
        if regenerate_ports: self._relative_exit_ports.clear()
        
        self.recalculate_preview()
        core_set = set(self.current_core_pixels)
        
        if not core_set:
            self.current_armor_pixels = []; self.all_base_pixels = set(); return
        
        armor_set = set()
        if final_calculation:
            margin = self.armor_thickness + 2
            min_y, max_y = min(p[0] for p in core_set) - margin, max(p[0] for p in core_set) + margin
            min_x, max_x = min(p[1] for p in core_set) - margin, max(p[1] for p in core_set) + margin
            
            local_grid_h = max_y - min_y + 1
            local_grid_w = max_x - min_x + 1
            
            core_local = set((y - min_y, x - min_x) for y, x in core_set)
            
            ext_local = self._find_exterior_pixels(core_local, local_grid_h, local_grid_w)
            armor_local = set()
            for cy, cx in core_local:
                for dy in range(-self.armor_thickness, self.armor_thickness + 1):
                    for dx in range(-self.armor_thickness, self.armor_thickness + 1):
                        cand = (cy + dy, cx + dx)
                        if cand not in core_local and cand in ext_local: armor_local.add(cand)
            armor_set = set((y + min_y, x + min_x) for y, x in armor_local)
        
        self.current_armor_pixels = list(armor_set)
        self.all_base_pixels = core_set.union(armor_set)
        self.rim_pixels = set()
        for y, x in self.all_base_pixels:
            if not all(((y+dy, x+dx) in self.all_base_pixels for dy, dx in [(0,1),(0,-1),(1,0),(-1,0)])):
                self.rim_pixels.add((y, x))
    
    def _load_template(self):
        try:
            with open('base_layouts.json', 'r') as f:
                templates = json.load(f).get('shape_templates', {})
                template_data = templates.get(self.shape_name, {})
                if template_data:
                    self.scale = template_data.get('scale', self.scale)
                    self.core_thickness = template_data.get('core_thickness', self.core_thickness)
                    self.armor_thickness = template_data.get('armor_thickness', self.armor_thickness)
                    self._relative_exit_ports = [tuple(p) for p in template_data.get('exit_ports', [])]
        except (FileNotFoundError, json.JSONDecodeError): pass

    def update_attributes(self, team_name=None, shape_name=None):
        if team_name: self.team_name = team_name; self.team_id = TEAM_NAME_TO_ID.get(team_name.lower())
        if shape_name and self.shape_name != shape_name:
            self.shape_name = shape_name;
            self.shape_type = 'lines' if shape_name in ['Y', 'N'] else 'polygon'
            self.core_template = self._get_shape_template(shape_name)
            self._load_template()
            self.recalculate_geometry(final_calculation=True, regenerate_ports=False)

    def update_spawning(self, sim):
        if not self.current_armor_pixels: return
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0:
            units_to_spawn = int(sim.get_param(self.team_id, 'units_per_spawn'))
            open_ports = [(y, x) for y, x in self.exit_ports if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH]
            if not open_ports: self.spawn_cooldown = int(sim.get_param(self.team_id, 'spawn_rate')); return
            for _ in range(units_to_spawn):
                spawn_y, spawn_x = random.choice(open_ports)
                sim.add_soldier(spawn_y, spawn_x, self.team_id, np.random.uniform(0, 2 * np.pi))
            self.spawn_cooldown = int(sim.get_param(self.team_id, 'spawn_rate'))