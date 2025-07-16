import os
import glob
import subprocess

def assemble_video(frame_dir, audio_path, output_filename, fps):
    """
    Assembles a video from a directory of frames and an audio file using FFmpeg.
    """
    print("\nAssembling video...")
    frame_pattern = os.path.join(frame_dir, "frame_%05d.png")
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
    Deletes all PNG files in a directory and then removes the directory itself.
    """
    print("Cleaning up temporary frame files...")
    try:
        files = glob.glob(os.path.join(frame_dir, '*.png'))
        for f in files:
            os.remove(f)
        if os.path.exists(frame_dir):
            os.rmdir(frame_dir)
        print(f"Removed temporary directory: {frame_dir}")
    except OSError as e:
        print(f"Error during cleanup: {e.strerror}")
    print("Cleanup complete.")