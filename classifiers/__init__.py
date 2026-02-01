"""Instrument classifiers for DigiJam gesture detection."""

from .drum_classifier import DrumClassifier
from .guitar_classifier import GuitarClassifier
from .piano_classifier import PianoClassifier

__all__ = ['DrumClassifier', 'GuitarClassifier', 'PianoClassifier']
