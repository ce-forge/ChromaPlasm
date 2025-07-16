import random
import math

class Particle:
    """A single particle for any visual effect."""
    def __init__(self, y, x, color, lifespan, velocity):
        self.pos = [y, x]
        self.color = color
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.vel = velocity
        self.alpha = 255.0

    def update(self):
        self.pos[0] += self.vel[0]
        self.pos[1] += self.vel[1]
        self.lifespan -= 1
        if self.max_lifespan > 0:
            self.alpha = 255 * (self.lifespan / self.max_lifespan)
        else:
            self.alpha = 0

class VFXManager:
    """Manages all active visual effects."""
    def __init__(self, audio_manager):
        self.particles = []
        self.audio_manager = audio_manager

    def create_explosion(self, y, x, color, frame_num, num_particles=15):
        """Creates a small, chaotic burst of particles."""
        if y is None or x is None:
            print(f"!!! VFX WARNING: create_explosion called with invalid coordinates. Skipping. !!!")
            return

        for _ in range(num_particles):
            # Make the explosion particles brighter than the unit color
            bright_color = tuple(min(255, c + 80) for c in color[:3])
            lifespan = random.randint(15, 30)
            velocity = [random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)]
            self.particles.append(Particle(y, x, bright_color, lifespan, velocity))
        
        # Trigger a sound event, making core hits sound bigger
        sound_to_play = 'boom' if num_particles >= 8 else 'pop'
        self.audio_manager.add_sfx(frame_num, sound_to_play)

    def update_effects(self):
        """Update all active particles and remove the dead ones."""
        # Process list in place for efficiency
        i = len(self.particles) - 1
        while i >= 0:
            p = self.particles[i]
            p.update()
            if p.lifespan <= 0:
                self.particles.pop(i)
            i -= 1