import numpy as np
import random
from src.constants import *

class Base:
    def __init__(self, team, pivot_y, pivot_x, shape_name, config, scale=1.0, 
                 core_thickness=1, armor_thickness=1, grid_h=0, grid_w=0):
        self.team = team
        self.pivot = (pivot_y, pivot_x)
        self.shape_name = shape_name
        self.config = config
        self.scale = scale
        self.id = f"{team}_{shape_name}_{pivot_y}_{pivot_x}"
        
        self.core_thickness = core_thickness
        self.armor_thickness = armor_thickness
        self.grid_h = grid_h
        self.grid_w = grid_w

        self.params = { 'spawn_rate': self.config.spawn_rate, 'units_per_spawn': self.config.units_per_spawn }
        self.spawn_rate = self.config.spawn_rate
        self.units_per_spawn = self.config.units_per_spawn

        self.core_template = self._get_shape_template(shape_name)
        self.current_armor_pixels, self.current_core_pixels, self.exit_ports = [], [], []
        
        self.recalculate_geometry()
        self.spawn_cooldown = 0

        # In base.py, inside the Base class
    def update_attributes(self, team=None, shape_name=None):
        """Updates core properties of the base and recalculates its geometry."""
        should_recalculate = False
        if team and self.team != team:
            self.team = team
            should_recalculate = True
        if shape_name and self.shape_name != shape_name:
            self.shape_name = shape_name
            self.core_template = self._get_shape_template(shape_name)
            should_recalculate = True
        
        if should_recalculate:
            self.recalculate_geometry()

    def _bresenham_line(self, y1, x1, y2, x2):
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx, sy = 1 if x1 < x2 else -1, 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            yield (y1, x1)
            if y1 == y2 and x1 == x2: break
            e2 = 2 * err
            if e2 > -dy: err -= dy; x1 += sx
            if e2 < dx: err += dx; y1 += sy

    def _get_shape_template(self, name):
        if name == 'Y':
            return [ ((4, 0), (-1, 0)), ((-1, 0), (-4, -3)), ((-1, 0), (-4, 3)) ]
        if name == 'N':
            return [ ((4, -2), (-4, -2)), ((-4, 2), (4, 2)), ((-4, -2), (4, 2)) ]
        return [ ((-2,-2), (-2,2)), ((-2,2), (2,2)), ((2,2), (2,-2)), ((2,-2), (-2,-2)) ]

    def recalculate_geometry(self):
        self.current_armor_pixels.clear()
        self.current_core_pixels.clear()
        self.exit_ports.clear()
        
        core_set = set()
        
        if self.shape_name == 'BOX':
            p1_rel, p2_rel = self.core_template[0][0], self.core_template[2][0]
            y1_rel_scaled, x1_rel_scaled = int(p1_rel[0] * self.scale), int(p1_rel[1] * self.scale)
            y2_rel_scaled, x2_rel_scaled = int(p2_rel[0] * self.scale), int(p2_rel[1] * self.scale)
            min_y, max_y = self.pivot[0] + min(y1_rel_scaled, y2_rel_scaled), self.pivot[0] + max(y1_rel_scaled, y2_rel_scaled)
            min_x, max_x = self.pivot[1] + min(x1_rel_scaled, x2_rel_scaled), self.pivot[1] + max(x1_rel_scaled, x2_rel_scaled)
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    core_set.add((y, x))
        else:
            thin_line_pixels = set()
            for p1, p2 in self.core_template:
                y1, x1 = int(p1[0] * self.scale), int(p1[1] * self.scale)
                y2, x2 = int(p2[0] * self.scale), int(p2[1] * self.scale)
                abs_y1, abs_x1 = self.pivot[0] + y1, self.pivot[1] + x1
                abs_y2, abs_x2 = self.pivot[0] + y2, self.pivot[1] + x2
                for y, x in self._bresenham_line(abs_y1, abs_x1, abs_y2, abs_x2):
                    thin_line_pixels.add((y, x))
            for y, x in thin_line_pixels:
                for dy in range(-self.core_thickness, self.core_thickness + 1):
                    for dx in range(-self.core_thickness, self.core_thickness + 1):
                        core_set.add((y + dy, x + dx))
        
        self.current_core_pixels = list(core_set)

        armor_set = set()
        for core_y, core_x in self.current_core_pixels:
            for dy in range(-self.armor_thickness, self.armor_thickness + 1):
                 for dx in range(-self.armor_thickness, self.armor_thickness + 1):
                    armor_candidate = (core_y + dy, core_x + dx)
                    if armor_candidate not in core_set:
                        armor_set.add(armor_candidate)
        self.current_armor_pixels = list(armor_set)
        self.all_base_pixels = core_set.union(armor_set)
        
        ideal_points = []
        
        if self.shape_name == 'Y':
            p1_end, p2_end, p3_end = self.core_template[0][0], self.core_template[1][1], self.core_template[2][1]
            ideal_points.extend([
                (self.pivot[0] + int(p1_end[0] * self.scale), self.pivot[1] + int(p1_end[1] * self.scale)),
                (self.pivot[0] + int(p2_end[0] * self.scale), self.pivot[1] + int(p2_end[1] * self.scale)),
                (self.pivot[0] + int(p3_end[0] * self.scale), self.pivot[1] + int(p3_end[1] * self.scale))
            ])
        elif self.shape_name == 'N':
            p1_start, p2_start = self.core_template[0][0], self.core_template[1][0]
            ideal_points.extend([
                (self.pivot[0] + int(p1_start[0] * self.scale), self.pivot[1] + int(p1_start[1] * self.scale)),
                (self.pivot[0] + int(p2_start[0] * self.scale), self.pivot[1] + int(p2_start[1] * self.scale))
            ])
        elif self.shape_name == 'BOX':
            if not self.current_armor_pixels: return
            armor_ys, armor_xs = [p[0] for p in self.current_armor_pixels], [p[1] for p in self.current_armor_pixels]
            min_y, max_y, min_x, max_x = min(armor_ys), max(armor_ys), min(armor_xs), max(armor_xs)
            spawn_offset, density = 3, 10
            for x in range(min_x, max_x + 1, density): self.exit_ports.append((min_y - spawn_offset, x))
            for x in range(min_x, max_x + 1, density): self.exit_ports.append((max_y + spawn_offset, x))
            for y in range(min_y + density, max_y, density): self.exit_ports.append((y, min_x - spawn_offset))
            for y in range(min_y + density, max_y, density): self.exit_ports.append((y, max_x + spawn_offset))
            return

        for ideal_y, ideal_x in ideal_points:
            best_pos, min_dist_sq = None, float('inf')
            for dy in range(-10, 11):
                for dx in range(-10, 11):
                    check_y, check_x = ideal_y + dy, ideal_x + dx
                    if (check_y, check_x) not in self.all_base_pixels:
                        dist_sq = dy**2 + dx**2
                        if dist_sq < min_dist_sq:
                            min_dist_sq, best_pos = dist_sq, (check_y, check_x)
            if best_pos: self.exit_ports.append(best_pos)

    def update_spawning(self, sim):
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0:
            units_to_spawn = int(sim.get_param(self.team, 'units_per_spawn'))
            
            # --- START: WAVE SPAWNING LOGIC ---
            
            # 1. Get a list of all physically available spawn points.
            #    We only check if the port is inside the world grid.
            open_ports = [
                (y, x) for y, x in self.exit_ports
                if 0 <= y < SIM_HEIGHT and 0 <= x < SIM_WIDTH
            ]
            
            # If the base has no valid spawn points left, do nothing.
            if not open_ports:
                self.spawn_cooldown = int(sim.get_param(self.team, 'spawn_rate'))
                return

            # 2. Loop for the number of units we WANT to spawn.
            for _ in range(units_to_spawn):
                # 3. For each unit, pick a random available port. This allows reuse.
                spawn_y, spawn_x = random.choice(open_ports)
                
                # 4. Create the agent in the data arrays. Overlapping here is OK.
                sim.add_soldier(spawn_y, spawn_x, self.team, np.random.uniform(0, 2 * np.pi))

            # --- END: WAVE SPAWNING LOGIC ---
            
            self.spawn_cooldown = int(sim.get_param(self.team, 'spawn_rate'))