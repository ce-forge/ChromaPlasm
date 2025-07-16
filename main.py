import os
import json
import time
from types import SimpleNamespace
from tqdm import tqdm

from src.constants import *
from src.simulation import Simulation
from src.renderer import Renderer
from src.vfx import VFXManager
from src.audio_manager import AudioManager
from src.video_utils import assemble_video, cleanup_frames

def run_simulation():
    with open('config.json', 'r') as f:
        config_data = json.load(f)

    config = SimpleNamespace(
        **config_data['run_settings'],
        **config_data['engine_settings'],
        **config_data['spawning_settings'],
        **config_data['camera_settings'],
        **config_data['presentation_settings']
    )

    config.video_id = f"{config.video_id_prefix}_{int(time.time())}"


    run_output_dir = os.path.join("output", config.video_id)
    os.makedirs(run_output_dir, exist_ok=True)
    frames_dir = os.path.join(run_output_dir, "frames")
    output_audio_path = os.path.join(run_output_dir, f"audio_{config.video_id}.wav")
    output_video_path = os.path.join(run_output_dir, f"video_{config.video_id}.mp4")

    config.beat_drop_frame = config_data['narrative_cues']['beat_drop_frame']
    
    audio_manager = AudioManager(config)
    vfx_manager = VFXManager(audio_manager)

    sim = Simulation(config, vfx_manager, audio_manager)
    renderer = Renderer(config, output_dir=frames_dir)


    print(f"Generating {config.total_frames} frames for video '{config.video_id}'...")
    print(f"Output will be saved in: {run_output_dir}")
    for _ in tqdm(range(config.total_frames), desc="Rendering Frames"):
        sim.step()
        
        vfx_manager.update_effects()
        
        viewbox = sim.get_viewbox()
        renderer.render_frame(sim.render_grid, vfx_manager, viewbox=viewbox)

    print("\n--- Post-Production ---")
    audio_manager.export_final_track(config.total_frames, config.fps, output_audio_path)
    assemble_video(frames_dir, output_audio_path, output_video_path, config.fps)
    cleanup_frames(frames_dir)
    print("\nProcess Complete.")

if __name__ == '__main__':
    run_simulation()