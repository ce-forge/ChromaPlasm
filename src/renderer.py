import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from src.constants import *

class Renderer:
    def __init__(self, config, output_dir="output/frames"):
        self.config = config
        self.output_dir = output_dir
        self.frame_count = 0
        os.makedirs(self.output_dir, exist_ok=True)

        # Create a color mapping array for fast color conversion
        # This is much faster than a dictionary lookup for every pixel.
        max_key = max(COLOR_MAP.keys())
        default_color = (0, 0, 0, 255) # Black for any undefined grid states
        self.color_array = np.array([COLOR_MAP.get(i, default_color) for i in range(max_key + 1)], dtype=np.uint8)

        # Load font for UI text
        try:
            self.font = ImageFont.truetype(self.config.font_path, self.config.font_size)
        except IOError:
            print(f"Font not found at {self.config.font_path}. Using default font.")
            self.font = ImageFont.load_default()
        self.question_text = self.config.question_text

    def render_frame(self, sim_grid, vfx_manager, viewbox=None, ui_info={}):
        """
        Renders a single frame. Can optionally render a zoomed-in 'viewbox'.
        """
        # --- Step 1: Select the grid area to render ---
        render_grid = sim_grid
        if viewbox:
            vy, vx, vh, vw = viewbox
            # Slice the simulation grid to get the viewbox area
            if vh > 0 and vw > 0:
                render_grid = sim_grid[vy:vy+vh, vx:vx+vw]

        # --- Step 2: Convert grid states to colors ---
        # Use the pre-built color array for a massive speedup
        game_area_pixels = self.color_array[render_grid]
        game_area_image = Image.fromarray(game_area_pixels, 'RGBA')

        # --- Step 3: Scale the image up to the final game area resolution ---
        scaled_game_image = game_area_image.resize(
            (GAME_AREA_WIDTH, GAME_AREA_HEIGHT),
            Image.Resampling.NEAREST  # Use NEAREST for a sharp, pixelated look
        )

        # --- Step 4: Create the final canvas and add UI bars ---
        final_canvas = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 255))
        draw = ImageDraw.Draw(final_canvas)
        ui_bar_color = (15, 15, 20, 255) # Slightly different from the sim background
        draw.rectangle([0, 0, VIDEO_WIDTH, TOP_MARGIN], fill=ui_bar_color)
        draw.rectangle([0, VIDEO_HEIGHT - BOTTOM_MARGIN, VIDEO_WIDTH, VIDEO_HEIGHT], fill=ui_bar_color)

        # Draw the question text in the top bar
        text_bbox = draw.textbbox((0, 0), self.question_text, font=self.font)
        text_x = (VIDEO_WIDTH - (text_bbox[2] - text_bbox[0])) / 2
        text_y = (TOP_MARGIN - (text_bbox[3] - text_bbox[1])) / 2
        draw.text((text_x, text_y), self.question_text, font=self.font, fill=(255, 255, 255, 200))

        # --- Step 5: Paste the scaled game area onto the canvas ---
        final_canvas.paste(scaled_game_image, (0, TOP_MARGIN))

        # --- Step 6: Draw VFX on top of everything ---
        draw_vfx = ImageDraw.Draw(final_canvas)
        for p in vfx_manager.particles:
            # Adjust particle position based on the viewbox
            particle_y, particle_x = p.pos[0], p.pos[1]
            if viewbox:
                vy, vx, vh, vw = viewbox
                particle_y -= vy
                particle_x -= vx
            
            # Scale particle position to the final render size
            if render_grid.shape[0] > 0 and render_grid.shape[1] > 0:
                px = int(particle_x * (GAME_AREA_WIDTH / render_grid.shape[1]))
                py = int(particle_y * (GAME_AREA_HEIGHT / render_grid.shape[0])) + TOP_MARGIN
            
                # Only draw particle if it's visible in the final canvas
                if 0 <= px < VIDEO_WIDTH and TOP_MARGIN <= py < VIDEO_HEIGHT - BOTTOM_MARGIN:
                    alpha = int(255 * (p.lifespan / p.max_lifespan))
                    particle_color = p.color[:3] + (alpha,)
                    draw_vfx.rectangle([px, py, px + PIXEL_SCALE-1, py + PIXEL_SCALE-1], fill=particle_color)
        
        # --- Step 7: Save the final image ---
        file_path = os.path.join(self.output_dir, f"frame_{self.frame_count:05d}.png")
        final_canvas.save(file_path)
        self.frame_count += 1