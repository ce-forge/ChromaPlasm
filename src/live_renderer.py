import pygame
import numpy as np
import os
import random
import math
from src.constants import *

class LiveRenderer:
    def __init__(self, config):
        self.config = config
        max_key = max(COLOR_MAP.keys()) if COLOR_MAP else 0
        self.color_array = np.array([COLOR_MAP.get(i, (0,0,0,0))[:3] for i in range(max_key + 1)], dtype=np.uint8)
        self.background_surface = self._create_background_surface()
        self.gradient_surface = self._create_fade_gradient((16, 16, 26), 60, VIDEO_WIDTH)
        self.trail_surface = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
        try:
            self.font_path = self.config.font_path
            self.base_font_size = self.config.font_size
        except AttributeError:
            self.font_path = None
            self.base_font_size = 50

    def _get_transformed_points(self, base, scale_multiplier):
        return [(base.pivot[1] + p[1] * base.scale * scale_multiplier, 
                 base.pivot[0] + p[0] * base.scale * scale_multiplier) for p in base.core_template]

    def draw(self, screen, sim, vfx_manager, viewport, show_pheromones, 
             selected_object=None, is_editing_spawns=False, title_text="", dragged_object=None):
        if viewport.rect.width <= 0 or viewport.rect.height <= 0: return
        
        viewport_surface = pygame.Surface(viewport.rect.size); viewport_surface.fill((10, 10, 15))
        world_surface = self.background_surface.copy()
        
        fade_alpha = getattr(self.config, 'trail_fade_rate', 25)
        fade_surf = pygame.Surface(self.trail_surface.get_size(), pygame.SRCALPHA)
        fade_surf.fill((0, 0, 0, fade_alpha))
        self.trail_surface.blit(fade_surf, (0,0))
        
        alive_mask = sim.agent_health[:sim.agent_count] > 0
        positions = sim.agent_positions[:sim.agent_count][alive_mask]
        teams = sim.agent_teams[:sim.agent_count][alive_mask]
        
        if show_pheromones:
            for p_surf in sim.pheromone_surfaces.values():
                self.trail_surface.blit(p_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        agent_radius = getattr(self.config, 'agent_size', 1.5)
        glow_intensity = getattr(self.config, 'glow_intensity', 255)

        for i in range(len(positions)):
            pos_x, pos_y = positions[i][1], positions[i][0]
            color = (*TEAMS[teams[i]]['color'], glow_intensity)
            pygame.draw.circle(self.trail_surface, color, (float(pos_x), float(pos_y)), agent_radius, 0)
        
        world_surface.blit(self.trail_surface, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

        base_surface = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
        # ... (The correct base rendering logic is here) ...
        for base in sim.bases:
            is_damaged = (sim.frame_count - base.last_damage_frame) < 5
            armor_color = (255, 255, 255) if is_damaged else TEAMS[base.team_id]['pheromone_color']
            core_color_base = COLOR_MAP[BASE_CORE_OFFSET + base.team_id][:3]
            for y, x in base.current_armor_pixels: base_surface.set_at((x, y), armor_color)
            for y, x in base.current_core_pixels: base_surface.set_at((x, y), TEAMS[base.team_id]['pheromone_color'])
            pulse = (np.sin(sim.frame_count * 0.05 + base.team_id) + 1) / 2
            if base.team_id in sim.dead_teams: pulse = 0.0
            if base.shape_type == 'polygon':
                num_layers = 5; min_brightness = 0.7; max_brightness = 1.5
                dynamic_max_brightness = max_brightness + pulse * 2.0; brightness_range = dynamic_max_brightness - min_brightness
                for i in range(num_layers, 0, -1):
                    t = i / num_layers; layer_brightness = min_brightness + (1.0 - t) * brightness_range
                    layer_color = tuple(min(255, max(0, int(c * layer_brightness))) for c in core_color_base)
                    layer_scale = 1.0 * t; points = self._get_transformed_points(base, layer_scale)
                    if len(points) > 2: pygame.draw.polygon(base_surface, layer_color, points, width=0)
            else:
                core_thickness_pixels = max(1, int(base.core_thickness * 2)); brightness = 1.0 + pulse * 0.6
                core_color = tuple(min(255, int(c * brightness)) for c in core_color_base)
                for p1, p2 in base.core_template:
                    y1, x1 = base.pivot[0] + p1[0] * base.scale, base.pivot[1] + p1[1] * base.scale
                    y2, x2 = base.pivot[0] + p2[0] * base.scale, base.pivot[1] + p2[1] * base.scale
                    pygame.draw.line(base_surface, core_color, (x1, y1), (x2, y2), core_thickness_pixels)
        
        world_surface.blit(base_surface, (0,0))
        
        final_render_surface = pygame.Surface((VIDEO_WIDTH, VIDEO_HEIGHT), pygame.SRCALPHA)
        scaled_world = pygame.transform.scale(world_surface, (VIDEO_GAME_AREA_WIDTH, VIDEO_GAME_AREA_HEIGHT))
        final_render_surface.blit(scaled_world, (0, VIDEO_TOP_MARGIN))
        
        for p in vfx_manager.particles:
            if hasattr(p, 'y') and p.y is not None:
                screen_x = p.x * PIXEL_SCALE
                screen_y = p.y * PIXEL_SCALE + VIDEO_TOP_MARGIN
                alpha = int(255 * (p.lifespan / p.max_lifespan)); size = max(1.0, p.radius * PIXEL_SCALE * 0.5)
                particle_surf = pygame.Surface((size, size), pygame.SRCALPHA); particle_surf.fill((*p.color[:3], alpha))
                final_render_surface.blit(particle_surf, (screen_x - size/2, screen_y - size/2))
        
        top_margin_rect = pygame.Rect(0, 0, VIDEO_WIDTH, VIDEO_TOP_MARGIN)
        bottom_margin_rect = pygame.Rect(0, VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN, VIDEO_WIDTH, VIDEO_BOTTOM_MARGIN)
        margin_color = (16, 16, 26, 220)
        pygame.draw.rect(final_render_surface, margin_color, top_margin_rect)
        pygame.draw.rect(final_render_surface, margin_color, bottom_margin_rect)
        final_render_surface.blit(self.gradient_surface, (0, VIDEO_TOP_MARGIN))
        bottom_gradient = pygame.transform.flip(self.gradient_surface, False, True)
        final_render_surface.blit(bottom_gradient, (0, VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN - self.gradient_surface.get_height()))

        active_teams_in_scene = sorted(list(set(base.team_id for base in sim.bases)))

        try:
            font_scale = VIDEO_HEIGHT / 1920.0
            title_font_size = int(self.base_font_size * font_scale * 0.6)
            title_font = pygame.font.Font(self.font_path, title_font_size)
            title_surf = title_font.render(title_text, True, (220, 220, 230))
            text_rect = title_surf.get_rect(centerx=top_margin_rect.centerx, y=top_margin_rect.y + top_margin_rect.height * 0.15)
            final_render_surface.blit(title_surf, text_rect)
            
            if active_teams_in_scene:
                # --- This section now uses your preferred layout logic ---
                groups = {}; [groups.setdefault(sim.alliance_map[tid], []).append(tid) for tid in active_teams_in_scene]
                
                # Define initial sizes based on your backend logic
                symbol_size = int(top_margin_rect.height * 0.32)
                padding = int(symbol_size * 0.5)
                div_width = int(symbol_size * 0.3)
                
                # Calculate initial width
                total_width = sum(len(teams) * (symbol_size + padding) for teams in groups.values()) - padding
                if len(groups) > 1:
                    total_width += (len(groups) - 1) * (div_width + padding * 2)

                # --- NEW: Dynamic Scaling ("Squishing") ---
                available_width = top_margin_rect.width * 0.90 # Use 90% of the margin width
                scale_factor = 1.0
                if total_width > available_width:
                    scale_factor = available_width / total_width
                    # Apply scale factor to all horizontal measurements
                    symbol_size = int(symbol_size * scale_factor)
                    padding = int(padding * scale_factor)
                    div_width = int(div_width * scale_factor)
                    # Recalculate the final width with the new scaled sizes
                    total_width = sum(len(teams) * (symbol_size + padding) for teams in groups.values()) - padding
                    if len(groups) > 1:
                        total_width += (len(groups) - 1) * (div_width + padding * 2)

                # Center the entire UI block using your backend logic
                x_pos = top_margin_rect.centerx - total_width // 2
                first_group = True
                
                for aid in sorted(groups.keys()):
                    if not first_group and len(groups) > 1:
                        pygame.draw.line(final_render_surface, (150, 150, 160), 
                                         (x_pos + padding, top_margin_rect.bottom - (symbol_size*1.1) - padding), 
                                         (x_pos + padding, top_margin_rect.bottom - padding), 2)
                        x_pos += div_width + padding * 2

                    for team_id in groups[aid]:
                        team, color = TEAMS[team_id], TEAMS[team_id]['color']
                        y_pos = top_margin_rect.bottom - symbol_size - padding
                        
                        border_rect = pygame.Rect(x_pos - 1, y_pos - 1, symbol_size + 2, symbol_size + 2)
                        pygame.draw.rect(final_render_surface, (10, 10, 15), border_rect, 0)
                        symbol_rect = pygame.Rect(x_pos, y_pos, symbol_size, symbol_size)
                        
                        if team_id in sim.dead_teams:
                            faded_symbol = pygame.Surface(symbol_rect.size, pygame.SRCALPHA)
                            faded_symbol.fill((*color, 128))
                            final_render_surface.blit(faded_symbol, symbol_rect.topleft)
                            pygame.draw.line(final_render_surface, (255, 50, 50), symbol_rect.topleft, symbol_rect.bottomright, 4)
                            pygame.draw.line(final_render_surface, (255, 50, 50), symbol_rect.topright, symbol_rect.bottomleft, 4)
                        else:
                            pygame.draw.rect(final_render_surface, color, symbol_rect)
                        
                        # --- MODIFIED: Kill count now uses the new visual style ---
                        kill_count = sim.kill_counts[team_id]
                        # Font size is also scaled down if the UI is squished
                        tally_font_size = int(symbol_size * 0.65 * (scale_factor**0.5)) # scale_factor**0.5 softens the text shrinking
                        tally_font = pygame.font.Font(self.font_path, tally_font_size)
                        # Text is always white for readability
                        tally_surf = tally_font.render(str(kill_count), True, (220, 220, 230))
                        tally_rect = tally_surf.get_rect(midtop=symbol_rect.midbottom)
                        final_render_surface.blit(tally_surf, tally_rect)
                        
                        x_pos += symbol_size + padding
                    first_group = False
        except (AttributeError, FileNotFoundError, TypeError) as e:
            print(f"Error drawing top UI: {e}")

        try:
            total_seconds = sim.config.total_frames / sim.config.fps; current_seconds = sim.frame_count / sim.config.fps
            seconds_remaining = max(0, total_seconds - current_seconds); minutes = int(seconds_remaining // 60); seconds = int(seconds_remaining % 60)
            timer_text = f"{minutes:02d}:{seconds:02d}"; bar_width = bottom_margin_rect.width * 0.4; bar_height = 8
            bar_x = bottom_margin_rect.centerx - bar_width / 2; bar_y = bottom_margin_rect.top + 30
            bg_bar_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height); pygame.draw.rect(final_render_surface, (10, 10, 15), bg_bar_rect)
            progress = current_seconds / total_seconds; fg_bar_width = bar_width * (1 - progress)
            fg_bar_rect = pygame.Rect(bar_x, bar_y, fg_bar_width, bar_height); pygame.draw.rect(final_render_surface, (200, 200, 220), fg_bar_rect)
            pygame.draw.rect(final_render_surface, (80, 80, 100), bg_bar_rect, 1)
            font_scale = VIDEO_HEIGHT / 1920.0; timer_font_size = int(self.base_font_size * font_scale * 0.7)
            timer_font = pygame.font.Font(self.font_path, timer_font_size); timer_surf = timer_font.render(timer_text, True, (220, 220, 230))
            timer_rect = timer_surf.get_rect(centerx=bottom_margin_rect.centerx, bottom=bar_y - 5); final_render_surface.blit(timer_surf, timer_rect)
        except (AttributeError, FileNotFoundError, TypeError): pass

        zoom = viewport.zoom
        scaled_final_surf = pygame.transform.scale(final_render_surface, (int(VIDEO_WIDTH * zoom), int(VIDEO_HEIGHT * zoom)))
        blit_x = (viewport.rect.width / 2) - viewport.offset_x * PIXEL_SCALE * zoom; blit_y = (viewport.rect.height / 2) - viewport.offset_y * PIXEL_SCALE * zoom
        viewport_surface.blit(scaled_final_surf, (blit_x, blit_y)); pygame.draw.rect(viewport_surface, (200, 200, 220), pygame.Rect(blit_x, blit_y, scaled_final_surf.get_width(), scaled_final_surf.get_height()), 2)

        if dragged_object:
            core_color = COLOR_MAP[BASE_CORE_OFFSET + dragged_object.team_id]
            for y,x in dragged_object.current_core_pixels:
                screen_x = blit_x + ((x * PIXEL_SCALE) * zoom); screen_y = blit_y + ((y * PIXEL_SCALE + VIDEO_TOP_MARGIN) * zoom)
                pygame.draw.rect(viewport_surface, core_color, (screen_x, screen_y, PIXEL_SCALE*zoom, PIXEL_SCALE*zoom))
        if selected_object and not is_editing_spawns:
            highlight_color = (255, 255, 0)
            for y,x in selected_object.rim_pixels:
                screen_x = blit_x + ((x * PIXEL_SCALE) * zoom); screen_y = blit_y + ((y * PIXEL_SCALE + VIDEO_TOP_MARGIN) * zoom)
                pygame.draw.rect(viewport_surface, highlight_color, (screen_x, screen_y, PIXEL_SCALE*zoom, PIXEL_SCALE*zoom), 1)
        if is_editing_spawns and selected_object:
             port_color = (255, 255, 0)
             for y, x in selected_object.exit_ports:
                screen_x = blit_x + ((x * PIXEL_SCALE) * zoom); screen_y = blit_y + ((y * PIXEL_SCALE + VIDEO_TOP_MARGIN) * zoom)
                pygame.draw.circle(viewport_surface, port_color, (screen_x, screen_y), int(max(2, 6 * zoom)), 2)
        
        if sim.winner_info is not None:
            overlay_surf = pygame.Surface(scaled_final_surf.get_size(), pygame.SRCALPHA)
            overlay_surf.fill((10, 10, 15, 180))
            try:
                winner_id, win_reason = sim.winner_info['id'], sim.winner_info['reason']
                line1_text, line2_text, winner_color = "", "", (200, 200, 200)

                if winner_id == -1:
                    line1_text = "STALEMATE"
                    line2_text = "Time expired with no victor"
                else:
                    winner_name = TEAMS[winner_id]['name'].upper()
                    winner_color = TEAMS[winner_id]['color']
                    line1_text = winner_name
                    if win_reason == 'elimination': line2_text = "is the last one standing!"
                    else: line2_text = "was the most hungry!"
                
                font_scale = scaled_final_surf.get_height() / 1920.0
                line1_font_size = int(120 * font_scale)
                line2_font_size = int(70 * font_scale)
                
                font1 = pygame.font.Font(self.font_path, line1_font_size)
                font2 = pygame.font.Font(self.font_path, line2_font_size)

                line1_surf = font1.render(line1_text, True, winner_color)
                line2_surf = font2.render(line2_text, True, (220, 220, 230))
                
                center_x = scaled_final_surf.get_width() / 2
                center_y = scaled_final_surf.get_height() / 2
                
                line1_rect = line1_surf.get_rect(centerx=center_x, centery=center_y - (line1_surf.get_height() / 2))
                line2_rect = line2_surf.get_rect(centerx=center_x, top=line1_rect.bottom)

                overlay_surf.blit(line1_surf, line1_rect)
                overlay_surf.blit(line2_surf, line2_rect)

            except (AttributeError, FileNotFoundError, TypeError) as e: print(f"Error rendering winner screen: {e}")
            viewport_surface.blit(overlay_surf, (blit_x, blit_y))

        screen.blit(viewport_surface, viewport.rect.topleft)



    def _create_fade_gradient(self, color, height, width):
        gradient = pygame.Surface((width, height), pygame.SRCALPHA);
        for y in range(height): alpha = 255 - int((y / height) * 255); pygame.draw.line(gradient, (*color, alpha), (0, y), (width, y))
        return gradient

    def _create_background_surface(self):
        background = pygame.Surface((SIM_WIDTH, SIM_HEIGHT)); background.fill((16, 16, 26)); center_x, center_y = SIM_WIDTH // 2, SIM_HEIGHT // 2
        
        # --- FIX: Implement centering logic for both grid layers ---
        
        # Layer 1: Fine grid
        grid_color_1 = (35, 35, 50); grid_spacing_1 = 10
        num_x_lines_1 = (SIM_WIDTH // grid_spacing_1) + 1
        num_y_lines_1 = (SIM_HEIGHT // grid_spacing_1) + 1
        grid_width_1 = (num_x_lines_1 - 1) * grid_spacing_1
        grid_height_1 = (num_y_lines_1 - 1) * grid_spacing_1
        offset_x_1 = (SIM_WIDTH - grid_width_1) // 2
        offset_y_1 = (SIM_HEIGHT - grid_height_1) // 2
        for i in range(num_x_lines_1): pygame.draw.line(background, grid_color_1, (offset_x_1 + i * grid_spacing_1, 0), (offset_x_1 + i * grid_spacing_1, SIM_HEIGHT))
        for i in range(num_y_lines_1): pygame.draw.line(background, grid_color_1, (0, offset_y_1 + i * grid_spacing_1), (SIM_WIDTH, offset_y_1 + i * grid_spacing_1))

        # Layer 2: Thicker accent grid
        grid_color_2 = (45, 55, 80); line_thickness_2 = 2; grid_spacing_2 = 100
        num_x_lines_2 = (SIM_WIDTH // grid_spacing_2) + 1
        num_y_lines_2 = (SIM_HEIGHT // grid_spacing_2) + 1
        grid_width_2 = (num_x_lines_2 - 1) * grid_spacing_2
        grid_height_2 = (num_y_lines_2 - 1) * grid_spacing_2
        offset_x_2 = (SIM_WIDTH - grid_width_2) // 2
        offset_y_2 = (SIM_HEIGHT - grid_height_2) // 2
        for i in range(num_x_lines_2): pygame.draw.line(background, grid_color_2, (offset_x_2 + i * grid_spacing_2, 0), (offset_x_2 + i * grid_spacing_2, SIM_HEIGHT), line_thickness_2)
        for i in range(num_y_lines_2): y_pos = offset_y_2 + i * grid_spacing_2; pygame.draw.line(background, grid_color_2, (0, y_pos), (SIM_WIDTH, y_pos), line_thickness_2)
        
        # Center decorations
        pygame.draw.circle(background, grid_color_2, (center_x, center_y), grid_spacing_2 // 2, 1)
        pygame.draw.line(background, grid_color_2, (center_x - grid_spacing_2, center_y), (center_x + grid_spacing_2, center_y), 1)
        pygame.draw.line(background, grid_color_2, (center_x, center_y - grid_spacing_2), (center_x, center_y + grid_spacing_2), 1)

        # Vignette
        vignette_mask = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), flags=pygame.SRCALPHA)
        max_dist = np.sqrt(center_x**2 + center_y**2); vignette_strength = 220
        for r in range(0, int(max_dist), 3):
            alpha = int(vignette_strength * (r / max_dist)**2); color = (0, 0, 0, alpha)
            pygame.draw.circle(vignette_mask, color, (center_x, center_y), r, 5)
        background.blit(vignette_mask, (0, 0))
        return background