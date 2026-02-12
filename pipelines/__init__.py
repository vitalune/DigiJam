"""
Pipeline modules for DigiJam music generation.

Each pipeline handles a specific AI support level:
- high_pipeline: Fully automated (no user vocals)
- medium_pipeline: Collaborative (AI + user vocals)
- low_pipeline: User-driven (voice transformation)
"""

from .high_pipeline import HighPipeline, HighPipelineConfig, PipelineResult
from .medium_pipeline import MediumPipeline, MediumPipelineConfig
from .low_pipeline import LowPipeline, LowPipelineConfig

__all__ = [
    "HighPipeline",
    "HighPipelineConfig",
    "MediumPipeline",
    "MediumPipelineConfig",
    "LowPipeline",
    "LowPipelineConfig",
    "PipelineResult",
]
