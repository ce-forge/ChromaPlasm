import pygame
import numpy as np
import os
from src.constants import *

class LiveRenderer:
    def __init__(self, config):
        self.config = config
        max_key = max(COLOR_MAP.keys())
        self.color_array = np.array([COLOR_MAP.get(i, (0,0,0))[:3] for i in range(max_key + 1)], dtype=np.uint8)
        try:
            self.font_path = config.font_path
            self.base_font_size = config.font_size
        except Exception:
            self.font_path = None
            self.base_font_size = 50

    def draw(self, screen, sim, vfx_manager, viewport, show_pheromones, 
             selected_object=None, is_editing_spawns=False, title_text=""):
        
        if viewport.rect.width <= 0 or viewport.rect.height <= 0: return

        viewport_surface = pygame.Surface(viewport.rect.size)
        viewport_surface.fill((10, 10, 15))

        # --- UNIFIED RENDERING LOGIC ---
        # Always render from the simulation's main grid.
        rgb_grid = self.color_array[sim.render_grid]
        sim_surface = pygame.surfarray.make_surface(rgb_grid.transpose(1, 0, 2))
        
        if show_pheromones:
            sim_surface.blit(sim.red_pheromone_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            sim_surface.blit(sim.blue_pheromone_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        scaled_w = int(sim_surface.get_width() * viewport.zoom * PIXEL_SCALE)
        scaled_h = int(sim_surface.get_height() * viewport.zoom * PIXEL_SCALE)
        
        draw_x, draw_y = 0, 0
        if scaled_w > 0 and scaled_h > 0:
            scaled_sim_surface = pygame.transform.scale(sim_surface, (scaled_w, scaled_h))
            draw_x = -viewport.offset_x * viewport.zoom * PIXEL_SCALE
            draw_y = -viewport.offset_y * viewport.zoom * PIXEL_SCALE
            viewport_surface.blit(scaled_sim_surface, (draw_x, draw_y))
        
        # --- FIX FOR ISSUE 4: Draw Shorts Overlay in ALL modes ---
        if scaled_w > 0 and scaled_h > 0:
            on_screen_scale = scaled_h / VIDEO_GAME_AREA_HEIGHT
            scaled_top_margin_h = VIDEO_TOP_MARGIN * on_screen_scale
            scaled_bottom_margin_h = VIDEO_BOTTOM_MARGIN * on_screen_scale
            video_frame_rect = pygame.Rect(draw_x, draw_y - scaled_top_margin_h, scaled_w, scaled_h + scaled_top_margin_h + scaled_bottom_margin_h)
            top_margin_rect = pygame.Rect(draw_x, draw_y - scaled_top_margin_h, scaled_w, scaled_top_margin_h)
            bottom_margin_rect = pygame.Rect(draw_x, draw_y + scaled_h, scaled_w, scaled_bottom_margin_h)
            
            margin_color = (0, 0, 0, 150)
            pygame.draw.rect(viewport_surface, margin_color, top_margin_rect)
            pygame.draw.rect(viewport_surface, margin_color, bottom_margin_rect)
            pygame.draw.rect(viewport_surface, (255, 255, 255), video_frame_rect, 2)
            
            dynamic_font_size = int(self.base_font_size * on_screen_scale)
            if dynamic_font_size > 0:
                try: title_font = pygame.font.Font(self.font_path, dynamic_font_size)
                except (FileNotFoundError, TypeError): title_font = pygame.font.Font(None, dynamic_font_size)
                
                # Use the title_text passed from the dashboard
                title_text_surf = title_font.render(title_text, True, (255, 255, 255))
                text_rect = title_text_surf.get_rect(center=top_margin_rect.center)
                viewport_surface.blit(title_text_surf, text_rect)

        # --- Editor Overlays ---
        if is_editing_spawns and selected_object:
            for y, x in selected_object.exit_ports:
                screen_x = (x - viewport.offset_x) * viewport.zoom * PIXEL_SCALE
                screen_y = (y - viewport.offset_y) * viewport.zoom * PIXEL_SCALE
                if 0 <= screen_x < viewport.rect.width and 0 <= screen_y < viewport.rect.height:
                    pygame.draw.circle(viewport_surface, (255, 255, 0), (screen_x, screen_y), 6, 2)
        
        # --- VFX Drawing (unchanged) ---
        for p in vfx_manager.particles:
            if hasattr(p, 'y') and p.y is not None:
                screen_x = (p.x - viewport.offset_x) * viewport.zoom * PIXEL_SCALE
                screen_y = (p.y - viewport.offset_y) * viewport.zoom * PIXEL_SCALE
                if 0 <= screen_x < viewport.rect.width and 0 <= screen_y < viewport.rect.height:
                    alpha = int(255 * (p.lifespan / p.max_lifespan))
                    size = max(1.0, PIXEL_SCALE * viewport.zoom * 0.5)
                    particle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                    particle_surf.fill((*p.color[:3], alpha))
                    viewport_surface.blit(particle_surf, (int(screen_x), int(screen_y)))

        screen.blit(viewport_surface, viewport.rect.topleft)