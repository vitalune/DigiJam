"""
Claude-powered voice selection for AI vocals.

Selects the optimal voice for each song section based on mood,
energy level, and genre, ensuring variety across sections.
"""

import json
import os
from typing import Optional, List

from dotenv import load_dotenv

# Import from parent module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze_wav import SongSection, SongStructure
from vocals.vocal_config import AVAILABLE_VOICES_EXTENDED


# Load environment variables
load_dotenv()


class VoiceSelector:
    """Selects optimal voices for song sections using Claude API."""

    SELECTION_PROMPT = """You are selecting the best voice for a song section.

Section Details:
- Name: {section_name}
- Mood: {mood}
- Energy Level: {energy_level}
- Lyrics Preview: {lyrics_preview}
- Suggested Style: {suggested_style}
- Duration: {duration} seconds

Available Voices:
{voices_json}

Previous section's voice: {previous_voice}

Voice Selection Criteria:
1. Voice tone should match the section's mood
2. Energy level compatibility is important
3. Genre appropriateness matters
4. Provide VARIETY - avoid using the same voice as the previous section when possible
5. Consider the suggested voice style from lyrics generation

Select the best voice and explain briefly.

Output JSON:
{{
  "voice_id": "<selected_voice_id>",
  "reasoning": "<1-2 sentence explanation>"
}}

Output ONLY valid JSON."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the voice selector.

        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def select_voice(
        self,
        section: SongSection,
        previous_voice: Optional[str] = None
    ) -> str:
        """
        Select the optimal voice for a single section.

        Args:
            section: Song section to select voice for
            previous_voice: Voice ID used in previous section (for variety)

        Returns:
            Selected voice ID
        """
        # Prepare voices JSON
        voices_json = json.dumps(AVAILABLE_VOICES_EXTENDED, indent=2)

        # Get previous voice name for context
        prev_voice_info = ""
        if previous_voice and previous_voice in AVAILABLE_VOICES_EXTENDED:
            prev_info = AVAILABLE_VOICES_EXTENDED[previous_voice]
            prev_voice_info = f"{prev_info['name']} ({prev_info['description']})"
        else:
            prev_voice_info = "None (this is the first section)"

        # Get lyrics preview (first 50 chars)
        lyrics_preview = (section.lyrics[:50] + "...") if section.lyrics and len(section.lyrics) > 50 else (section.lyrics or "No lyrics")

        prompt = self.SELECTION_PROMPT.format(
            section_name=section.name,
            mood=section.mood,
            energy_level=section.energy_level,
            lyrics_preview=lyrics_preview,
            suggested_style=section.suggested_voice_style or "not specified",
            duration=section.duration,
            voices_json=voices_json,
            previous_voice=prev_voice_info,
        )

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse JSON response
        response_text = message.content[0].text.strip()

        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: try to find voice_id in response
            for voice_id in AVAILABLE_VOICES_EXTENDED.keys():
                if voice_id in response_text:
                    return voice_id
            # Default to first voice if parsing fails
            return list(AVAILABLE_VOICES_EXTENDED.keys())[0]

        return data.get("voice_id", list(AVAILABLE_VOICES_EXTENDED.keys())[0])

    def select_voice_simple(
        self,
        section: SongSection,
        previous_voice: Optional[str] = None
    ) -> str:
        """
        Simple voice selection without Claude API (faster, for fallback).

        Uses heuristics based on mood and energy level.

        Args:
            section: Song section to select voice for
            previous_voice: Voice ID used in previous section (for variety)

        Returns:
            Selected voice ID
        """
        # Find voices matching energy level
        candidates = []
        for voice_id, info in AVAILABLE_VOICES_EXTENDED.items():
            if section.energy_level in info.get("energy_match", []):
                candidates.append(voice_id)

        # If no match, use all voices
        if not candidates:
            candidates = list(AVAILABLE_VOICES_EXTENDED.keys())

        # Filter by mood if possible
        mood_matches = []
        for voice_id in candidates:
            info = AVAILABLE_VOICES_EXTENDED[voice_id]
            voice_moods = [m.lower() for m in info.get("moods", [])]
            if section.mood.lower() in voice_moods:
                mood_matches.append(voice_id)

        if mood_matches:
            candidates = mood_matches

        # Avoid previous voice if possible
        if previous_voice and previous_voice in candidates and len(candidates) > 1:
            candidates.remove(previous_voice)

        # Return first candidate
        return candidates[0] if candidates else list(AVAILABLE_VOICES_EXTENDED.keys())[0]

    def select_voices_for_structure(
        self,
        structure: SongStructure,
        use_ai: bool = True
    ) -> SongStructure:
        """
        Select voices for all sections in a song structure.

        Args:
            structure: Song structure with sections
            use_ai: Whether to use Claude API (True) or simple heuristics (False)

        Returns:
            Updated song structure with voice IDs assigned
        """
        previous_voice: Optional[str] = None

        for section in structure.sections:
            # Skip user sections (no voice needed)
            if section.is_user_section:
                continue

            # Skip sections without lyrics
            if not section.lyrics:
                continue

            # Select voice
            if use_ai:
                section.voice_id = self.select_voice(section, previous_voice)
            else:
                section.voice_id = self.select_voice_simple(section, previous_voice)

            previous_voice = section.voice_id

        return structure

    def get_voice_for_mood(self, mood: str) -> str:
        """
        Quick lookup: get a voice that matches a mood.

        Args:
            mood: Mood string to match

        Returns:
            Voice ID that matches the mood
        """
        for voice_id, info in AVAILABLE_VOICES_EXTENDED.items():
            voice_moods = [m.lower() for m in info.get("moods", [])]
            if mood.lower() in voice_moods:
                return voice_id

        # Default to first voice
        return list(AVAILABLE_VOICES_EXTENDED.keys())[0]

    def get_voice_for_energy(self, energy_level: str) -> str:
        """
        Quick lookup: get a voice that matches an energy level.

        Args:
            energy_level: "low", "medium", or "high"

        Returns:
            Voice ID that matches the energy level
        """
        for voice_id, info in AVAILABLE_VOICES_EXTENDED.items():
            if energy_level in info.get("energy_match", []):
                return voice_id

        # Default to first voice
        return list(AVAILABLE_VOICES_EXTENDED.keys())[0]
