import os
import glob
import subprocess
import shutil
import pygame
import pygame_gui

def render_simulation_to_frames(dashboard, frames_folder, total_frames, fps):
    """
    Runs the main offline rendering loop, saving each frame to the specified folder.
    Returns True if completed, False if cancelled.
    """
    print(f"Rendering {total_frames} frames...")
    frame_num = 0
    while frame_num < total_frames and dashboard.is_recording:
        progress_text = f"REC: {frame_num}/{total_frames}"
        dashboard.record_button.set_text(progress_text)
        
        # Step simulation and update VFX
        dashboard.simulation.step(frame_num)
        dashboard.vfx_manager.update_effects()

        # Draw the frame in memory using the renderer
        dashboard.renderer.draw(dashboard.screen, dashboard.simulation, dashboard.vfx_manager, dashboard.viewport, dashboard.show_pheromones, None, False, dashboard.shorts_title_text)
        final_frame = dashboard.renderer.final_render_surface 
        
        # Save the frame to disk
        frame_filename = os.path.join(frames_folder, f"frame_{frame_num:05d}.jpg")
        pygame.image.save(final_frame, frame_filename)
        frame_num += 1

        # Handle events to check for cancellation or quitting
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                dashboard.is_running = False
                dashboard.is_recording = False
            dashboard.ui_manager.process_events(event)
            if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == dashboard.record_button:
                dashboard.is_recording = False
        
        # Keep the UI minimally responsive
        dashboard.ui_manager.update(1/fps)
        dashboard.ui_manager.draw_ui(dashboard.screen)
        pygame.display.flip()

    return dashboard.is_recording

def assemble_video(frame_dir, audio_path, output_filename, fps):
    """
    Assembles a video from a directory of frames and an audio file using FFmpeg.
    """
    print("\nAssembling video...")
    frame_pattern = os.path.join(frame_dir, "frame_%05d.jpg")
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    
    command = [
        'ffmpeg',
        '-framerate', str(fps),
        '-i', frame_pattern,
        '-i', audio_path,
        '-c:v', 'libx264',   # A widely compatible video codec
        '-r', str(fps),      # Set the output frame rate
        '-pix_fmt', 'yuv420p', # Ensures compatibility with most players
        '-c:a', 'aac',       # A common audio codec
        '-shortest',         # Finish encoding when the shortest input stream ends
        '-y',                # Overwrite output file if it exists
        output_filename
    ]
    
    try:
        # Run the command, hiding the noisy ffmpeg output unless there's an error
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("Video assembled successfully!")
        print(f"Video saved to: {output_filename}")
    except subprocess.CalledProcessError as e:
        print("!!! FFmpeg Error !!!")
        print(f"FFmpeg stdout:\n{e.stdout}")
        print(f"FFmpeg stderr:\n{e.stderr}")
    except FileNotFoundError:
        print("!!! FFmpeg Error: command not found. Is FFmpeg installed and in your system's PATH? !!!")

def cleanup_frames(frame_dir):
    """
    Deletes the entire frames directory and its contents.
    """
    print("Cleaning up temporary frame files...")
    try:
        if os.path.isdir(frame_dir):
            # shutil.rmtree is more robust and deletes the folder and all its contents
            shutil.rmtree(frame_dir)
            print(f"Removed temporary directory: {frame_dir}")
    except OSError as e:
        print(f"Error during cleanup: {e.strerror}")
    print("Cleanup complete.")