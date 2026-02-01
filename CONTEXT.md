# DigiJam - Development Context

> Your body is the instrument. AI is the producer.

## Project Vision

DigiJam is a real-time machine vision system that transforms human movement into studio-quality music. Up to three people stand in front of a single webcam, mime their instruments (drums, guitar, or piano), and the system generates professional audio output.

---

## Current Implementation Status

### Completed Components

| Component | Status | Location |
|-----------|--------|----------|
| Pose Detection | ✅ Complete | `multi_person_tracker.py` |
| Drum Detection | ✅ Complete | `classifiers/drum_classifier.py`, `detectors/hit_detector.py` |
| Guitar Detection | ✅ Complete | `classifiers/guitar_classifier.py`, `detectors/strum_detector.py` |
| Piano Detection | ✅ Complete | `classifiers/piano_classifier.py`, `detectors/piano_detector.py` |
| Video Recording | ✅ Complete | `webcam_recorder.py` |
| JSON Logging | ✅ Complete | All classifiers output to `output/` |
| Soundpack Assets | ✅ Complete | `soundpack/` directory |
| Audio Playback | ❌ Missing | Needs integration |
| Vocals | Missing | Will be implemented later down the line |

### Architecture Overview

```
Webcam Input
    ↓
MultiPersonTracker (MediaPipe Pose - 33 landmarks)
    ↓
Instrument-Specific Detector (velocity analysis, zone classification)
    ↓
Classifier (recording, JSON/video output, callbacks)
    ↓
Output (JSON sessions + MP4 video)
    ↓
[NEXT] Audio Engine ← CURRENT STEP
```

---

## Directory Structure

```
spartahacks/
├── classifiers/              # Instrument orchestration
│   ├── drum_classifier.py    # Drum tracking & recording
│   ├── guitar_classifier.py  # Guitar tracking & recording
│   └── piano_classifier.py   # Piano tracking & recording
├── detectors/                # Detection algorithms
│   ├── hit_detector.py       # Drums/piano hit velocity & zones
│   ├── piano_detector.py     # Piano zone & chord mapping
│   ├── pose_detector.py      # Base MediaPipe integration
│   └── strum_detector.py     # Guitar strum & fret tracking
├── soundpack/                # Audio assets
│   ├── drums/
│   │   ├── kick.wav
│   │   ├── hi-hat.wav
│   │   ├── snare.wav
│   │   └── guitar.wav        # Actually crash cymbal
│   ├── guitar/
│   │   ├── C3.wav, C4.wav, C5.wav, C6.wav
│   └── piano/
│       └── C2.wav through C8.wav (7 octaves)
├── output/                   # Recording session outputs
├── multi_person_tracker.py   # Core pose tracking
├── webcam_recorder.py        # Main recording orchestrator
├── webcam_posedetect.py      # CLI entry point
├── requirements.txt
└── README.md
```

---

## Instrument Detection Details

### Drums (`drum_classifier.py` + `hit_detector.py`)

**Detection Method:** Wrist/foot velocity tracking with zone classification

**Zones (body-relative):**
- **Hi-Hat:** Dominant hand above shoulders
- **Crash:** Non-dominant hand above shoulders
- **Snare:** Non-dominant hand between shoulder/hip, near center (±0.35m)
- **Kick:** Foot downward motion after lift

**Parameters:**
- Velocity threshold: 0.25 m/s (hits), 0.15 m/s (kicks)
- Debounce time: 0.12s (hands), 0.18s (feet)

**Output JSON:**
```json
{
  "action": "snare|hi-hat|kick|crash",
  "velocity": 0.6035,
  "hand": "left|right",
  "world_coords_meters": {"x": 0.15, "y": -0.05, "z": -0.13}
}
```

### Guitar (`guitar_classifier.py` + `strum_detector.py`)

**Detection Method:** Auto-calibrating strum detection + fret position tracking

**Calibration:** Automatic on first frame with both hands visible
- Manual recalibration: Press 'g' key

**Fret Calculation:** Every 5cm (0.05m) movement = +1 fret (max 24 frets)

**Parameters:**
- Strum velocity threshold: 0.2 m/s
- Displacement threshold: 0.15m
- Debounce time: 0.15s

**Output JSON:**
```json
{
  "action": "strum",
  "fret": 2,
  "intensity": 1.2442
}
```

### Piano (`piano_classifier.py` + `piano_detector.py`)

**Detection Method:** 7-zone system with manual calibration

