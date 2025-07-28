import numpy as np

# --- TEAM DEFINITIONS (The New Single Source of Truth) ---
# All team-related data is now managed from this list.
TEAMS = [
    {"id": 0, "name": "Azure",    "color": (50, 100, 255), "pheromone_color": (20, 50, 180)},
    {"id": 1, "name": "Crimson",  "color": (255, 50, 50),  "pheromone_color": (180, 20, 20)},
    {"id": 2, "name": "Veridian", "color": (50, 255, 100), "pheromone_color": (20, 180, 50)},
    {"id": 3, "name": "Gold",     "color": (255, 215, 0),  "pheromone_color": (200, 160, 0)},
    {"id": 4, "name": "Amethyst", "color": (153, 50, 204), "pheromone_color": (110, 20, 160)},
    {"id": 5, "name": "Amber",    "color": (255, 126, 0),  "pheromone_color": (200, 100, 0)},
    {"id": 6, "name": "Jade",     "color": (0, 168, 107),  "pheromone_color": (0, 120, 80)},
    {"id": 7, "name": "Sapphire", "color": (15, 82, 186),  "pheromone_color": (10, 60, 140)},
    {"id": 8, "name": "Rose",     "color": (255, 105, 180),"pheromone_color": (200, 80, 140)},
    {"id": 9, "name": "Onyx",     "color": (200, 200, 200),"pheromone_color": (150, 150, 150)},
]

# --- DYNAMIC ID OFFSETS ---
# These ensure that different object types have unique, non-overlapping ID ranges.
EMPTY = 0
SOLDIER_OFFSET = 10
BASE_ARMOR_OFFSET = 100
BASE_CORE_OFFSET = 200

# --- DYNAMICALLY GENERATED MAPPINGS ---
# These dictionaries are now built automatically from the TEAMS list.
COLOR_MAP = { EMPTY: (10, 10, 15, 255) }
TEAM_NAME_TO_ID = {team["name"].lower(): team["id"] for team in TEAMS}
TEAM_ID_TO_NAME = {team["id"]: team["name"] for team in TEAMS}

for team in TEAMS:
    team_id = team["id"]
    # Add a full RGBA tuple to the color map for each dynamically calculated ID
    COLOR_MAP[SOLDIER_OFFSET + team_id] = team["color"] + (255,)
    COLOR_MAP[BASE_ARMOR_OFFSET + team_id] = team["pheromone_color"] + (255,)
    # Programmatically create a lighter core color, similar to the old system
    core_color = tuple(min(255, c + 80) for c in team["pheromone_color"])
    COLOR_MAP[BASE_CORE_OFFSET + team_id] = core_color + (255,)

# --- SIMULATION & RENDERING CONSTANTS (Unchanged) ---
PHEROMONE_SENSE_THRESHOLD = 0.1
EDITOR_GRID_SNAP_SIZE = 10

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
PIXEL_SCALE = 2
VIDEO_TOP_MARGIN = int(VIDEO_HEIGHT * 0.10)
VIDEO_BOTTOM_MARGIN = int(VIDEO_HEIGHT * 0.15)
VIDEO_GAME_AREA_HEIGHT = VIDEO_HEIGHT - VIDEO_TOP_MARGIN - VIDEO_BOTTOM_MARGIN
VIDEO_GAME_AREA_WIDTH = VIDEO_WIDTH

SIM_HEIGHT = VIDEO_GAME_AREA_HEIGHT // PIXEL_SCALE
SIM_WIDTH = VIDEO_GAME_AREA_WIDTH // PIXEL_SCALE

DASHBOARD_WIDTH = 1920
DASHBOARD_HEIGHT = 1080
DASHBOARD_RIGHT_PANEL_WIDTH = 420
DASHBOARD_BOTTOM_PANEL_HEIGHT = 80