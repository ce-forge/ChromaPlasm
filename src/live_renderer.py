import pygame
import numpy as np
import os
from src.constants import *

class LiveRenderer:
    def __init__(self, config):
        self.config = config
        max_key = max(COLOR_MAP.keys())
        default_color = (0, 0, 0)
        self.color_array = np.array([COLOR_MAP.get(i, default_color)[:3] for i in range(max_key + 1)], dtype=np.uint8)

        try:
            self.font_path = config.font_path
            self.base_font_size = config.font_size
            print(f"Font path set to: {self.font_path}")
        except Exception as e:
            print(f"Error setting up font: {e}")
            self.font_path = None
            self.base_font_size = 50
            
    # --- MODIFIED: Added show_pheromones parameter with a default value ---
    def draw(self, screen, sim, vfx_manager, viewport, show_pheromones=True):
        if viewport.rect.width <= 0 or viewport.rect.height <= 0:
            return

        viewport_surface = pygame.Surface(viewport.rect.size)
        viewport_surface.fill((10, 10, 15))

        # --- 1. Draw Simulation Grid & Trails ---
        # Draw the main grid of agents and bases first
        rgb_grid = self.color_array[sim.render_grid]
        sim_surface = pygame.surfarray.make_surface(rgb_grid.transpose(1, 0, 2))
        
        # --- MODIFIED: This entire block is now conditional ---
        if show_pheromones:
            surface_dims = (sim.grid_size[1], sim.grid_size[0])
            trail_surface = pygame.Surface(surface_dims, pygame.SRCALPHA)
            rgb_view = pygame.surfarray.pixels3d(trail_surface)
            alpha_view = pygame.surfarray.pixels_alpha(trail_surface)
            
            # Use a slightly lower threshold for a more visible but still clean look
            red_mask = sim.red_pheromone > 0.05
            blue_mask = sim.blue_pheromone > 0.05
            
            rgb_view[red_mask.T] = COLOR_MAP[RED_BASE_ARMOR][:3]
            alpha_view[red_mask.T] = 150
            rgb_view[blue_mask.T] = COLOR_MAP[BLUE_BASE_ARMOR][:3]
            alpha_view[blue_mask.T] = 150
            
            del rgb_view
            del alpha_view
            
            # Blend the trails on top of the main simulation surface
            sim_surface.blit(trail_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # --- 2. Scale and Position the Simulation ---
        scaled_w = int(sim_surface.get_width() * viewport.zoom * PIXEL_SCALE)
        scaled_h = int(sim_surface.get_height() * viewport.zoom * PIXEL_SCALE)
        draw_x, draw_y = 0, 0
        
        if scaled_w > 0 and scaled_h > 0:
            scaled_sim_surface = pygame.transform.scale(sim_surface, (scaled_w, scaled_h))
            draw_x = -viewport.offset_x * viewport.zoom * PIXEL_SCALE
            draw_y = -viewport.offset_y * viewport.zoom * PIXEL_SCALE
            viewport_surface.blit(scaled_sim_surface, (draw_x, draw_y))

        # --- 3. Draw YouTube Shorts Overlay ---
        if scaled_w > 0 and scaled_h > 0:
            on_screen_scale = scaled_h / VIDEO_GAME_AREA_HEIGHT
            scaled_top_margin_h = VIDEO_TOP_MARGIN * on_screen_scale
            scaled_bottom_margin_h = VIDEO_BOTTOM_MARGIN * on_screen_scale
            total_scaled_video_h = VIDEO_HEIGHT * on_screen_scale
            video_frame_rect = pygame.Rect(draw_x, draw_y - scaled_top_margin_h, scaled_w, total_scaled_video_h)
            top_margin_rect = pygame.Rect(draw_x, draw_y - scaled_top_margin_h, scaled_w, scaled_top_margin_h)
            bottom_margin_rect = pygame.Rect(draw_x, draw_y + scaled_h, scaled_w, scaled_bottom_margin_h)
            margin_color = (0, 0, 0, 150)
            pygame.draw.rect(viewport_surface, margin_color, top_margin_rect)
            pygame.draw.rect(viewport_surface, margin_color, bottom_margin_rect)
            pygame.draw.rect(viewport_surface, (255, 255, 255), video_frame_rect, 2)
            dynamic_font_size = int(self.base_font_size * on_screen_scale)
            if dynamic_font_size > 0:
                try:
                    title_font = pygame.font.Font(self.font_path, dynamic_font_size)
                except (FileNotFoundError, TypeError):
                    title_font = pygame.font.Font(None, dynamic_font_size)
                
                title_text_surf = title_font.render(self.config.question_text, True, (255, 255, 255))
                text_rect = title_text_surf.get_rect(center=top_margin_rect.center)
                viewport_surface.blit(title_text_surf, text_rect)

        # --- 4. Draw VFX (Particles) ---
        for p in vfx_manager.particles:
            if hasattr(p, 'y') and p.y is not None:
                screen_x = (p.x - viewport.offset_x) * viewport.zoom * PIXEL_SCALE
                screen_y = (p.y - viewport.offset_y) * viewport.zoom * PIXEL_SCALE
                
                if 0 <= screen_x < viewport.rect.width and 0 <= screen_y < viewport.rect.height:
                    alpha = int(255 * (p.lifespan / p.max_lifespan))
                    color = p.color[:3]
                    particle_surf = pygame.Surface((PIXEL_SCALE * viewport.zoom, PIXEL_SCALE * viewport.zoom), pygame.SRCALPHA)
                    particle_surf.fill((*color, alpha))
                    viewport_surface.blit(particle_surf, (int(screen_x), int(screen_y)))

        screen.blit(viewport_surface, viewport.rect.topleft)