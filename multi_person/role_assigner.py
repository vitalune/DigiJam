"""
Spatial role assignment for multi-player DigiJam sessions.

Assigns instruments to players based on their x-position in the camera frame.

Role Assignment Rules:
- 1 player: Free position, assigned to selected instrument
- 2 players: Left = Drums, Right = Piano or Guitar
- 3 players: Middle = Drums, Left/Right = Piano/Guitar based on handedness

Guitar Handedness Override:
- Right-handed guitarist: rightmost = Guitar, leftmost = Piano
- Left-handed guitarist: leftmost = Guitar, rightmost = Piano
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RoleAssignment:
    """Result of role assignment for a single player."""
    position_index: int  # 0=left, 1=center, 2=right (sorted by x)
    instrument: str
    x_center: float  # X coordinate used for sorting


class RoleAssigner:
    """
    Assigns instruments to players based on their spatial position.

    Players are sorted by x-coordinate (left to right in camera view)
    and assigned instruments based on the configured rules.

    Attributes:
        num_players: Expected number of players (1, 2, or 3)
        instruments: List of instruments for this session
        guitar_handedness: "right" or "left" for guitar player
    """

    def __init__(
        self,
        num_players: int,
        instruments: List[str],
        guitar_handedness: str = "right"
    ):
        """
        Initialize role assigner.

        Args:
            num_players: Expected number of players (1, 2, or 3)
            instruments: List of instruments selected for the session
            guitar_handedness: Handedness of guitar player ("right" or "left")

        Raises:
            ValueError: If configuration is invalid
        """
        if not 1 <= num_players <= 3:
            raise ValueError(f"num_players must be 1-3, got {num_players}")

        if len(instruments) != num_players:
            raise ValueError(
                f"Number of instruments ({len(instruments)}) "
                f"must match num_players ({num_players})"
            )

        self.num_players = num_players
        self.instruments = instruments
        self.guitar_handedness = guitar_handedness

        # Pre-compute role mapping based on rules
        self._role_map = self._compute_role_map()

    def _compute_role_map(self) -> Dict[int, str]:
        """
        Compute the position -> instrument mapping based on rules.

        Returns:
            Dict mapping position_index (0, 1, 2) to instrument name
        """
        if self.num_players == 1:
            # Single player gets the only instrument
            return {0: self.instruments[0]}

        elif self.num_players == 2:
            # 2 players: Left = Drums (if present), Right = melodic
            return self._compute_2_player_roles()

        else:  # 3 players
            # 3 players: Middle = Drums, sides based on guitar handedness
            return self._compute_3_player_roles()

    def _compute_2_player_roles(self) -> Dict[int, str]:
        """
        Compute roles for 2 players.

        Rules:
        - Position 0 (left): Drums (if in instruments)
        - Position 1 (right): Piano or Guitar

        If drums not in instruments, positions are:
        - Position 0 (left): Piano or Guitar based on handedness
        - Position 1 (right): The other melodic instrument
        """
        has_drums = "drums" in self.instruments

        if has_drums:
            # Left = Drums, Right = melodic
            melodic = [i for i in self.instruments if i != "drums"][0]
            return {0: "drums", 1: melodic}
        else:
            # Both are melodic instruments
            # Use guitar handedness to determine positions
            has_guitar = "guitar" in self.instruments
            has_piano = "piano" in self.instruments

            if has_guitar and has_piano:
                if self.guitar_handedness == "right":
                    # Right-handed guitar goes on right
                    return {0: "piano", 1: "guitar"}
                else:
                    # Left-handed guitar goes on left
                    return {0: "guitar", 1: "piano"}
            else:
                # Only one type of melodic (shouldn't happen with unique instruments)
                return {0: self.instruments[0], 1: self.instruments[1]}

    def _compute_3_player_roles(self) -> Dict[int, str]:
        """
        Compute roles for 3 players.

        Rules:
        - Position 1 (middle): Drums (always)
        - Position 0 (left) and Position 2 (right): Piano and Guitar

        Guitar Handedness Override:
        - Right-handed: Position 2 (right) = Guitar, Position 0 (left) = Piano
        - Left-handed: Position 0 (left) = Guitar, Position 2 (right) = Piano
        """
        if self.guitar_handedness == "right":
            # Right-handed guitarist on the right
            return {0: "piano", 1: "drums", 2: "guitar"}
        else:
            # Left-handed guitarist on the left
            return {0: "guitar", 1: "drums", 2: "piano"}

    def assign_roles(
        self,
        person_centroids: List[Tuple[float, float]]
    ) -> List[RoleAssignment]:
        """
        Assign instruments to detected people based on their x-positions.

        Args:
            person_centroids: List of (x, y) centroids for each detected person

        Returns:
            List of RoleAssignment objects sorted by position_index

        Raises:
            ValueError: If number of detected people doesn't match num_players
        """
        if len(person_centroids) != self.num_players:
            raise ValueError(
                f"Expected {self.num_players} people, "
                f"got {len(person_centroids)}"
            )

        # Sort by x-coordinate (left to right)
        indexed = [(i, x, y) for i, (x, y) in enumerate(person_centroids)]
        sorted_by_x = sorted(indexed, key=lambda t: t[1])

        assignments = []
        for position_index, (original_idx, x, y) in enumerate(sorted_by_x):
            instrument = self._role_map[position_index]
            assignments.append(RoleAssignment(
                position_index=position_index,
                instrument=instrument,
                x_center=x
            ))

        return assignments

    def get_role_for_position(self, position_index: int) -> Optional[str]:
        """
        Get the instrument assigned to a specific position.

        Args:
            position_index: Position index (0=left, 1=center, 2=right)

        Returns:
            Instrument name or None if position is invalid
        """
        return self._role_map.get(position_index)

    def get_position_for_instrument(self, instrument: str) -> Optional[int]:
        """
        Get the position index for a specific instrument.

        Args:
            instrument: Instrument name

        Returns:
            Position index or None if instrument not in session
        """
        for pos, inst in self._role_map.items():
            if inst == instrument:
                return pos
        return None

    def describe_roles(self) -> str:
        """
        Get a human-readable description of role assignments.

        Returns:
            String describing positions and their instruments
        """
        position_names = ["LEFT", "CENTER", "RIGHT"]
        lines = []
        for pos in sorted(self._role_map.keys()):
            inst = self._role_map[pos]
            name = position_names[pos] if pos < len(position_names) else f"POS {pos}"
            lines.append(f"  {name}: {inst.upper()}")
        return "\n".join(lines)


def validate_role_assignment(
    num_players: int,
    instruments: List[str],
    guitar_handedness: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a role assignment configuration is valid.

    Args:
        num_players: Number of players
        instruments: List of instruments
        guitar_handedness: Guitar player handedness

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check player count
    if not 1 <= num_players <= 3:
        return False, f"Player count must be 1-3, got {num_players}"

    # Check instrument count matches
    if len(instruments) != num_players:
        return False, f"Need {num_players} instruments, got {len(instruments)}"

    # Check for duplicates
    if len(instruments) != len(set(instruments)):
        return False, "Duplicate instruments not allowed"

    # Check valid instruments
    valid = {"drums", "guitar", "piano"}
    for inst in instruments:
        if inst not in valid:
            return False, f"Invalid instrument: {inst}"

    # Check 3-player requires all instruments
    if num_players == 3:
        required = {"drums", "guitar", "piano"}
        if set(instruments) != required:
            return False, "3 players requires drums, guitar, and piano"

    # Check 2-player must have drums
    if num_players == 2 and "drums" not in instruments:
        # Actually, 2 players can have any combination
        # The rules say "Left = Drums, Right = Piano or Guitar" but
        # that assumes drums is selected. Let's allow any 2 unique instruments.
        pass

    # Check handedness
    if guitar_handedness not in ("right", "left"):
        return False, f"Invalid handedness: {guitar_handedness}"

    return True, None
