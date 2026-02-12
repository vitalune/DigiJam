"""
DigiJam API Server - FastAPI backend for frontend integration.

Handles video upload, pose detection, event extraction, and audio rendering.
"""

import os
import sys
import json
import uuid
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from classifiers.drum_classifier import DrumClassifier
from classifiers.guitar_classifier import GuitarClassifier
from classifiers.piano_classifier import PianoClassifier
from audio.loader import load_drums_session, load_guitar_session, load_piano_session
from audio.quantizer import build_grid, snap_to_grid, get_grid_for_event
from audio.mixer import AudioMixer
from audio.music_theory import AVAILABLE_KEYS
import cv2

app = FastAPI(title="DigiJam API", version="1.0.0")

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


class PlayerConfig(BaseModel):
    instrument: str
    hand: str


class SessionConfig(BaseModel):
    playerCount: int
    players: List[PlayerConfig]
    bpm: int
    keyNote: str
    keyMode: str
    aiSupportLevel: str = "low"  # "low" | "medium" | "high"
    includeVocals: bool = False


class ProcessingResult(BaseModel):
    status: str
    audioUrl: str
    videoUrl: str
    duration: float


def convert_webm_to_mp4(webm_path: str, mp4_path: str) -> bool:
    """Convert WebM to MP4 using ffmpeg."""
    try:
        result = subprocess.run([
            'ffmpeg', '-y', '-i', webm_path,
            '-c:v', 'libx264', '-preset', 'fast',
            '-crf', '22', mp4_path
        ], capture_output=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        print(f"FFmpeg conversion error: {e}")
        return False


def process_video_for_instrument(
    video_path: str,
    instrument: str,
    dominant_hand: str,
    key: str,
    output_dir: Path,
    session_id: str
) -> tuple[Optional[str], float]:
    """
    Process video to extract instrument events.

    Returns:
        Tuple of (json_path, end_time) or (None, 0) on failure
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return None, 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0

    # Initialize classifier
    if instrument == 'drums':
        classifier = DrumClassifier(dominant_hand=dominant_hand)
    elif instrument == 'guitar':
        classifier = GuitarClassifier(dominant_hand=dominant_hand, key=key)
    elif instrument == 'piano':
        classifier = PianoClassifier(dominant_hand=dominant_hand, key=key)
    else:
        print(f"Unknown instrument: {instrument}")
        return None, 0

    # Event storage
    events = []
    start_time = datetime.now().timestamp()

    # Callback to collect events
    def on_event(event):
        event_dict = {
            'timestamp': (datetime.now().timestamp() - start_time),
            'raw_timestamp': datetime.now().timestamp()
        }

        if instrument == 'drums':
            event_dict.update({
                'action': event.action,
                'velocity': event.velocity,
                'hand': event.hand
            })
        elif instrument == 'guitar':
            event_dict.update({
                'action': 'strum',
                'zone': event.zone,
                'intensity': event.intensity
            })
        elif instrument == 'piano':
            event_dict.update({
                'action': event.action,
                'chord': event.zone,
                'octave': event.octave,
                'intensity': event.intensity,
                'hand': event.hand
            })

        events.append(event_dict)

    # Set callback
    if instrument == 'drums':
        classifier.on_hit_callback = on_event
    elif instrument == 'guitar':
        classifier.on_strum_callback = on_event
    elif instrument == 'piano':
        classifier.on_piano_hit_callback = on_event

    # Process frames
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Process frame
        try:
            classifier.process_frame(frame)
        except Exception as e:
            print(f"Frame processing error: {e}")

        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx}/{frame_count} frames")

    cap.release()

    # Save events to JSON
    json_path = output_dir / f"{instrument}_session_{session_id}.json"

    if instrument == 'drums':
        session_data = {
            'hits': events,
            'end_time': duration
        }
    elif instrument == 'guitar':
        session_data = {
            'strums': events,
            'key': key,
            'end_time': duration
        }
    elif instrument == 'piano':
        session_data = {
            'hits': events,
            'key': key,
            'end_time': duration
        }

    with open(json_path, 'w') as f:
        json.dump(session_data, f, indent=2)

    print(f"Saved {len(events)} {instrument} events to {json_path}")
    return str(json_path), duration


def render_audio(
    drums_json: Optional[str],
    guitar_json: Optional[str],
    piano_json: Optional[str],
    bpm: float,
    key: str,
    output_path: str,
    soundpack_dir: str = "soundpack"
) -> float:
    """
    Render audio from event JSONs.

    Returns:
        Duration of rendered audio
    """
    from audio.loader import AudioEvent

    all_events: List[AudioEvent] = []
    max_end_time = 0.0

    # Load events from each instrument
    if drums_json and Path(drums_json).exists():
        events, end_time = load_drums_session(drums_json)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} drum events")

    if guitar_json and Path(guitar_json).exists():
        events, end_time = load_guitar_session(guitar_json, key=key)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} guitar events")

    if piano_json and Path(piano_json).exists():
        events, end_time = load_piano_session(piano_json, key=key)
        all_events.extend(events)
        max_end_time = max(max_end_time, end_time)
        print(f"Loaded {len(events)} piano events")

    if not all_events:
        # Create a short silence if no events
        print("No events found, creating minimal audio")
        max_end_time = 1.0

    # Build quantization grids
    grids = {
        '16th': build_grid(bpm, max_end_time, '16th'),
        'quarter': build_grid(bpm, max_end_time, 'quarter'),
        'half': build_grid(bpm, max_end_time, 'half'),
    }

    # Quantize events
    for event in all_events:
        grid_type = get_grid_for_event(event.instrument, event.action)
        event.quantized_time = snap_to_grid(event.timestamp, grids[grid_type])

    # Sort by quantized time
    all_events.sort(key=lambda e: e.quantized_time)

    # Initialize mixer and render
    mixer = AudioMixer(soundpack_dir, sample_rate=44100)
    mixer.load_samples()

    audio = mixer.render(all_events, max_end_time)
    audio = mixer.normalize(audio, headroom_db=-1.0)

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Export
    mixer.export_wav(audio, output_path)

    return len(audio) / 44100


@app.post("/api/generate-music", response_model=ProcessingResult)
async def generate_music(
    video: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Process uploaded video and generate music.

    Accepts:
        - video: WebM video file from browser recording
        - config: JSON string with session configuration

    Returns:
        - audioUrl: URL to download generated audio
        - duration: Audio duration in seconds
    """
    try:
        # Parse config
        session_config = SessionConfig.model_validate_json(config)
        session_id = str(uuid.uuid4())[:8]

        print(f"\n{'='*50}")
        print(f"Processing session: {session_id}")
        print(f"Players: {session_config.playerCount}")
        print(f"BPM: {session_config.bpm}")
        print(f"Key: {session_config.keyNote} {session_config.keyMode}")
        print(f"{'='*50}\n")

        # Save uploaded video
        webm_path = OUTPUT_DIR / f"upload_{session_id}.webm"
        mp4_path = OUTPUT_DIR / f"upload_{session_id}.mp4"

        with open(webm_path, "wb") as f:
            content = await video.read()
            f.write(content)

        print(f"Saved video: {webm_path} ({len(content)} bytes)")

        # Convert WebM to MP4
        print("Converting WebM to MP4...")
        if not convert_webm_to_mp4(str(webm_path), str(mp4_path)):
            # Try using the WebM directly
            print("Conversion failed, trying WebM directly...")
            mp4_path = webm_path

        # Build key string
        key = f"{session_config.keyNote} {session_config.keyMode}"
        if key not in AVAILABLE_KEYS:
            key = "E Minor"  # Fallback

        # Process video for each instrument
        json_paths = {'drums': None, 'guitar': None, 'piano': None}
        max_duration = 0.0

        for player in session_config.players:
            if player.instrument and player.instrument != 'vocals':
                print(f"\nProcessing {player.instrument} (hand: {player.hand})...")
                json_path, duration = process_video_for_instrument(
                    str(mp4_path),
                    player.instrument,
                    player.hand,
                    key,
                    OUTPUT_DIR,
                    session_id
                )
                if json_path:
                    json_paths[player.instrument] = json_path
                    max_duration = max(max_duration, duration)

        # Render audio
        print("\nRendering audio...")
        audio_filename = f"mixed_{session_id}.wav"
        audio_path = OUTPUT_DIR / audio_filename

        soundpack_dir = Path(__file__).parent.parent / "soundpack"
        duration = render_audio(
            json_paths['drums'],
            json_paths['guitar'],
            json_paths['piano'],
            session_config.bpm,
            key,
            str(audio_path),
            str(soundpack_dir)
        )

        print(f"\nAudio rendered: {audio_path} ({duration:.2f}s)")

        # Move video to videos directory for serving
        videos_dir = OUTPUT_DIR / "videos"
        videos_dir.mkdir(exist_ok=True)
        video_filename = f"recording_{session_id}.mp4"
        final_video_path = videos_dir / video_filename

        try:
            if mp4_path.exists():
                import shutil
                shutil.move(str(mp4_path), str(final_video_path))
                print(f"Video saved: {final_video_path}")
        except Exception as e:
            print(f"Video move warning: {e}")

        # Cleanup temp files
        try:
            if webm_path.exists():
                webm_path.unlink()
        except Exception as e:
            print(f"Cleanup warning: {e}")

        return ProcessingResult(
            status="completed",
            audioUrl=f"/api/files/audio/{audio_filename}",
            videoUrl=f"/api/files/video/{video_filename}",
            duration=duration
        )

    except Exception as e:
        print(f"Processing error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio files."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        media_type="audio/wav",
        filename=filename
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


# ============================================================================
# VOCALS PROCESSING ENDPOINTS
# ============================================================================

class VocalConfig(BaseModel):
    voiceId: str
    enableAutotune: bool
    retuneSpeed: int
    keyNote: str
    keyMode: str


class VocalResult(BaseModel):
    status: str
    transformedVocalsUrl: str


class MixConfig(BaseModel):
    transformedVocalsUrl: str
    instrumentalUrl: str
    vocalVolume: float
    instrumentalVolume: float


class MixResult(BaseModel):
    status: str
    audioUrl: str


def convert_webm_to_wav(webm_path: str, wav_path: str) -> bool:
    """Convert WebM audio to WAV using ffmpeg."""
    try:
        result = subprocess.run([
            'ffmpeg', '-y', '-i', webm_path,
            '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1',
            wav_path
        ], capture_output=True, timeout=60)
        return result.returncode == 0
    except Exception as e:
        print(f"FFmpeg audio conversion error: {e}")
        return False


@app.post("/api/process-vocals", response_model=VocalResult)
async def process_vocals(
    audio: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Process uploaded vocals with ElevenLabs voice transformation.

    Accepts:
        - audio: WebM audio file from browser recording
        - config: JSON string with vocal configuration

    Returns:
        - transformedVocalsUrl: URL to transformed vocals
    """
    try:
        from vocals.vocal_processor import VocalProcessor
        from vocals.vocal_config import VocalConfig as VConfig
        from vocals.autotune import autotune_audio, AutotuneConfig

        # Parse config
        vocal_config = VocalConfig.model_validate_json(config)
        session_id = str(uuid.uuid4())[:8]

        print(f"\n{'='*50}")
        print(f"Processing vocals: {session_id}")
        print(f"Voice ID: {vocal_config.voiceId}")
        print(f"Autotune: {vocal_config.enableAutotune} (speed: {vocal_config.retuneSpeed})")
        print(f"Key: {vocal_config.keyNote} {vocal_config.keyMode}")
        print(f"{'='*50}\n")

        # Save uploaded audio
        vocals_dir = OUTPUT_DIR / "vocals"
        vocals_dir.mkdir(exist_ok=True)

        webm_path = vocals_dir / f"raw_{session_id}.webm"
        wav_path = vocals_dir / f"raw_{session_id}.wav"

        with open(webm_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        print(f"Saved raw audio: {webm_path} ({len(content)} bytes)")

        # Convert to WAV
        print("Converting to WAV...")
        if not convert_webm_to_wav(str(webm_path), str(wav_path)):
            raise HTTPException(status_code=500, detail="Audio conversion failed")

        # Apply autotune if enabled
        processed_wav = wav_path
        if vocal_config.enableAutotune:
            print("Applying autotune...")
            key_str = f"{vocal_config.keyNote}:{vocal_config.keyMode.lower()[:3]}"
            autotune_config = AutotuneConfig(
                key=key_str,
                retune_speed=vocal_config.retuneSpeed
            )
            autotuned_path = vocals_dir / f"autotuned_{session_id}.wav"
            autotune_audio(str(wav_path), str(autotuned_path), autotune_config)
            processed_wav = autotuned_path
            print(f"Autotuned audio saved: {autotuned_path}")

        # Transform voice with ElevenLabs
        print("Transforming voice with ElevenLabs...")
        processor = VocalProcessor()
        vconfig = VConfig(voice_id=vocal_config.voiceId)

        transformed_path = vocals_dir / f"transformed_{session_id}.wav"
        transformed_audio = processor.transform_voice(str(processed_wav), vconfig)

        # Save transformed audio
        with open(transformed_path, 'wb') as f:
            f.write(transformed_audio)

        print(f"Transformed vocals saved: {transformed_path}")

        # Cleanup
        try:
            webm_path.unlink()
        except:
            pass

        return VocalResult(
            status="completed",
            transformedVocalsUrl=f"/api/files/vocals/transformed_{session_id}.wav"
        )

    except Exception as e:
        print(f"Vocal processing error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mix-audio", response_model=MixResult)
async def mix_audio(config: str = Form(...)):
    """
    Mix vocals with instrumental track.

    Accepts:
        - config: JSON string with mixing configuration

    Returns:
        - audioUrl: URL to final mixed audio
    """
    try:
        from vocals.vocal_mixer import VocalMixer

        # Parse config
        mix_config = MixConfig.model_validate_json(config)
        session_id = str(uuid.uuid4())[:8]

        print(f"\n{'='*50}")
        print(f"Mixing audio: {session_id}")
        print(f"Vocal volume: {mix_config.vocalVolume}")
        print(f"Instrumental volume: {mix_config.instrumentalVolume}")
        print(f"{'='*50}\n")

        # Get file paths from URLs
        vocals_filename = mix_config.transformedVocalsUrl.split('/')[-1]
        instrumental_filename = mix_config.instrumentalUrl.split('/')[-1]

        vocals_path = OUTPUT_DIR / "vocals" / vocals_filename
        instrumental_path = OUTPUT_DIR / instrumental_filename

        if not vocals_path.exists():
            raise HTTPException(status_code=404, detail="Vocals file not found")
        if not instrumental_path.exists():
            raise HTTPException(status_code=404, detail="Instrumental file not found")

        # Mix audio
        mixer = VocalMixer()
        mixed_path = OUTPUT_DIR / f"final_mix_{session_id}.wav"

        mixed_audio = mixer.mix_files(
            str(instrumental_path),
            str(vocals_path),
            vocal_volume=mix_config.vocalVolume,
            instrumental_volume=mix_config.instrumentalVolume
        )

        # Normalize and export
        mixed_audio = mixer.normalize(mixed_audio)
        mixer.export(mixed_audio, str(mixed_path))

        print(f"Mixed audio saved: {mixed_path}")

        return MixResult(
            status="completed",
            audioUrl=f"/api/files/audio/final_mix_{session_id}.wav"
        )

    except Exception as e:
        print(f"Audio mixing error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/vocals/{filename}")
async def get_vocals_file(filename: str):
    """Serve processed vocal files."""
    file_path = OUTPUT_DIR / "vocals" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        media_type="audio/wav",
        filename=filename
    )


# ============================================================================
# VIDEO GENERATION ENDPOINT
# ============================================================================

class VideoConfig(BaseModel):
    audioUrl: Optional[str] = None
    bpm: int
    keyNote: str
    keyMode: str
    instruments: List[str]


class VideoResult(BaseModel):
    status: str
    videoUrl: Optional[str] = None


@app.post("/api/generate-video", response_model=VideoResult)
async def generate_video(
    video: Optional[UploadFile] = File(None),
    config: str = Form(...)
):
    """
    Generate AI music video using Google Veo 3.1.

    Accepts:
        - video: Optional performance video for reference
        - config: JSON string with video configuration

    Returns:
        - videoUrl: URL to generated video (or None if generation fails)
    """
    try:
        from generate_video import generate_music_video

        # Parse config
        video_config = VideoConfig.model_validate_json(config)
        session_id = str(uuid.uuid4())[:8]

        print(f"\n{'='*50}")
        print(f"Generating video: {session_id}")
        print(f"Instruments: {video_config.instruments}")
        print(f"{'='*50}\n")

        # Get audio path
        audio_path = None
        if video_config.audioUrl:
            audio_filename = video_config.audioUrl.split('/')[-1]
            audio_path = OUTPUT_DIR / audio_filename
            if not audio_path.exists():
                audio_path = OUTPUT_DIR / "vocals" / audio_filename

        # Save reference video if provided
        reference_path = None
        if video:
            reference_path = OUTPUT_DIR / f"reference_{session_id}.webm"
            with open(reference_path, "wb") as f:
                content = await video.read()
                f.write(content)

        # Generate video
        videos_dir = OUTPUT_DIR / "videos"
        videos_dir.mkdir(exist_ok=True)

        output_path = videos_dir / f"music_video_{session_id}.mp4"

        # Call the video generation function
        success = generate_music_video(
            audio_path=str(audio_path) if audio_path else None,
            output_path=str(output_path),
            instruments=video_config.instruments,
            key=f"{video_config.keyNote} {video_config.keyMode}",
            bpm=video_config.bpm
        )

        if success and output_path.exists():
            return VideoResult(
                status="completed",
                videoUrl=f"/api/files/video/music_video_{session_id}.mp4"
            )
        else:
            return VideoResult(
                status="failed",
                videoUrl=None
            )

    except Exception as e:
        print(f"Video generation error: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the request - video is optional
        return VideoResult(
            status="failed",
            videoUrl=None
        )


@app.get("/api/files/video/{filename}")
async def get_video_file(filename: str):
    """Serve generated video files."""
    file_path = OUTPUT_DIR / "videos" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename
    )


# ============================================================================
# AI SUPPORT LEVEL ENDPOINTS
# ============================================================================

class AIProcessingConfig(BaseModel):
    """Configuration for AI processing endpoint."""
    aiSupportLevel: str = "low"  # "low" | "medium" | "high"
    instrumentalUrl: str
    keyNote: str
    keyMode: str
    bpm: int
    genre: str = "pop"
    # Low AI mode - manual voice selection
    voiceId: Optional[str] = None


class AIProcessingResult(BaseModel):
    """Result from AI processing endpoint."""
    status: str
    mode: str
    audioUrl: str
    # Medium mode additional info
    userSections: Optional[List[dict]] = None
    # High mode additional info
    sections: Optional[List[dict]] = None


class UserVocalsConfig(BaseModel):
    """Configuration for adding user vocals (medium mode phase 2)."""
    masterTrackUrl: str
    userVocalsUrl: str
    voiceId: Optional[str] = None  # For voice transformation


@app.post("/api/process-with-ai", response_model=AIProcessingResult)
async def process_with_ai(config: AIProcessingConfig):
    """
    Main AI processing endpoint that routes based on aiSupportLevel.

    - Low: Generates supplemental melody, user sings manually
    - Medium: Generates AI vocals with gaps, returns master for user recording
    - High: Generates complete AI vocals, no user recording needed
    """
    try:
        session_id = str(uuid.uuid4())[:8]
        key = f"{config.keyNote} {config.keyMode}"

        if config.aiSupportLevel == "low":
            return await process_low_ai_mode(config, session_id, key)
        elif config.aiSupportLevel == "medium":
            return await process_medium_ai_mode(config, session_id, key)
        else:  # high
            return await process_high_ai_mode(config, session_id, key)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_low_ai_mode(config: AIProcessingConfig, session_id: str, key: str) -> AIProcessingResult:
    """
    Low AI mode: Generate supplemental melody at low volume.
    User will record vocals manually.
    """
    from compose_music import MusicComposer, MelodyMixer, CompositionConfig, AI_VOLUME_PRESETS

    # Download instrumental
    # For now, assume instrumentalUrl is a local file path or we need to download it
    instrumental_path = config.instrumentalUrl

    # Generate melody
    composer = MusicComposer()
    prompt = f"Instrumental melody at {config.bpm} BPM in {key}, {config.genre} style, subtle background accompaniment"

    comp_config = CompositionConfig(
        output_format="mp3_44100_128",
        force_instrumental=True,
    )

    melody_bytes = composer.compose_from_prompt(prompt, comp_config)

    # Mix with low AI volumes
    mixer = MelodyMixer()
    instrumental_audio = mixer.load_wav(Path(instrumental_path))
    melody_audio = mixer.load_audio_bytes(melody_bytes, format_hint="mp3_44100_128", pcm_sample_rate=44100, pcm_channels=2)

    volumes = AI_VOLUME_PRESETS["low"]
    mixed_audio = mixer.mix(
        original=instrumental_audio,
        melody=melody_audio,
        melody_volume=volumes["melody"],
        original_volume=volumes["instrumental"]
    )
    mixed_audio = mixer.normalize(mixed_audio)

    # Save output
    output_filename = f"low_ai_{session_id}.wav"
    output_path = OUTPUT_DIR / "music" / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixer.export(mixed_audio, output_path)

    return AIProcessingResult(
        status="success",
        mode="low",
        audioUrl=f"/api/files/audio/{output_filename}",
    )


async def process_medium_ai_mode(config: AIProcessingConfig, session_id: str, key: str) -> AIProcessingResult:
    """
    Medium AI mode: Generate AI vocals with gaps for user participation.
    Returns master track - user records vocals in phase 2.
    """
    from vocals.medium_ai_pipeline import MediumAIPipeline, MediumAIPipelineConfig

    instrumental_path = config.instrumentalUrl

    # Run phase 1
    pipeline = MediumAIPipeline()
    pipeline_config = MediumAIPipelineConfig(genre=config.genre)

    output_filename = f"medium_ai_master_{session_id}.wav"
    output_path = OUTPUT_DIR / "music" / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = pipeline.phase1_generate_master_with_gaps(
        instrumental_path=instrumental_path,
        output_path=str(output_path),
        config=pipeline_config,
        verbose=False
    )

    return AIProcessingResult(
        status="success",
        mode="medium",
        audioUrl=f"/api/files/audio/{output_filename}",
        userSections=results.get("user_sections", []),
    )


async def process_high_ai_mode(config: AIProcessingConfig, session_id: str, key: str) -> AIProcessingResult:
    """
    High AI mode: Generate complete AI vocals.
    No user recording needed.
    """
    from vocals.high_ai_pipeline import HighAIPipeline, HighAIPipelineConfig

    instrumental_path = config.instrumentalUrl

    # Run full pipeline
    pipeline = HighAIPipeline()
    pipeline_config = HighAIPipelineConfig(genre=config.genre)

    output_filename = f"high_ai_{session_id}.wav"
    output_path = OUTPUT_DIR / "music" / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = pipeline.process(
        instrumental_path=instrumental_path,
        output_path=str(output_path),
        config=pipeline_config,
        verbose=False
    )

    return AIProcessingResult(
        status="success",
        mode="high",
        audioUrl=f"/api/files/audio/{output_filename}",
        sections=results.get("sections", []),
    )


@app.post("/api/add-user-vocals", response_model=AIProcessingResult)
async def add_user_vocals(config: UserVocalsConfig):
    """
    Medium AI mode phase 2: Add user-recorded vocals to master track.
    """
    try:
        from vocals.medium_ai_pipeline import MediumAIPipeline, MediumAIPipelineConfig
        from vocals.vocal_config import VocalConfig

        session_id = str(uuid.uuid4())[:8]

        pipeline = MediumAIPipeline()
        pipeline_config = MediumAIPipelineConfig()

        # Set voice transformation if requested
        if config.voiceId:
            pipeline_config.transform_user_vocals = True
            pipeline_config.user_voice_config = VocalConfig(voice_id=config.voiceId)

        output_filename = f"medium_ai_final_{session_id}.wav"
        output_path = OUTPUT_DIR / "music" / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = pipeline.phase2_add_user_vocals(
            master_track_path=config.masterTrackUrl,
            user_vocals_path=config.userVocalsUrl,
            output_path=str(output_path),
            config=pipeline_config,
            verbose=False
        )

        return AIProcessingResult(
            status="success",
            mode="medium",
            audioUrl=f"/api/files/audio/{output_filename}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NEW PIPELINE ENDPOINTS (with video generation)
# ============================================================================

class PipelineResponse(BaseModel):
    """Response from pipeline endpoints."""
    status: str
    videoUrl: str
    audioUrl: str
    duration: float
    sections: Optional[List[dict]] = None


class HighPipelineConfig(BaseModel):
    """Configuration for high AI pipeline."""
    sessionId: str
    instrumentalUrl: str
    bpm: float = 120
    key: str = "C Major"
    genre: str = "pop"
    lyricsPrompt: Optional[str] = None
    voiceId: Optional[str] = None


class MediumPipelineConfig(BaseModel):
    """Configuration for medium AI pipeline."""
    sessionId: str
    instrumentalUrl: str
    bpm: float = 120
    key: str = "C Major"
    genre: str = "pop"
    lyricsPrompt: Optional[str] = None
    voiceId: str


class LowPipelineConfig(BaseModel):
    """Configuration for low AI pipeline."""
    sessionId: str
    instrumentalUrl: str
    bpm: float = 120
    key: str = "C Major"
    voiceId: str


def get_file_from_url(url: str) -> Path:
    """Convert API URL to local file path."""
    # Handle different URL patterns
    if url.startswith("/api/files/audio/"):
        filename = url.split("/api/files/audio/")[-1]
        return OUTPUT_DIR / filename
    elif url.startswith("/api/files/video/"):
        filename = url.split("/api/files/video/")[-1]
        return OUTPUT_DIR / "videos" / filename
    elif url.startswith("/api/files/vocals/"):
        filename = url.split("/api/files/vocals/")[-1]
        return OUTPUT_DIR / "vocals" / filename
    else:
        # Assume it's already a path
        return Path(url)


@app.post("/api/pipeline/high", response_model=PipelineResponse)
async def pipeline_high(
    session_id: str = Form(...),
    instrumental_url: str = Form(...),
    bpm: float = Form(120),
    key: str = Form("C Major"),
    genre: str = Form("pop"),
    lyrics_prompt: Optional[str] = Form(None),
    voice_id: Optional[str] = Form(None),
):
    """
    Full AI automation pipeline with video generation.

    1. Generate melody → mix with instrumental (high AI volumes)
    2. Generate song structure and complete lyrics
    3. Select voices automatically (or use provided voice_id)
    4. Synthesize all vocals via TTS
    5. Mix final audio with ducking
    6. Generate music video (loop short videos)

    No user vocals required.
    """
    try:
        from pipelines.high_pipeline import HighPipeline, HighPipelineConfig as HPConfig

        print(f"\n{'='*50}")
        print(f"HIGH AI PIPELINE: {session_id}")
        print(f"BPM: {bpm}, Key: {key}, Genre: {genre}")
        if lyrics_prompt:
            print(f"Lyrics prompt: {lyrics_prompt[:50]}...")
        print(f"{'='*50}\n")

        # Get instrumental file path
        instrumental_path = get_file_from_url(instrumental_url)
        if not instrumental_path.exists():
            raise HTTPException(status_code=404, detail=f"Instrumental file not found: {instrumental_url}")

        # Create pipeline and config
        pipeline = HighPipeline(output_dir=OUTPUT_DIR)
        config = HPConfig(
            genre=genre,
            lyrics_prompt=lyrics_prompt or "",
            voice_id=voice_id,
        )

        # Run pipeline
        result = pipeline.process(
            session_id=session_id,
            instrumental_path=str(instrumental_path),
            bpm=bpm,
            key=key,
            config=config,
            verbose=True
        )

        return PipelineResponse(
            status="completed",
            videoUrl=f"/api/files/video/{result.video_path.name}",
            audioUrl=f"/api/files/audio/{result.audio_path.name}",
            duration=result.duration,
            sections=result.sections,
        )

    except Exception as e:
        print(f"High pipeline error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/medium", response_model=PipelineResponse)
async def pipeline_medium(
    session_id: str = Form(...),
    instrumental_url: str = Form(...),
    bpm: float = Form(120),
    key: str = Form("C Major"),
    genre: str = Form("pop"),
    lyrics_prompt: str = Form(...),
    voice_id: str = Form(...),
    user_vocals: UploadFile = File(...),
):
    """
    Collaborative mode pipeline with video generation.

    1. Generate melody → mix with instrumental (balanced volumes)
    2. Generate song structure with partial lyrics (AI + gaps)
    3. Synthesize AI vocals for non-gap sections
    4. Transform user vocals to selected voice
    5. Mix AI vocals + user vocals
    6. Generate music video

    User vocals required for gap sections.
    """
    try:
        from pipelines.medium_pipeline import MediumPipeline, MediumPipelineConfig as MPConfig

        print(f"\n{'='*50}")
        print(f"MEDIUM AI PIPELINE: {session_id}")
        print(f"BPM: {bpm}, Key: {key}, Genre: {genre}")
        print(f"Voice ID: {voice_id}")
        print(f"Lyrics prompt: {lyrics_prompt[:50]}...")
        print(f"{'='*50}\n")

        # Get instrumental file path
        instrumental_path = get_file_from_url(instrumental_url)
        if not instrumental_path.exists():
            raise HTTPException(status_code=404, detail=f"Instrumental file not found: {instrumental_url}")

        # Save user vocals
        vocals_dir = OUTPUT_DIR / "vocals"
        vocals_dir.mkdir(exist_ok=True)

        user_vocals_path = vocals_dir / f"user_vocals_{session_id}.webm"
        with open(user_vocals_path, "wb") as f:
            content = await user_vocals.read()
            f.write(content)

        # Convert to WAV
        user_vocals_wav = vocals_dir / f"user_vocals_{session_id}.wav"
        if not convert_webm_to_wav(str(user_vocals_path), str(user_vocals_wav)):
            raise HTTPException(status_code=500, detail="User vocals conversion failed")

        # Create pipeline and config
        pipeline = MediumPipeline(output_dir=OUTPUT_DIR)
        config = MPConfig(
            genre=genre,
            lyrics_prompt=lyrics_prompt,
            voice_id=voice_id,
        )

        # Run pipeline
        result = pipeline.process(
            session_id=session_id,
            instrumental_path=str(instrumental_path),
            user_vocals=str(user_vocals_wav),
            voice_id=voice_id,
            lyrics_prompt=lyrics_prompt,
            bpm=bpm,
            key=key,
            config=config,
            verbose=True
        )

        # Cleanup temp files
        try:
            user_vocals_path.unlink()
        except:
            pass

        return PipelineResponse(
            status="completed",
            videoUrl=f"/api/files/video/{result.video_path.name}",
            audioUrl=f"/api/files/audio/{result.audio_path.name}",
            duration=result.duration,
            sections=result.sections,
        )

    except Exception as e:
        print(f"Medium pipeline error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/low", response_model=PipelineResponse)
async def pipeline_low(
    session_id: str = Form(...),
    instrumental_url: str = Form(...),
    bpm: float = Form(120),
    key: str = Form("C Major"),
    voice_id: str = Form(...),
    user_vocals: UploadFile = File(...),
):
    """
    User-driven pipeline with AI voice transformation and video generation.

    1. Generate subtle background melody (low volume)
    2. Transform user vocals to selected voice style
    3. Mix transformed vocals + melody + instrumental
    4. Generate music video

    User vocals required - AI enhances with voice transformation.
    """
    try:
        from pipelines.low_pipeline import LowPipeline, LowPipelineConfig as LPConfig

        print(f"\n{'='*50}")
        print(f"LOW AI PIPELINE: {session_id}")
        print(f"BPM: {bpm}, Key: {key}")
        print(f"Voice ID: {voice_id}")
        print(f"{'='*50}\n")

        # Get instrumental file path
        instrumental_path = get_file_from_url(instrumental_url)
        if not instrumental_path.exists():
            raise HTTPException(status_code=404, detail=f"Instrumental file not found: {instrumental_url}")

        # Save user vocals
        vocals_dir = OUTPUT_DIR / "vocals"
        vocals_dir.mkdir(exist_ok=True)

        user_vocals_path = vocals_dir / f"user_vocals_{session_id}.webm"
        with open(user_vocals_path, "wb") as f:
            content = await user_vocals.read()
            f.write(content)

        # Convert to WAV
        user_vocals_wav = vocals_dir / f"user_vocals_{session_id}.wav"
        if not convert_webm_to_wav(str(user_vocals_path), str(user_vocals_wav)):
            raise HTTPException(status_code=500, detail="User vocals conversion failed")

        # Create pipeline and config
        pipeline = LowPipeline(output_dir=OUTPUT_DIR)
        config = LPConfig(voice_id=voice_id)

        # Run pipeline
        result = pipeline.process(
            session_id=session_id,
            instrumental_path=str(instrumental_path),
            user_vocals=str(user_vocals_wav),
            voice_id=voice_id,
            bpm=bpm,
            key=key,
            config=config,
            verbose=True
        )

        # Cleanup temp files
        try:
            user_vocals_path.unlink()
        except:
            pass

        return PipelineResponse(
            status="completed",
            videoUrl=f"/api/files/video/{result.video_path.name}",
            audioUrl=f"/api/files/audio/{result.audio_path.name}",
            duration=result.duration,
            sections=[],
        )

    except Exception as e:
        print(f"Low pipeline error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
