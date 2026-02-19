__all__ = ['PathLike', 'midi_to_freq']

from numbers import Number
from pathlib import Path

PathLike = str | Path


def midi_to_freq(midi_note: float) -> float:
    return 440.0 * (2.0**((midi_note - 69) / 12))
