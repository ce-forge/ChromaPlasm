import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
import json

# --- Load parameters from your config to match the simulation ---
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    SIGMA = config['engine_settings']['pheromone_blur_sigma']
    print(f"Loaded SIGMA from config.json: {SIGMA}")
except Exception as e:
    SIGMA = 0.5 # Default fallback
    print(f"Could not load config.json, using default SIGMA: {SIGMA}. Error: {e}")

IMAGE_SIZE = 200
TRUNCATE = 2.5 # This matches the value from our last fix in simulation.py

# 1. Create a blank black image with a single bright dot in the middle
print("Creating a test image with a single dot...")
array = np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
array[IMAGE_SIZE // 2, IMAGE_SIZE // 2] = 255.0

# 2. Apply the Gaussian filter, using the same parameters as your simulation
print(f"Applying Gaussian filter with sigma={SIGMA} and truncate={TRUNCATE}...")
blurred_array = gaussian_filter(array, sigma=SIGMA, truncate=TRUNCATE)

# 3. Check if the blur actually did anything
if np.max(blurred_array) > 0:
    # Normalize the blurred array to 0-255 so it's visible as an image
    normalized_blurred = (blurred_array / np.max(blurred_array) * 255).astype(np.uint8)
    blurred_image = Image.fromarray(normalized_blurred, 'L')
    blurred_image.save("test_blurred_output.png")
    print("\nSUCCESS: Saved 'test_blurred_output.png'")
    print("Please open this image file. It should show a soft, blurry circle.")
else:
    print("\nERROR: The blur operation resulted in a completely black image.")