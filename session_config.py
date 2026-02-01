"""
Session configuration dataclasses for multi-player DigiJam sessions.

Defines the configuration structure for multi-player sessions including
player assignments, instruments, and session-wide settings.

Config files are stored as output/session_config_NNN.json with incrementing numbers.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum


# Output directory for session configs
OUTPUT_DIR = Path("output")


class Instrument(str, Enum):
    """Available instruments."""
    DRUMS = "drums"
    GUITAR = "guitar"
    PIANO = "piano"


class Handedness(str, Enum):
    """Player handedness options."""
    RIGHT = "right"
    LEFT = "left"


@dataclass
class PlayerConfig:
    """
    Configuration for a single player in the session.

    Attributes:
        player_id: Unique identifier assigned during role assignment
        instrument: The instrument this player is assigned to
        position_index: Spatial position (0=left, 1=center, 2=right)
        dominant_hand: Player's dominant hand for instrument-specific logic
        key: Musical key for melodic instruments (guitar/piano)
    """
    player_id: int
    instrument: str
    position_index: int
    dominant_hand: str = "right"
    key: str = "C Major"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "player_id": self.player_id,
            "instrument": self.instrument,
            "position_index": self.position_index,
            "dominant_hand": self.dominant_hand,
            "key": self.key
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerConfig':
        """Create from dictionary."""
        return cls(
            player_id=data["player_id"],
            instrument=data["instrument"],
            position_index=data["position_index"],
            dominant_hand=data.get("dominant_hand", "right"),
            key=data.get("key", "C Major")
        )


@dataclass
class SessionConfig:
    """
    Configuration for a multi-player session.

    Attributes:
        num_players: Number of players (1, 2, or 3)
        instruments: List of instruments selected for this session
        players: List of player configurations (populated after role assignment)
        guitar_handedness: Handedness of guitar player (affects role assignment)
        key: Shared musical key for all melodic instruments
        bpm: Tempo in beats per minute (for audio rendering)
    """
    num_players: int
    instruments: List[str]
    guitar_handedness: str = "right"
    key: str = "C Major"
    bpm: float = 120.0
    players: List[PlayerConfig] = field(default_factory=list)

    def __post_init__(self):
        """Validate configuration."""
        if not 1 <= self.num_players <= 3:
            raise ValueError(f"num_players must be 1-3, got {self.num_players}")

        if len(self.instruments) != self.num_players:
            raise ValueError(
                f"Number of instruments ({len(self.instruments)}) "
                f"must match num_players ({self.num_players})"
            )

        # Check for duplicate instruments
        if len(self.instruments) != len(set(self.instruments)):
            raise ValueError("Duplicate instruments not allowed")

        # Validate all instruments
        valid_instruments = {e.value for e in Instrument}
        for inst in self.instruments:
            if inst not in valid_instruments:
                raise ValueError(f"Invalid instrument: {inst}")

    def has_instrument(self, instrument: str) -> bool:
        """Check if an instrument is in this session."""
        return instrument in self.instruments

    def get_player_by_instrument(self, instrument: str) -> Optional[PlayerConfig]:
        """Get the player assigned to a specific instrument."""
        for player in self.players:
            if player.instrument == instrument:
                return player
        return None

    def get_player_by_id(self, player_id: int) -> Optional[PlayerConfig]:
        """Get player configuration by player ID."""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "num_players": self.num_players,
            "instruments": self.instruments,
            "guitar_handedness": self.guitar_handedness,
            "key": self.key,
            "bpm": self.bpm,
            "players": [p.to_dict() for p in self.players]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionConfig':
        """Create from dictionary."""
        config = cls(
            num_players=data["num_players"],
            instruments=data["instruments"],
            guitar_handedness=data.get("guitar_handedness", "right"),
            key=data.get("key", "C Major"),
            bpm=data.get("bpm", 120.0)
        )
        config.players = [
            PlayerConfig.from_dict(p) for p in data.get("players", [])
        ]
        return config

    def save(self, output_dir: Path = OUTPUT_DIR) -> Path:
        """
        Save config to a numbered file (session_config_NNN.json).

        Args:
            output_dir: Directory to save config files

        Returns:
            Path to the saved config file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find highest existing number
        config_pattern = re.compile(r"session_config_(\d+)\.json$")
        max_num = 0

        for f in output_dir.iterdir():
            match = config_pattern.match(f.name)
            if match:
                max_num = max(max_num, int(match.group(1)))

        # Create next numbered file
        next_num = max_num + 1
        filepath = output_dir / f"session_config_{next_num:03d}.json"

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath

    def save_as(self, filepath: Path) -> None:
        """
        Save config to a specific file path.

        Args:
            filepath: Exact path to save the config file
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> 'SessionConfig':
        """
        Load config from a file.

        Args:
            filepath: Path to config file

        Returns:
            SessionConfig instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_latest(cls, output_dir: Path = OUTPUT_DIR) -> Optional['SessionConfig']:
        """
        Load the most recent numbered config file.

        Args:
            output_dir: Directory containing config files

        Returns:
            SessionConfig or None if no config found
        """
        if not output_dir.exists():
            return None

        config_pattern = re.compile(r"session_config_(\d+)\.json$")
        numbered_configs = []

        for f in output_dir.iterdir():
            match = config_pattern.match(f.name)
            if match:
                numbered_configs.append((int(match.group(1)), f))

        if numbered_configs:
            numbered_configs.sort(key=lambda x: x[0], reverse=True)
            return cls.load(numbered_configs[0][1])

        # Fallback to unnumbered config
        fallback = output_dir / "session_config.json"
        if fallback.exists():
            return cls.load(fallback)

        return None


def create_single_player_config(
    instrument: str,
    dominant_hand: str = "right",
    key: str = "C Major"
) -> SessionConfig:
    """
    Create a session config for single-player mode.

    Single player has no spatial constraints and is assigned player_id=1.

    Args:
        instrument: The instrument to play
        dominant_hand: Player's dominant hand
        key: Musical key for melodic instruments

    Returns:
        SessionConfig configured for single player
    """
    config = SessionConfig(
        num_players=1,
        instruments=[instrument],
        guitar_handedness=dominant_hand if instrument == "guitar" else "right",
        key=key
    )

    # Pre-assign player with ID 1
    config.players = [
        PlayerConfig(
            player_id=1,
            instrument=instrument,
            position_index=0,
            dominant_hand=dominant_hand,
            key=key
        )
    ]

    return config
