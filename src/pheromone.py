import numpy as np
from scipy.ndimage import gaussian_filter
import pygame
from collections import deque

class PheromoneManager:
    """
    A self-contained class to manage a single pheromone grid,
    including its data, updates (decay and blur), and rendering.
    """
    def __init__(self, grid_size, config):
        self.grid = np.zeros(grid_size, dtype=np.float32)
        self.config = config
        self.color = (255, 255, 255)
        
        # --- FLICKER FIX: Smoothed normalization ---
        self.max_pheromone_history = deque(maxlen=30) # Store max values for the last 30 frames
        self.smoothed_max = 1.0

    def deposit(self, positions, amount=1.0):
        """Adds pheromones at a list of agent positions."""
        if len(positions) > 0:
            y_coords, x_coords = positions[:, 0].astype(int), positions[:, 1].astype(int)
            y_coords = np.clip(y_coords, 0, self.grid.shape[0] - 1)
            x_coords = np.clip(x_coords, 0, self.grid.shape[1] - 1)
            self.grid[y_coords, x_coords] += amount

    def update(self, frame_count):
        """Applies decay and the Gaussian blur to the grid."""
        self.grid *= self.config.pheromone_decay_rate
        
        # Only apply the expensive blur operation on even-numbered frames
        if self.config.pheromone_blur_sigma > 0 and frame_count % 2 == 0:
            self.grid = gaussian_filter(
                self.grid, 
                sigma=self.config.pheromone_blur_sigma, 
                truncate=2.5
            )
        
        self.grid[self.grid < 0.001] = 0
        
        # --- FLICKER FIX: Update the smoothed maximum ---
        current_max = np.max(self.grid)
        if current_max > 0:
            self.max_pheromone_history.append(current_max)
        
        if len(self.max_pheromone_history) > 0:
            self.smoothed_max = np.mean(list(self.max_pheromone_history))


    def get_render_surface(self):
        """
        Creates the final, colored, and blurred pheromone surface.
        """
        surface_dims = (self.grid.shape[1], self.grid.shape[0])
        glow_surface = pygame.Surface(surface_dims, flags=pygame.SRCALPHA)
        
        pixels_rgb = pygame.surfarray.pixels3d(glow_surface)
        pixels_alpha = pygame.surfarray.pixels_alpha(glow_surface)

        # --- FLICKER FIX: Normalize against the stable, smoothed maximum ---
        if self.smoothed_max < 1.0:
            return glow_surface

        norm_grid = self.grid / self.smoothed_max
        
        # Transpose is essential to map numpy (h, w) to pygame (w, h)
        norm_grid_t = norm_grid.T

        # Scale the RGB channels by the normalized brightness
        pixels_rgb[:, :, 0] = np.clip(norm_grid_t * self.color[0], 0, 255)
        pixels_rgb[:, :, 1] = np.clip(norm_grid_t * self.color[1], 0, 255)
        pixels_rgb[:, :, 2] = np.clip(norm_grid_t * self.color[2], 0, 255)

        # Scale the alpha channel
        pixels_alpha[:, :] = np.clip(norm_grid_t * 255, 0, 255).astype(np.uint8)

        del pixels_rgb
        del pixels_alpha

        return glow_surface

    def clear_zone(self, zone_pixels):
        """Dampens the pheromone values within a given zone instead of clearing."""
        if len(zone_pixels) > 0:
            zone_y = [p[0] for p in zone_pixels]
            zone_x = [p[1] for p in zone_pixels]
            self.grid[zone_y, zone_x] *= 0.1