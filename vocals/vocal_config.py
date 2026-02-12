"""
Configuration dataclasses for the vocals module.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, List, Any


@dataclass
class VocalConfig:
    """Configuration for ElevenLabs Voice Changer API."""

    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # Default ElevenLabs voice (George)
    model_id: str = "eleven_multilingual_sts_v2"
    output_format: str = "pcm_22050"  # PCM/WAV format (lower sample rate, available on all tiers)
    remove_background_noise: bool = True

    # Voice settings (optional JSON-encoded string)
    voice_settings: Optional[str] = None

    # Seed for deterministic output (optional)
    seed: Optional[int] = None


@dataclass
class RecordingConfig:
    """Configuration for microphone recording."""

    sample_rate: int = 44100
    channels: int = 1  # Mono for voice
    chunk_size: int = 1024

    # Audio format
    dtype: str = "float32"  # sounddevice dtype

    # Output format
    output_format: str = "wav"


@dataclass
class TTSConfig:
    """Configuration for ElevenLabs Text-to-Speech API."""

    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"
    sample_rate: int = 44100

    # Voice settings for TTS generation
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


# Available voice options (voice_id -> (name, description))
AVAILABLE_VOICES: Dict[str, Tuple[str, str]] = {
    "xO2Q4ARMEd4BI2sGDH9c": ("Voice 1", "Deep male voice"),
    "JJQDkHrp6uKU5Vk0WKhY": ("Voice 2", "Smooth male voice"),
    "Nggzl2QAXh3OijoXD116": ("Voice 3", "Energetic voice"),
    "mtrellq69YZsNwzUSyXh": ("Voice 4", "Warm voice"),
    "LRpNiUBlcqgIsKUzcrlN": ("Voice 5", "Clear voice"),
    "CKfuQaJKfvUG2Wtrda3Y": ("Voice 6", "Rich voice"),
    "SgG3x729SgH346SJc0ck": ("Voice 7", "Soft voice"),
    "pZv6Kbgq62dtlvkJTupr": ("Voice 8", "Bright voice"),
    "lP1EpPqqTU5DCn2ga6OD": ("Voice 9", "Dynamic voice"),
    "ui0NMIinCTg8KvB4ogeV": ("Voice 10", "Expressive voice"),
}

# Extended voice metadata for AI voice selection
AVAILABLE_VOICES_EXTENDED: Dict[str, Dict[str, Any]] = {
    "xO2Q4ARMEd4BI2sGDH9c": {
        "name": "Voice 1",
        "description": "Deep male voice",
        "moods": ["powerful", "dramatic", "authoritative"],
        "energy_match": ["high", "medium"],
        "genre_fit": ["rock", "cinematic", "epic"],
    },
    "JJQDkHrp6uKU5Vk0WKhY": {
        "name": "Voice 2",
        "description": "Smooth male voice",
        "moods": ["calm", "intimate", "warm"],
        "energy_match": ["low", "medium"],
        "genre_fit": ["jazz", "r&b", "acoustic"],
    },
    "Nggzl2QAXh3OijoXD116": {
        "name": "Voice 3",
        "description": "Energetic voice",
        "moods": ["upbeat", "excited", "joyful"],
        "energy_match": ["high"],
        "genre_fit": ["pop", "dance", "electronic"],
    },
    "mtrellq69YZsNwzUSyXh": {
        "name": "Voice 4",
        "description": "Warm voice",
        "moods": ["comforting", "nostalgic", "gentle"],
        "energy_match": ["low", "medium"],
        "genre_fit": ["folk", "country", "ballad"],
    },
    "LRpNiUBlcqgIsKUzcrlN": {
        "name": "Voice 5",
        "description": "Clear voice",
        "moods": ["neutral", "articulate", "professional"],
        "energy_match": ["medium"],
        "genre_fit": ["pop", "indie", "alternative"],
    },
    "CKfuQaJKfvUG2Wtrda3Y": {
        "name": "Voice 6",
        "description": "Rich voice",
        "moods": ["soulful", "passionate", "emotional"],
        "energy_match": ["medium", "high"],
        "genre_fit": ["soul", "gospel", "r&b"],
    },
    "SgG3x729SgH346SJc0ck": {
        "name": "Voice 7",
        "description": "Soft voice",
        "moods": ["dreamy", "ethereal", "melancholic"],
        "energy_match": ["low"],
        "genre_fit": ["ambient", "chill", "acoustic"],
    },
    "pZv6Kbgq62dtlvkJTupr": {
        "name": "Voice 8",
        "description": "Bright voice",
        "moods": ["cheerful", "optimistic", "playful"],
        "energy_match": ["medium", "high"],
        "genre_fit": ["pop", "indie", "folk"],
    },
    "lP1EpPqqTU5DCn2ga6OD": {
        "name": "Voice 9",
        "description": "Dynamic voice",
        "moods": ["versatile", "expressive", "dramatic"],
        "energy_match": ["low", "medium", "high"],
        "genre_fit": ["musical", "theatrical", "pop"],
    },
    "ui0NMIinCTg8KvB4ogeV": {
        "name": "Voice 10",
        "description": "Expressive voice",
        "moods": ["emotional", "intense", "heartfelt"],
        "energy_match": ["medium", "high"],
        "genre_fit": ["ballad", "pop", "indie"],
    },
}

# Ordered list for menu display
VOICE_OPTIONS = list(AVAILABLE_VOICES.keys())


def display_voice_options() -> None:
    """Display available voice options to the user."""
    print("\n" + "=" * 50)
    print("        AVAILABLE VOICE OPTIONS")
    print("=" * 50)
    for i, voice_id in enumerate(VOICE_OPTIONS, 1):
        name, description = AVAILABLE_VOICES[voice_id]
        print(f"  [{i:2d}] {name}: {description}")
    print("=" * 50)


def select_voice() -> VocalConfig:
    """
    Prompt user to select a voice option.

    Returns:
        VocalConfig with the selected voice_id
    """
    display_voice_options()

    while True:
        try:
            choice = input("\nSelect voice (1-10): ").strip()
            index = int(choice) - 1

            if 0 <= index < len(VOICE_OPTIONS):
                voice_id = VOICE_OPTIONS[index]
                name, description = AVAILABLE_VOICES[voice_id]
                print(f"\n> Selected: {name} ({description})")
                return VocalConfig(voice_id=voice_id)
            else:
                print("Invalid selection. Please enter a number 1-10.")
        except ValueError:
            print("Invalid input. Please enter a number 1-10.")
        except KeyboardInterrupt:
            print("\n\nUsing default voice.")
            return VocalConfig(voice_id=VOICE_OPTIONS[0])


def get_voice_by_index(index: int) -> VocalConfig:
    """
    Get a voice config by index (1-10).

    Args:
        index: Voice number (1-10)

    Returns:
        VocalConfig with the selected voice_id
    """
    if 1 <= index <= len(VOICE_OPTIONS):
        return VocalConfig(voice_id=VOICE_OPTIONS[index - 1])
    raise ValueError(f"Invalid voice index: {index}. Must be 1-10.")


# Preset voice configurations (legacy support)
VOICE_PRESETS = {
    "george": VocalConfig(voice_id="JBFqnCBsd6RMkjVDRZzb"),
    "default": VocalConfig(voice_id=VOICE_OPTIONS[0]),
}


def get_voice_preset(name: str) -> VocalConfig:
    """Get a preset voice configuration by name."""
    return VOICE_PRESETS.get(name.lower(), VOICE_PRESETS["default"])
