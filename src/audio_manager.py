import numpy as np
from pydub import AudioSegment
import random
import os

# This explicit setting is robust and good to keep.
try:
    AudioSegment.converter = "ffmpeg"
except FileNotFoundError:
    print("!!! pydub could not find FFmpeg. Exporting audio will fail. !!!")

class AudioManager:
    """
    Manages a main soundtrack, procedural sound effects, and a timeline of cues
    to synchronize the simulation with audio events.
    """
    def __init__(self, config):
        self.config = config
        self.sample_rate = 44100

        # --- Soundtrack ---
        self.main_track = None
        self._load_soundtrack() # Placeholder for loading a main song

        # --- Procedural SFX ---
        self.sfx_events = []

        # --- Cue Timeline ---
        # A list of tuples: (frame_number, event_name, data)
        # This is the core of the new system.
        self.cue_points = []
        self._generate_initial_cues() # Placeholder for pre-generating cues

    def _load_soundtrack(self):
        """
        Placeholder for loading a main audio file (e.g., an MP3).
        In the future, this will load from a path in the config.
        For now, it does nothing.
        """
        pass

    def _generate_initial_cues(self):
        """
        Placeholder for analyzing a soundtrack or loading pre-defined cues.
        This is where you would do beat detection on self.main_track.
        For now, we can manually add a cue from the config for demonstration.
        """
        beat_drop_frame = getattr(self.config, 'beat_drop_frame', None)
        if beat_drop_frame:
            print(f"Audio Cue: Scheduled 'BEAT_DROP' event at frame {beat_drop_frame}.")
            self.cue_points.append((beat_drop_frame, 'BEAT_DROP', {}))

    def get_cues_for_frame(self, frame_num):
        """
        Called by the simulation every frame to check for events.
        Returns a list of all events scheduled for the current frame.
        """
        triggered_cues = []
        for cue_frame, event_name, data in self.cue_points:
            if cue_frame == frame_num:
                triggered_cues.append({'event': event_name, 'data': data})
        return triggered_cues

    # --- SFX Generation ---
    def add_sfx(self, frame_num, sfx_name, custom_params=None):
        """Logs a request to play a procedural sound effect."""
        self.sfx_events.append({
            'frame': frame_num,
            'name': sfx_name,
            'params': custom_params or {}
        })

    def _generate_sfx(self, sfx_name, params):
        """Generates the actual sound wave for a requested SFX."""
        pitch_var = params.get('pitch_variation', random.uniform(-15, 15))
        if sfx_name == 'pop':
            return self._generate_pop(pitch_variation=pitch_var)
        if sfx_name == 'boom':
            return self._generate_boom(pitch_variation=pitch_var)
        if sfx_name == 'crack':
            return self._generate_crack(pitch_variation=pitch_var)
        return None

    def export_final_track(self, total_frames, fps, output_path):
        """Builds and exports the complete audio track."""
        duration_ms = (total_frames / fps) * 1000
        
        # Start with the main soundtrack, or silence if none is loaded.
        if self.main_track and len(self.main_track) > 0:
            # Trim or pad the main track to match the video length
            final_track = self.main_track[:duration_ms]
            if len(final_track) < duration_ms:
                final_track += AudioSegment.silent(duration=duration_ms - len(final_track))
        else:
            final_track = AudioSegment.silent(duration=duration_ms)

        # Overlay the procedural SFX
        if self.sfx_events:
            print(f"Overlaying {len(self.sfx_events)} sound effects...")
            for event in self.sfx_events:
                sound = self._generate_sfx(event['name'], event['params'])
                if sound:
                    position_ms = (event['frame'] / fps) * 1000
                    final_track = final_track.overlay(sound - 8, position=position_ms)
        
        print(f"Attempting to export final audio mix to: {output_path}")
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            final_track.export(output_path, format="wav")
            print(f"SUCCESS: Audio track saved to {output_path}")
            return True
        except Exception as e:
            print(f"!!! CRITICAL ERROR during audio export: {e} !!!")
            return False

    def _generate_pop(self, pitch_variation=0):
        frequency = 500 + pitch_variation; duration_s = 0.08
        t = np.linspace(0., duration_s, int(self.sample_rate * duration_s), endpoint=False)
        envelope = np.exp(-t * 60); tone = np.sin(2. * np.pi * frequency * t); noise = np.random.uniform(-1, 1, len(t)) * 0.8
        data = (tone * 0.2 + noise) * envelope; amplitude = np.iinfo(np.int16).max * 0.4
        data = (np.clip(data, -1, 1) * amplitude).astype(np.int16)
        return AudioSegment(data.tobytes(), frame_rate=self.sample_rate, sample_width=2, channels=1)

    def _generate_boom(self, pitch_variation=0):
        frequency = 70 + pitch_variation; duration_s = 0.3
        t = np.linspace(0., duration_s, int(self.sample_rate * duration_s), endpoint=False)
        envelope = np.exp(-t * 15); data = np.sin(2. * np.pi * frequency * t)
        data += np.sin(2. * np.pi * (frequency * 1.5) * t) * 0.5; data *= envelope
        amplitude = np.iinfo(np.int16).max * 0.6; data = (np.clip(data, -1, 1) * amplitude).astype(np.int16)
        return AudioSegment(data.tobytes(), frame_rate=self.sample_rate, sample_width=2, channels=1)
    
    def _generate_crack(self, pitch_variation=0):
        """Generates a multi-layered, crunchy sound for armor hits."""
        duration_s = 0.2
        t = np.linspace(0., duration_s, int(self.sample_rate * duration_s), endpoint=False)
        
        # 1. The initial "crack" - a sharp burst of noise
        noise = np.random.uniform(-1, 1, len(t))
        crack_envelope = np.exp(-t * 200) # Very fast decay
        crack_sound = noise * crack_envelope

        # 2. The metallic "ring" - two detuned high-frequency sine waves
        freq1 = 880 + pitch_variation
        freq2 = freq1 * 1.505 # A slightly detuned musical fifth for a metallic sound
        ring_tone = (np.sin(2. * np.pi * freq1 * t) * 0.5 + 
                     np.sin(2. * np.pi * freq2 * t) * 0.5)
        ring_envelope = np.exp(-t * 30) # Slower decay
        ring_sound = ring_tone * ring_envelope
        
        # 3. Mix the two parts together, with the crack being more prominent
        data = crack_sound * 0.6 + ring_sound * 0.4
        
        # 4. Normalize the audio to prevent clipping and ensure it's audible
        peak = np.max(np.abs(data))
        if peak > 0:
            data /= peak # Normalize to a range of [-1, 1]
        
        # 5. Set amplitude and convert to 16-bit format for pydub
        amplitude = np.iinfo(np.int16).max * 0.5 # 50% volume
        data_16bit = (data * amplitude).astype(np.int16)
        
        return AudioSegment(data_16bit.tobytes(), frame_rate=self.sample_rate, sample_width=2, channels=1)
