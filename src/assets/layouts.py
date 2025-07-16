import numpy as np
from src.constants import *
from src.base import Base

def poll_layout(grid_size, config):
    """
    Generates the 'Y' vs 'N' layout for a standard poll video.
    Returns a grid and a list of Base objects.
    """
    height, width = grid_size
    grid = np.full(grid_size, EMPTY, dtype=np.uint8)

    # Create Base Objects
    blue_base = Base(
        team='blue',
        pivot_y=height // 2,
        pivot_x=60,
        shape_name='Y',
        config=config,
        scale=3.0
    )

    red_base = Base(
        team='red',
        pivot_y=height // 2,
        pivot_x=width - 60,
        shape_name='N',
        config=config,
        scale=3.0
    )
    
    bases = [blue_base, red_base]

    # Stamp initial base shapes onto the grid for rendering
    for base in bases:
        armor_val = BLUE_BASE_ARMOR if base.team == 'blue' else RED_BASE_ARMOR
        core_val = BLUE_BASE_CORE if base.team == 'blue' else RED_BASE_CORE

        for y, x in base.current_armor_pixels:
            if 0 <= y < height and 0 <= x < width:
                grid[y, x] = armor_val
        for y, x in base.current_core_pixels:
            if 0 <= y < height and 0 <= x < width:
                grid[y, x] = core_val

    return grid, bases