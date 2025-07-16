import pygame
from src.constants import *

class Viewport:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)  # The screen area this viewport occupies
        self.zoom = 1.0
        # The offset represents the top-left corner of the simulation world
        # that should be drawn at the top-left of the viewport.
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.is_panning = False
        self.pan_start_pos = (0, 0)

    def handle_event(self, event):
        """Processes mouse events for panning and zooming."""
        is_mouse_over = self.rect.collidepoint(pygame.mouse.get_pos())

        if event.type == pygame.MOUSEWHEEL and is_mouse_over:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            # Convert mouse screen coords to world coords before zoom
            world_x_before, world_y_before = self.screen_to_world(mouse_x, mouse_y)
            
            # Apply zoom
            self.zoom *= 1.1 if event.y > 0 else 0.9
            self.zoom = max(0.2, min(5.0, self.zoom)) # Clamp zoom
            
            # Get world coords under mouse after zoom
            world_x_after, world_y_after = self.screen_to_world(mouse_x, mouse_y)
            
            # Adjust offset to keep the point under the mouse stationary
            self.offset_x += world_x_before - world_x_after
            self.offset_y += world_y_before - world_y_after

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2 and is_mouse_over:
            self.is_panning = True
            self.pan_start_pos = event.pos
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.is_panning = False
            
        if event.type == pygame.MOUSEMOTION and self.is_panning:
            dx, dy = event.rel
            # Adjust offset by mouse movement, scaled by zoom
            self.offset_x -= dx / (self.zoom * PIXEL_SCALE)
            self.offset_y -= dy / (self.zoom * PIXEL_SCALE)

    def screen_to_world(self, screen_x, screen_y):
        """Converts coordinates from the global screen to the simulation world."""
        # Adjust for viewport's position on the screen
        local_x = screen_x - self.rect.x
        local_y = screen_y - self.rect.y
        
        world_x = (local_x / (self.zoom * PIXEL_SCALE)) + self.offset_x
        world_y = (local_y / (self.zoom * PIXEL_SCALE)) + self.offset_y
        return world_x, world_y

    def get_grid_pos(self, mouse_pos):
        """
        Converts a global screen mouse position to a simulation grid coordinate.
        Returns (grid_y, grid_x) or None if the click is outside the viewport.
        """
        if not self.rect.collidepoint(mouse_pos):
            return None

        world_x, world_y = self.screen_to_world(mouse_pos[0], mouse_pos[1])
        
        grid_x = int(world_x)
        grid_y = int(world_y)

        if 0 <= grid_y < SIM_HEIGHT and 0 <= grid_x < SIM_WIDTH:
            return (grid_y, grid_x)
        
        return None