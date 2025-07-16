import numpy as np
import random
from src.constants import *
from src.soldier import Soldier

class Base:
    def __init__(self, team, pivot_y, pivot_x, shape_name, config, scale=1.0):
        self.team = team
        self.pivot = (pivot_y, pivot_x)
        self.shape_name = shape_name
        self.config = config
        self.scale = scale
        self.id = f"{team}_{shape_name}_{pivot_y}_{pivot_x}"

        self.params = {
            # We start with the base-specific params.
            # The global slime params will be added by the UI if they are changed.
            'spawn_rate': self.config.spawn_rate,
            'units_per_spawn': self.config.units_per_spawn
        }

        self.spawn_rate = self.config.spawn_rate
        self.units_per_spawn = self.config.units_per_spawn

        self.core_template = self._get_shape_template(shape_name)
        self.current_armor_pixels, self.current_core_pixels, self.exit_ports = [], [], []
        
        self.recalculate_geometry()
        self.spawn_cooldown = 0

    def _bresenham_line(self, y1, x1, y2, x2):
        """Standard Bresenham's line algorithm. Yields (y, x) tuples."""
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
        """Returns a list of CORE line segments. Segments are ((y1,x1), (y2,x2))."""
        if name == 'Y':
            return [ ((4, 0), (-1, 0)), ((-1, 0), (-4, -3)), ((-1, 0), (-4, 3)) ]
        if name == 'N':
            return [ ((4, -2), (-4, -2)), ((-4, 2), (4, 2)), ((-4, -2), (4, 2)) ]
        return [ ((-2,-2), (-2,2)), ((-2,2), (2,2)), ((2,2), (2,-2)), ((2,-2), (-2,-2)) ]

    def recalculate_geometry(self):
        """Applies scaling and generates the full base shape and exit ports."""
        self.current_armor_pixels.clear(); self.current_core_pixels.clear(); self.exit_ports.clear()
        
        core_set = set()
        for p1, p2 in self.core_template:
            y1, x1 = int(p1[0] * self.scale), int(p1[1] * self.scale)
            y2, x2 = int(p2[0] * self.scale), int(p2[1] * self.scale)
            abs_y1, abs_x1 = self.pivot[0] + y1, self.pivot[1] + x1
            abs_y2, abs_x2 = self.pivot[0] + y2, self.pivot[1] + x2
            for y, x in self._bresenham_line(abs_y1, abs_x1, abs_y2, abs_x2):
                core_set.add((y, x))
        self.current_core_pixels = list(core_set)

        armor_set = set()
        for core_y, core_x in self.current_core_pixels:
            for dy, dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
                armor_candidate = (core_y + dy, core_x + dx)
                if armor_candidate not in core_set: armor_set.add(armor_candidate)
        self.current_armor_pixels = list(armor_set)

        if self.shape_name == 'Y':
            p1_end, p2_end, p3_end = self.core_template[0][0], self.core_template[1][1], self.core_template[2][1]
            self.exit_ports.extend([
                (self.pivot[0] + int(p1_end[0] * self.scale) + np.sign(p1_end[0]), self.pivot[1] + int(p1_end[1] * self.scale)),
                (self.pivot[0] + int(p2_end[0] * self.scale) + np.sign(p2_end[0]), self.pivot[1] + int(p2_end[1] * self.scale) + np.sign(p2_end[1])),
                (self.pivot[0] + int(p3_end[0] * self.scale) + np.sign(p3_end[0]), self.pivot[1] + int(p3_end[1] * self.scale) + np.sign(p3_end[1]))
            ])
        elif self.shape_name == 'N':
            p1_start, p2_end = self.core_template[0][1], self.core_template[1][1]
            self.exit_ports.extend([
                (self.pivot[0] + int(p1_start[0] * self.scale) + np.sign(p1_start[0]), self.pivot[1] + int(p1_start[1] * self.scale) + np.sign(p1_start[1])),
                (self.pivot[0] + int(p2_end[0] * self.scale) + np.sign(p2_end[0]), self.pivot[1] + int(p2_end[1] * self.scale) + np.sign(p2_end[1]))
            ])

    def update_spawning(self, sim):
        """Creates new soldiers based on the configured spawn rate."""
        self.spawn_cooldown -= 1
        if self.spawn_cooldown <= 0:
            for _ in range(self.params['units_per_spawn']):
                if not self.exit_ports: continue
                spawn_y, spawn_x = random.choice(self.exit_ports)
                if 0 <= spawn_y < SIM_HEIGHT and 0 <= spawn_x < SIM_WIDTH and sim.object_grid[spawn_y, spawn_x] is None:
                    soldier = Soldier(spawn_y, spawn_x, self.team)
                    soldier.base_pivot = self.pivot
                    sim.add_soldier(soldier)
            self.spawn_cooldown = self.params['spawn_rate']