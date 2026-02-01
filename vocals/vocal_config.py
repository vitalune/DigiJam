"""
Configuration dataclasses for the vocals module.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple


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
