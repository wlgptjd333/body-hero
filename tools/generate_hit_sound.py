"""
Generate a short punch/hit impact sound (WAV) for the game.
Run once to create assets/sfx_punch_hit.wav
"""
import wave
import struct
import math

SAMPLE_RATE = 44100
DURATION_SEC = 0.12  # short thud
OUT_PATH = "assets/sfx_punch_hit.wav"

def generate_punch_wav():
    n = int(SAMPLE_RATE * DURATION_SEC)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        # Quick attack, then decay (envelope)
        envelope = math.exp(-t * 35) * (1 - math.exp(-t * 120))
        # Mix: low thump (80Hz) + mid punch (200Hz) + short noise burst
        thump = 0.5 * math.sin(2 * math.pi * 80 * t) * envelope
        punch = 0.25 * math.sin(2 * math.pi * 200 * t) * envelope
        # Noise burst in first 20ms
        noise = 0.0
        if i < int(0.02 * SAMPLE_RATE):
            import random
            noise = (random.random() * 2 - 1) * 0.4 * (1 - i / (0.02 * SAMPLE_RATE))
        s = max(-1, min(1, thump + punch + noise))
        samples.append(int(s * 32767))
    with wave.open(OUT_PATH, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for v in samples:
            w.writeframes(struct.pack("<h", v))
    print("Written:", OUT_PATH)

if __name__ == "__main__":
    generate_punch_wav()
