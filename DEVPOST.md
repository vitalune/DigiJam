# 🎸 DigiJam

**Your body is the instrument. AI is the producer.**

---

We turned air guitar into a freaking album.

DigiJam is a real-time machine vision system that transforms human movement into studio-quality music videos — no instruments, no training, no limits. Up to four people stand in front of a single webcam, mime their instruments, and walk away with a professionally mixed track and an AI-generated anime music video of their performance.

**Heads up, this isn't a toy.**

---

## 🔥 How It Works

### 1. Band Assembly
- Users select their instrument: **Drums**, **Guitar**, **Piano**, or **Vocals**
- Everyone positions themselves in front of a single webcam
- Our **multi-person tracking system** locks onto each performer and assigns them to spatial zones

### 2. Performance Capture
- **MediaPipe pose estimation** tracks 33 body landmarks per person at 30+ FPS
- Instrument-specific classifiers detect musical gestures in real-time:
  - `drum_classifier.py` → Detects hits, identifies snare/kick/hi-hat zones based on hand position and velocity
  - `guitar_classifier.py` + `strum_detector.py` → Tracks strumming patterns, chord hand positioning, and attack intensity
  - `piano_classifier.py` + `piano_detector.py` → Maps finger movements across a virtual keyboard space
- Every detected gesture is logged with **millisecond-precision timestamps** to structured JSON

### 3. Audio Synthesis
- Gesture JSON is **quantized to a tempo grid** (8th/16th notes) for rhythmic coherence
- Each event triggers from a curated **instrument soundpack**
- Stems are generated per instrument and run through our **AI enhancement pipeline**:
  - Dynamic compression and EQ
  - Reverb and spatial positioning
  - Intelligent fill generation for sparse sections

### 4. The Mixing Console 🎛️
- Users access a **beginner-friendly dashboard** with:
  - Per-instrument volume faders
  - One-knob effects (reverb, drive, width)
  - Genre presets (Rock, Lo-Fi, J-Pop, Electronic)
- No audio engineering experience required — if you can use a slider, you can mix a track

### 5. Music Video Generation 🎬
- Face snapshots from the performance are transformed into **anime-style avatars** via generative AI
- Avatars are composited onto a dynamic stage background
- Character animations are **synced to detected gesture timestamps**
- Final output: a shareable MP4 music video with the mixed master track

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| Pose Detection | MediaPipe Holistic, OpenCV |
| Multi-Person Tracking | Custom zone-based tracking system |
| Gesture Classification | Velocity-threshold classifiers, temporal pattern matching |
| Audio Engine | Quantized sample triggering, stem mixing |
| AI Enhancement | Dynamic processing, intelligent arrangement |
| Avatar Generation | Stable Diffusion (anime checkpoint) |
| Video Composition | Frame-by-frame rendering with gesture-synced animation |

---

## Who is Savvy Addy?

Three builders. One vision. A Greyhound bus that smelled like regret.

I'm Amir — the AI/ML engineer on this team. I spend my days pushing the limits of what's possible with modern coding tools and AI-assisted engineering. Andrej Karpathy, the guy who built Tesla's Autopilot and is genuinely one of the most inspiring minds in AI, recently said he feels *behind* with how fast the tooling landscape is evolving. That lit a fire under me. I'm fighting hard to catch up to him and prove that it's possible to fully harness everything these new tools offer. **DigiJam is that proof.**

**Gyan** is our secret weapon. Experienced musician, relentless creative, and an engineer who doesn't know how to quit. When we needed someone who *gets* music at a gut level and can translate that into systems — Gyan showed up and delivered. Every time.

**Ash** is the orchestrator. Brilliant logician, sharp project manager, and the guy who keeps the train on the tracks. He's fundraised **five-digit profit figures** before — so when I say he knows how to execute, I mean he *knows how to execute*. No further explanation needed.

When we were brainstorming project ideas, something clicked. DigiJam wasn't just a cool concept — it was the most harmonious fusion of everything we're individually great at. Music. Systems. AI. Execution.

Gyan and I believed in it so much that we got on a **Greyhound bus from Pittsburgh to Detroit** — 6+ hours, questionable passengers, smells we're still recovering from — just to make this happen. Ash believed in it so much that he let two borderline strangers crash in his dorm room for two nights and drove us around for hours.

That's Savvy Addy. We don't just talk about ideas. We get on the sketchy bus. 

---

## 🚀 Why DigiJam?

Music creation has gatekeepers: expensive instruments, years of practice, access to studios. We're removing all of them.

With DigiJam, a group of friends at a party can produce a music video in under 5 minutes. A kid who's never touched a guitar can feel like a rockstar. A content creator can generate unlimited original music without licensing headaches.

**We didn't build a gimmick. We built a pipeline.**

---

*Your body is the instrument. AI is the producer. The stage is wherever you're standing.*