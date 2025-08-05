import pygame
from src.constants import *

class Viewport:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.offset_x = SIM_WIDTH / 2
        self.offset_y = SIM_HEIGHT / 2
        self.zoom = 0.5
        self.panning = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            if self.rect.collidepoint(event.pos):
                self.panning = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.panning = False
        elif event.type == pygame.MOUSEMOTION and self.panning:
            self.offset_x -= event.rel[0] / self.zoom
            self.offset_y -= event.rel[1] / self.zoom
        elif event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            if self.rect.collidepoint(mouse_pos):
                old_zoom = self.zoom
                world_x_before, world_y_before = self.get_world_pos_from_screen(mouse_pos, old_zoom)
                
                zoom_factor = 1.1
                if event.y > 0:
                    self.zoom *= zoom_factor
                elif event.y < 0:
                    self.zoom /= zoom_factor

                self.zoom = max(0.1, min(self.zoom, 5.0))
                
                world_x_after, world_y_after = self.get_world_pos_from_screen(mouse_pos, self.zoom)
                self.offset_x += world_x_before - world_x_after
                self.offset_y += world_y_before - world_y_after

    def get_world_pos_from_screen(self, screen_pos, zoom_level):
        vp_x = screen_pos[0] - self.rect.x
        vp_y = screen_pos[1] - self.rect.y
        mouse_dx_pixels = vp_x - self.rect.width / 2
        mouse_dy_pixels = vp_y - self.rect.height / 2
        world_dx = mouse_dx_pixels / (PIXEL_SCALE * zoom_level)
        world_dy = mouse_dy_pixels / (PIXEL_SCALE * zoom_level)
        return self.offset_x + world_dx, self.offset_y + world_dy

    def get_grid_pos(self, screen_pos):
        mouse_x = screen_pos[0] - self.rect.x
        mouse_y = screen_pos[1] - self.rect.y
        
        blit_x = (self.rect.width / 2) - self.offset_x * PIXEL_SCALE * self.zoom
        blit_y = (self.rect.height / 2) - self.offset_y * PIXEL_SCALE * self.zoom
        
        x_on_final_surf = (mouse_x - blit_x) / self.zoom
        y_on_final_surf = (mouse_y - blit_y) / self.zoom
        
        if not (0 <= x_on_final_surf < VIDEO_WIDTH and 0 <= y_on_final_surf < VIDEO_HEIGHT):
            return None
        if y_on_final_surf < VIDEO_TOP_MARGIN or y_on_final_surf >= (VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN):
            return None
            
        x_in_game_area = x_on_final_surf
        y_in_game_area = y_on_final_surf - VIDEO_TOP_MARGIN
        
        grid_x = x_in_game_area / PIXEL_SCALE
        grid_y = y_in_game_area / PIXEL_SCALE
        
        if 0 <= grid_x < SIM_WIDTH and 0 <= grid_y < SIM_HEIGHT:
            return int(grid_y), int(grid_x)
            
        return None