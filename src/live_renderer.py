import pygame
import numpy as np
import os
from src.constants import *

class LiveRenderer:
    def __init__(self, config):
        self.config = config
        max_key = max(COLOR_MAP.keys()) if COLOR_MAP else 0
        self.color_array = np.array([COLOR_MAP.get(i, (0,0,0,0))[:3] for i in range(max_key + 1)], dtype=np.uint8)
        
        self.background_surface = self._create_background_surface()
        # --- NEW: Pre-render the fade gradient for performance ---
        self.gradient_surface = self._create_fade_gradient((16, 16, 26), 60, VIDEO_WIDTH)

        try:
            self.font_path = config.font_path
            self.base_font_size = config.font_size
        except AttributeError:
            self.font_path = None
            self.base_font_size = 50

    def draw(self, screen, sim, vfx_manager, viewport, show_pheromones, 
             selected_object=None, is_editing_spawns=False, title_text=""):
        if viewport.rect.width <= 0 or viewport.rect.height <= 0: return
        viewport_surface = pygame.Surface(viewport.rect.size)
        viewport_surface.fill((10, 10, 15))
        final_render_surface = pygame.Surface((VIDEO_WIDTH, VIDEO_HEIGHT), pygame.SRCALPHA)
        top_margin_rect = pygame.Rect(0, 0, VIDEO_WIDTH, VIDEO_TOP_MARGIN)
        bottom_margin_rect = pygame.Rect(0, VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN, VIDEO_WIDTH, VIDEO_BOTTOM_MARGIN)
        margin_color = (16, 16, 26, 220); pygame.draw.rect(final_render_surface, margin_color, top_margin_rect); pygame.draw.rect(final_render_surface, margin_color, bottom_margin_rect)
        try:
            font_scale = VIDEO_HEIGHT / 1920.0; title_font_size = int(self.base_font_size * font_scale * 0.6); title_font = pygame.font.Font(self.font_path, title_font_size)
            title_surf = title_font.render(title_text, True, (220, 220, 230)); text_rect = title_surf.get_rect(centerx=top_margin_rect.centerx, y=top_margin_rect.y + top_margin_rect.height * 0.15)
            final_render_surface.blit(title_surf, text_rect)
        except (FileNotFoundError, TypeError): pass
        active_teams = sorted(list(set(base.team_id for base in sim.bases)))
        if active_teams:
            groups = {}; [groups.setdefault(sim.alliance_map[tid], []).append(tid) for tid in active_teams]
            symbol_size = int(top_margin_rect.height * 0.32); padding = int(symbol_size * 0.5); div_width = int(symbol_size * 0.3)
            total_width = sum(len(teams) * (symbol_size + padding) for teams in groups.values()) - padding + (len(groups) - 1) * (div_width + padding * 2)
            x_pos = top_margin_rect.centerx - total_width // 2; first_group = True
            for aid in sorted(groups.keys()):
                if not first_group: pygame.draw.line(final_render_surface, (150, 150, 160), (x_pos + padding, top_margin_rect.bottom - (symbol_size*1.1) - padding), (x_pos + padding, top_margin_rect.bottom - padding), 2); x_pos += div_width + padding * 2
                for team_id in groups[aid]:
                    team, color = TEAMS[team_id], TEAMS[team_id]['color']; y_pos = top_margin_rect.bottom - symbol_size - padding; symbol_rect = pygame.Rect(x_pos, y_pos, symbol_size, symbol_size)
                    pygame.draw.rect(final_render_surface, color, symbol_rect)
                    try:
                        health = sim.get_team_base_health(team['name']); h_font_size = int(symbol_size * 0.65); health_font = pygame.font.Font(self.font_path, h_font_size); health_font.set_bold(True)
                        health_surf = health_font.render(str(health), True, (0,0,0)); health_rect = health_surf.get_rect(center=symbol_rect.center); final_render_surface.blit(health_surf, health_rect)
                    except (FileNotFoundError, TypeError): pass
                    x_pos += symbol_size + padding
                first_group = False
        
        world_surface = self.background_surface.copy()
        grid_surface = pygame.surfarray.make_surface(self.color_array[sim.render_grid].transpose(1, 0, 2)); grid_surface.set_colorkey(COLOR_MAP[EMPTY][:3]); world_surface.blit(grid_surface, (0, 0))
        if show_pheromones: [world_surface.blit(p_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD) for p_surf in sim.pheromone_surfaces.values()]
        for p in vfx_manager.particles:
            if hasattr(p, 'y') and p.y is not None:
                alpha = int(255 * (p.lifespan / p.max_lifespan)); size = max(1.0, p.radius * PIXEL_SCALE * 0.5)
                particle_surf = pygame.Surface((size, size), pygame.SRCALPHA); particle_surf.fill((*p.color[:3], alpha))
                world_surface.blit(particle_surf, (p.x - size/2, p.y - size/2))
        scaled_world = pygame.transform.scale(world_surface, (VIDEO_GAME_AREA_WIDTH, VIDEO_GAME_AREA_HEIGHT)); final_render_surface.blit(scaled_world, (0, VIDEO_TOP_MARGIN))

        # --- NEW: Draw the fade gradients to blend the margins ---
        final_render_surface.blit(self.gradient_surface, (0, VIDEO_TOP_MARGIN))
        bottom_gradient = pygame.transform.flip(self.gradient_surface, False, True)
        final_render_surface.blit(bottom_gradient, (0, VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN - self.gradient_surface.get_height()))

        zoom = viewport.zoom; scaled_final_surf = pygame.transform.scale(final_render_surface, (int(VIDEO_WIDTH * zoom), int(VIDEO_HEIGHT * zoom)))
        blit_x = (viewport.rect.width / 2) - viewport.offset_x * PIXEL_SCALE * zoom; blit_y = (viewport.rect.height / 2) - viewport.offset_y * PIXEL_SCALE * zoom
        viewport_surface.blit(scaled_final_surf, (blit_x, blit_y)); pygame.draw.rect(viewport_surface, (200, 200, 220), pygame.Rect(blit_x, blit_y, scaled_final_surf.get_width(), scaled_final_surf.get_height()), 2)
        if selected_object or is_editing_spawns:
            game_area_screen_x = blit_x; game_area_screen_y = blit_y + (VIDEO_TOP_MARGIN * zoom)
            if selected_object:
                highlight_color = (255, 255, 0); pixel_size = max(1, PIXEL_SCALE * zoom)
                for y, x in selected_object.rim_pixels: pygame.draw.rect(viewport_surface, highlight_color, (game_area_screen_x + (x*PIXEL_SCALE*zoom), game_area_screen_y + (y*PIXEL_SCALE*zoom), pixel_size, pixel_size), 1)
            if is_editing_spawns:
                 port_color = (255, 255, 0)
                 for y, x in selected_object.exit_ports: pygame.draw.circle(viewport_surface, port_color, (game_area_screen_x + (x*PIXEL_SCALE*zoom), game_area_screen_y + (y*PIXEL_SCALE*zoom)), int(max(2, 6 * zoom)), 2)
        screen.blit(viewport_surface, viewport.rect.topleft)

    def _create_fade_gradient(self, color, height, width):
        """Creates a surface with a vertical gradient from a color to transparent."""
        gradient = pygame.Surface((width, height), pygame.SRCALPHA)
        for y in range(height):
            # As y increases, alpha decreases, creating a fade-out effect.
            alpha = 255 - int((y / height) * 255)
            pygame.draw.line(gradient, (*color, alpha), (0, y), (width, y))
        return gradient

    def _create_background_surface(self):
        background = pygame.Surface((SIM_WIDTH, SIM_HEIGHT)); background.fill((16, 16, 26)); center_x, center_y = SIM_WIDTH // 2, SIM_HEIGHT // 2
        grid_color_1 = (35, 35, 50); grid_spacing_1 = 10
        num_x_lines_1 = (SIM_WIDTH // grid_spacing_1) + 1; num_y_lines_1 = (SIM_HEIGHT // grid_spacing_1) + 1
        grid_width_1 = (num_x_lines_1 - 1) * grid_spacing_1; grid_height_1 = (num_y_lines_1 - 1) * grid_spacing_1
        offset_x_1 = (SIM_WIDTH - grid_width_1) // 2; offset_y_1 = (SIM_HEIGHT - grid_height_1) // 2
        for i in range(num_x_lines_1): pygame.draw.line(background, grid_color_1, (offset_x_1 + i * grid_spacing_1, 0), (offset_x_1 + i * grid_spacing_1, SIM_HEIGHT))
        for i in range(num_y_lines_1): pygame.draw.line(background, grid_color_1, (0, offset_y_1 + i * grid_spacing_1), (SIM_WIDTH, offset_y_1 + i * grid_spacing_1))
        grid_color_2 = (45, 55, 80); line_thickness_2 = 2; grid_spacing_2 = 100
        num_x_lines_2 = (SIM_WIDTH // grid_spacing_2) + 1; num_y_lines_2 = (SIM_HEIGHT // grid_spacing_2) + 1
        grid_width_2 = (num_x_lines_2 - 1) * grid_spacing_2; grid_height_2 = (num_y_lines_2 - 1) * grid_spacing_2
        offset_x_2 = (SIM_WIDTH - grid_width_2) // 2; offset_y_2 = (SIM_HEIGHT - grid_height_2) // 2
        for i in range(num_x_lines_2): pygame.draw.line(background, grid_color_2, (offset_x_2 + i * grid_spacing_2, 0), (offset_x_2 + i * grid_spacing_2, SIM_HEIGHT), line_thickness_2)
        for i in range(num_y_lines_2): y_pos = offset_y_2 + i * grid_spacing_2; pygame.draw.line(background, grid_color_2, (0, y_pos), (SIM_WIDTH, y_pos), line_thickness_2)
        pygame.draw.circle(background, grid_color_2, (center_x, center_y), grid_spacing_2 // 2, 1)
        pygame.draw.line(background, grid_color_2, (center_x - grid_spacing_2, center_y), (center_x + grid_spacing_2, center_y), 1)
        pygame.draw.line(background, grid_color_2, (center_x, center_y - grid_spacing_2), (center_x, center_y + grid_spacing_2), 1)
        vignette_mask = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), flags=pygame.SRCALPHA)
        max_dist = np.sqrt(center_x**2 + center_y**2); vignette_strength = 10
        for r in range(0, int(max_dist), 3):
            alpha = int(vignette_strength * (r / max_dist)**2); color = (0, 0, 0, alpha)
            pygame.draw.circle(vignette_mask, color, (center_x, center_y), r, 5)
        background.blit(vignette_mask, (0, 0))
        return background