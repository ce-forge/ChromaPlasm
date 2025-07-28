import random
import math

class Particle:
    """A single particle for any visual effect."""
    def __init__(self, y, x, color, lifespan, velocity, p_type='dot'):
        self.y = y
        self.x = x
        self.color = color
        self.lifespan = lifespan
        self.max_lifespan = lifespan
        self.vel = velocity
        self.p_type = p_type
        self.radius = 1.0

    def update(self):
        self.y += self.vel[0]
        self.x += self.vel[1]
        self.lifespan -= 1

class VFXManager:
    """Manages all active visual effects, focusing on particles."""
    def __init__(self, audio_manager):
        self.particles = []
        self.audio_manager = audio_manager

    def create_explosion(self, y, x, color, frame_num, num_particles=5):
        """Creates a simple, performant burst of a few small particles."""
        if y is None or x is None:
            return

        for _ in range(num_particles):
            p_color = tuple(min(255, c + random.randint(60, 110)) for c in color[:3])
            lifespan = random.randint(30, 50)
            velocity = [random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)]
            self.particles.append(Particle(y, x, p_color, lifespan, velocity, p_type='dot'))

        self.audio_manager.add_sfx(frame_num, 'boom')

    def update_effects(self):
        """Update all active particles and remove dead ones."""
        i = len(self.particles) - 1
        while i >= 0:
            p = self.particles[i]
            p.update()
            if p.lifespan <= 0:
                self.particles.pop(i)
            i -= 1