**Calibration:** 3-second countdown, user positions hands at virtual piano edges

**Zone Mapping:**
- Right hand → Chord zones 1-7
- Left hand → Octave zones 1-7 (bass)

**Parameters:**
- Hit velocity threshold: 0.15 m/s (upward motion)
- Debounce time: 0.12s
- Minimum piano length: 10cm

**Output JSON:**
```json
{
  "action": "chord|bass",
  "hand": "right|left",
  "chord": 6,
  "octave": 4,
  "intensity": 0.1945
}
```

---

## Soundpack Mapping (To Be Implemented)

### Drums
| Action | Sound File |
|--------|------------|
| kick | `soundpack/drums/kick.wav` |
| hi-hat | `soundpack/drums/hi-hat.wav` |
| snare | `soundpack/drums/snare.wav` |
| crash | `soundpack/drums/guitar.wav` (rename needed) |

### Guitar
| Fret Range | Sound File | Notes |
|------------|------------|-------|
| 0-6 | `soundpack/guitar/C3.wav` | Lowest octave |
| 7-12 | `soundpack/guitar/C4.wav` | |
| 13-18 | `soundpack/guitar/C5.wav` | |
| 19-24 | `soundpack/guitar/C6.wav` | Highest octave |

### Piano
| Zone/Octave | Sound File |
|-------------|------------|
| 1 | `soundpack/piano/C2.wav` |
| 2 | `soundpack/piano/C3.wav` |
| 3 | `soundpack/piano/C4.wav` |
| 4 | `soundpack/piano/C5.wav` |
| 5 | `soundpack/piano/C6.wav` |
| 6 | `soundpack/piano/C7.wav` |
| 7 | `soundpack/piano/C8.wav` |

---

## Callback System (Ready for Audio Integration)

Each classifier has callback hooks that fire on detected actions:

```python
# In webcam_recorder.py
self._on_hit()       # Drum hit detected
self._on_strum()     # Guitar strum detected
self._on_piano_hit() # Piano key hit detected
```

These callbacks receive action data and are the integration point for audio playback.

---

## Current Step: Soundpack Integration

### What Needs to Be Done

1. **Add audio playback engine** (pygame.mixer recommended for low latency)
2. **Load soundpack samples** on startup
3. **Map actions to sounds:**
   - Drums: action name → wav file
   - Guitar: fret range → octave wav file
   - Piano: zone → octave wav file
4. **Apply velocity-to-volume mapping** (0.0-1.0 range based on intensity)
5. **Handle concurrent playback** (multiple hits in quick succession)

### Suggested Implementation

```python
import pygame

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# Load sounds
drum_sounds = {
    'kick': pygame.mixer.Sound('soundpack/drums/kick.wav'),
    'snare': pygame.mixer.Sound('soundpack/drums/snare.wav'),
    'hi-hat': pygame.mixer.Sound('soundpack/drums/hi-hat.wav'),
    'crash': pygame.mixer.Sound('soundpack/drums/guitar.wav'),
}

# Play with velocity-based volume
def play_drum_hit(action, velocity):
    volume = min(1.0, velocity / 2.0)  # Normalize velocity to 0-1
    sound = drum_sounds.get(action)
    if sound:
        sound.set_volume(volume)
        sound.play()
```

---

## Platform Notes

- **Target Platform:** Apple Silicon Macs (M1/M2/M3/M4)
- **Python Version:** 3.x with MediaPipe compatibility
- **Key Dependencies:** mediapipe, opencv-python, numpy

---

## Git History

```
4d7d405  add soundpack; reorganize repo          ← Current
1bc9066  add new instrument functionality: piano
8bfa322  add better drum functionality + guitar functionality
e408a04  add initial webcam feed detection script
f8123d8  initialize mediapipe functionality + basic pose detection
```

---

## Future Roadmap (Post-Audio Integration)

1. **Audio Synthesis & Enhancement**
   - Tempo grid quantization
   - Per-instrument stem generation
   - AI enhancement pipeline (compression, EQ, reverb)

2. **Mixing Console UI**
   - Per-instrument volume faders
   - One-knob effects
   - Genre presets

3. **Music Video Generation**
   - Face snapshot → anime avatar (Stable Diffusion)
   - Gesture-synced animation
   - MP4 export with mixed audio

4. **Multi-Person Support**
   - Zone-based player assignment
   - Up to 3 simultaneous performers (vocals are done seperately)
