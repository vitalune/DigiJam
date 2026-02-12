"""
Claude-powered lyrics generation for AI vocals.

Analyzes song structure and generates lyrics for each section,
with support for both high AI mode (complete lyrics) and
medium AI mode (lyrics with gaps for user participation).
"""

import json
import os
from typing import Optional, List
from dataclasses import asdict

from dotenv import load_dotenv

# Import from parent module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze_wav import AudioFeatures, SongSection, SongStructure


# Load environment variables
load_dotenv()


class LyricsGenerator:
    """Generates song sections and lyrics using Claude API."""

    SECTION_ANALYSIS_PROMPT = """You are a music analyst. Analyze this instrumental track and identify its sections.

Audio Features:
{features_json}

Track Duration: {duration_seconds} seconds
BPM: {bpm}
Key: {key}

Identify the song structure by detecting these possible sections:
1. Intro (typically 0-8 seconds, building energy)
2. Verse sections (melodic development, moderate energy)
3. Chorus sections (peak energy, memorable hooks)
4. Bridge (contrasting section, often near 2/3 through)
5. Outro (winding down, final 8-15 seconds)

Based on the tempo ({bpm} BPM) and energy profile, output a JSON structure:

{{
  "sections": [
    {{
      "name": "intro",
      "start_time": 0.0,
      "end_time": 8.0,
      "mood": "building",
      "energy_level": "low"
    }},
    {{
      "name": "verse1",
      "start_time": 8.0,
      "end_time": 24.0,
      "mood": "contemplative",
      "energy_level": "medium"
    }}
  ]
}}

Use these mood options: "building", "energetic", "contemplative", "triumphant", "melancholic", "uplifting", "intense", "peaceful"
Use these energy levels: "low", "medium", "high"

Output ONLY valid JSON, no explanations."""

    LYRICS_COMPLETE_PROMPT = """Generate COMPLETE lyrics for a {genre} track in {key} at {bpm} BPM.

Track Duration: {duration} seconds
Music Mood: {mood_description}
{user_lyrics_prompt}
Section Structure:
{sections_json}

Guidelines:
- Match mood and energy per section
- Chorus sections should have memorable, repeatable phrases
- Verses tell a story or develop themes
- Bridge provides emotional contrast
- Keep lines singable - 4-8 syllables per line ideal
- Match the {key} tonality mood ({key_mood})
- Estimate 2-3 words per second for normal singing pace

Output JSON with lyrics for each section:
{{
  "sections": [
    {{
      "name": "verse1",
      "lyrics": "First line of verse\\nSecond line continues",
      "suggested_voice_style": "warm and intimate"
    }},
    {{
      "name": "chorus1",
      "lyrics": "Memorable chorus line\\nRepeatable hook",
      "suggested_voice_style": "powerful and soaring"
    }}
  ]
}}

Output ONLY valid JSON."""

    LYRICS_WITH_GAPS_PROMPT = """Generate PARTIAL lyrics for a {genre} track in {key} at {bpm} BPM.
This is a collaborative song where AI sings some parts and the USER fills in gaps.

Track Duration: {duration} seconds
Music Mood: {mood_description}
{user_lyrics_prompt}
Section Structure:
{sections_json}

Guidelines for gap placement:
- Mark sections where user should participate with is_user_section: true
- Common patterns to choose from:
  * AI sings verses, USER sings choruses (call-and-response)
  * AI sings lead lines, USER does backing/harmony
  * Alternating: AI handles complex parts, user handles simpler melodic parts
- Ensure gaps are musically satisfying (at phrase boundaries)
- User sections should be easier rhythmically (simpler timing)
- Leave 30-50% of the song as user participation gaps
- For user sections, provide a brief hint of what they should sing (theme/mood)

Output JSON with lyrics and gap markers:
{{
  "sections": [
    {{
      "name": "verse1",
      "lyrics": "AI sings this verse\\nWith these words",
      "suggested_voice_style": "warm and smooth",
      "is_user_section": false
    }},
    {{
      "name": "chorus1",
      "lyrics": null,
      "suggested_voice_style": "",
      "is_user_section": true,
      "user_hint": "Sing something uplifting about hope"
    }}
  ]
}}

Output ONLY valid JSON."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the lyrics generator.

        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Import anthropic here to avoid import errors if not installed
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def analyze_sections(
        self,
        features: AudioFeatures,
        duration: float
    ) -> List[SongSection]:
        """
        Analyze audio features to detect song sections.

        Args:
            features: Extracted audio features
            duration: Track duration in seconds

        Returns:
            List of SongSection objects
        """
        features_json = json.dumps(asdict(features), indent=2)

        prompt = self.SECTION_ANALYSIS_PROMPT.format(
            features_json=features_json,
            duration_seconds=duration,
            bpm=features.tempo_bpm,
            key=features.key,
        )

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse JSON response
        response_text = message.content[0].text.strip()

        # Try to extract JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse section analysis response: {e}\nResponse: {response_text}")

        # Convert to SongSection objects
        sections = []
        for s in data.get("sections", []):
            section = SongSection(
                name=s["name"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                mood=s.get("mood", "neutral"),
                energy_level=s.get("energy_level", "medium"),
            )
            sections.append(section)

        return sections

    def generate_lyrics(
        self,
        sections: List[SongSection],
        key: str,
        bpm: float,
        mood_description: str = "",
        genre: str = "pop",
        lyrics_prompt: str = ""
    ) -> List[SongSection]:
        """
        Generate complete lyrics for HIGH AI mode.

        Args:
            sections: List of song sections
            key: Musical key
            bpm: Tempo in BPM
            mood_description: Description of the track's mood
            genre: Music genre
            lyrics_prompt: User's description of what lyrics should be about

        Returns:
            List of SongSection objects with lyrics filled in
        """
        # Determine key mood
        key_mood = "melancholic, introspective" if "minor" in key.lower() else "uplifting, bright"

        # Calculate total duration
        duration = max(s.end_time for s in sections) if sections else 0

        sections_json = json.dumps([
            {
                "name": s.name,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration": s.duration,
                "mood": s.mood,
                "energy_level": s.energy_level,
            }
            for s in sections
        ], indent=2)

        # Format user lyrics prompt if provided
        user_lyrics_section = ""
        if lyrics_prompt:
            user_lyrics_section = f"\nUser's Lyrics Request: {lyrics_prompt}\nIMPORTANT: Incorporate the user's requested theme, style, and subject matter into the lyrics.\n"

        prompt = self.LYRICS_COMPLETE_PROMPT.format(
            genre=genre,
            key=key,
            bpm=bpm,
            duration=duration,
            mood_description=mood_description or "varied moods throughout",
            sections_json=sections_json,
            key_mood=key_mood,
            user_lyrics_prompt=user_lyrics_section,
        )

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse lyrics response: {e}\nResponse: {response_text}")

        # Update sections with lyrics
        lyrics_map = {s["name"]: s for s in data.get("sections", [])}

        for section in sections:
            if section.name in lyrics_map:
                lyrics_data = lyrics_map[section.name]
                section.lyrics = lyrics_data.get("lyrics")
                section.suggested_voice_style = lyrics_data.get("suggested_voice_style", "")
                section.is_user_section = False

        return sections

    def generate_lyrics_with_gaps(
        self,
        sections: List[SongSection],
        key: str,
        bpm: float,
        mood_description: str = "",
        genre: str = "pop",
        lyrics_prompt: str = ""
    ) -> List[SongSection]:
        """
        Generate partial lyrics with gaps for MEDIUM AI mode.

        Args:
            sections: List of song sections
            key: Musical key
            bpm: Tempo in BPM
            mood_description: Description of the track's mood
            genre: Music genre
            lyrics_prompt: User's description of what lyrics should be about

        Returns:
            List of SongSection objects with some lyrics and some marked as user sections
        """
        # Calculate total duration
        duration = max(s.end_time for s in sections) if sections else 0

        sections_json = json.dumps([
            {
                "name": s.name,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration": s.duration,
                "mood": s.mood,
                "energy_level": s.energy_level,
            }
            for s in sections
        ], indent=2)

        # Format user lyrics prompt if provided
        user_lyrics_section = ""
        if lyrics_prompt:
            user_lyrics_section = f"\nUser's Lyrics Request: {lyrics_prompt}\nIMPORTANT: Incorporate the user's requested theme, style, and subject matter into the AI-generated lyrics. Also guide user sections to follow the same theme.\n"

        prompt = self.LYRICS_WITH_GAPS_PROMPT.format(
            genre=genre,
            key=key,
            bpm=bpm,
            duration=duration,
            mood_description=mood_description or "varied moods throughout",
            sections_json=sections_json,
            user_lyrics_prompt=user_lyrics_section,
        )

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse lyrics response: {e}\nResponse: {response_text}")

        # Update sections with lyrics and gap markers
        lyrics_map = {s["name"]: s for s in data.get("sections", [])}

        for section in sections:
            if section.name in lyrics_map:
                lyrics_data = lyrics_map[section.name]
                section.lyrics = lyrics_data.get("lyrics")
                section.suggested_voice_style = lyrics_data.get("suggested_voice_style", "")
                section.is_user_section = lyrics_data.get("is_user_section", False)

        return sections

    def create_song_structure(
        self,
        features: AudioFeatures,
        ai_support_level: str = "high",
        genre: str = "pop",
        mood_description: str = "",
        lyrics_prompt: str = ""
    ) -> SongStructure:
        """
        Complete pipeline: analyze sections and generate lyrics.

        Args:
            features: Extracted audio features
            ai_support_level: "high" for complete lyrics, "medium" for lyrics with gaps
            genre: Music genre for lyric style
            mood_description: Optional mood description
            lyrics_prompt: User's description of what lyrics should be about

        Returns:
            Complete SongStructure with sections and lyrics
        """
        # Step 1: Analyze sections
        sections = self.analyze_sections(features, features.duration_seconds)

        # Step 2: Generate lyrics based on AI support level
        if ai_support_level == "high":
            sections = self.generate_lyrics(
                sections=sections,
                key=features.key,
                bpm=features.tempo_bpm,
                mood_description=mood_description,
                genre=genre,
                lyrics_prompt=lyrics_prompt,
            )
        elif ai_support_level == "medium":
            sections = self.generate_lyrics_with_gaps(
                sections=sections,
                key=features.key,
                bpm=features.tempo_bpm,
                mood_description=mood_description,
                genre=genre,
                lyrics_prompt=lyrics_prompt,
            )
        # "low" mode doesn't need lyrics generation

        # Create structure
        return SongStructure(
            total_duration=features.duration_seconds,
            bpm=features.tempo_bpm,
            key=features.key,
            sections=sections,
        )
