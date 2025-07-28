import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from src.constants import *

class Renderer:
    def __init__(self, config, output_dir="output/frames"):
        self.config = config
        self.output_dir = output_dir
        
        max_key = max(COLOR_MAP.keys())
        default_color = (0, 0, 0, 255)
        self.color_array = np.array([COLOR_MAP.get(i, default_color) for i in range(max_key + 1)], dtype=np.uint8)

        try:
            self.font = ImageFont.truetype(self.config.font_path, self.config.font_size)
        except IOError:
            print(f"Font not found at {self.config.font_path}. Using default font.")
            self.font = ImageFont.load_default()

    def draw_video_ui(self, target_surface):
        """Draws the UI bars and text for the final video onto a given PIL surface."""
        draw = ImageDraw.Draw(target_surface)
        
        ui_bar_color = (15, 15, 20, 255)
        draw.rectangle([0, 0, VIDEO_WIDTH, VIDEO_TOP_MARGIN], fill=ui_bar_color)
        draw.rectangle([0, VIDEO_HEIGHT - VIDEO_BOTTOM_MARGIN, VIDEO_WIDTH, VIDEO_HEIGHT], fill=ui_bar_color)

        text_bbox = draw.textbbox((0, 0), self.config.question_text, font=self.font)
        text_x = (VIDEO_WIDTH - (text_bbox[2] - text_bbox[0])) / 2
        text_y = (VIDEO_TOP_MARGIN - (text_bbox[3] - text_bbox[1])) / 2
        draw.text((text_x, text_y), self.config.question_text, font=self.font, fill=(255, 255, 255, 200))
        
        return target_surface

    def render_frame_to_file(self, sim_grid, vfx_manager, frame_num):
        """Renders a complete frame and saves it to a file for video assembly."""
        # This method would combine the UI drawing and simulation drawing for an offline render.
        # For now, we are focusing on the live dashboard renderer.
        pass