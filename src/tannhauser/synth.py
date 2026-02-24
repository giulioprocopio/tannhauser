from __future__ import annotations

__all__ = ['Synth']

from abc import ABC, abstractmethod
from typing import Any, Protocol, Self


class Synth(ABC):
    """Abstract base class for a synthesizer. Defines the interface for playing 
    notes, starting and stopping sequences, and setting parameters.
    """

    def __init__(self):
        self._params = {}
        self.ready = False

    def _ensure_ready(self) -> None:
        if not self.ready:
            raise RuntimeError(
                'Synth is not ready. Call `boot` or use a context manager to'
                ' initialize the synth.')

    def boot(self) -> Self:
        self.ready = True
        return self

    def quit(self) -> None:
        self.ready = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.quit()

    @abstractmethod
    def note_on(self,
                note_id: int,
                midi_note: int,
                velocity: float = 0.8) -> None:
        pass

    @abstractmethod
    def note_off(self, note_id: int) -> None:
        pass

    @abstractmethod
    def play(self, name: str) -> None:
        pass

    @abstractmethod
    def stop(self, name: str) -> None:
        pass

    def pause(self, name: str) -> None:
        self.stop(name)

    def _register_param(self, name: str, value: Any) -> None:
        self._params[name] = value

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        pass

    def set_params(self, params: dict[str, Any]) -> None:
        for name, value in params.items():
            self.set_param(name, value)


class _SynthProtocol(Protocol):
    """Protocol for `Synth` mixins that need to reference a `Synth` instance
    using structural typing.
    """

    def note_on(self,
                note_id: int,
                midi_note: int,
                velocity: float = 0.8) -> None:
        ...

    def note_off(self, note_id: int) -> None:
        ...

    def play(self, name: str) -> None:
        ...

    def stop(self, name: str) -> None:
        ...

    def set_param(self, name: str, value: Any) -> None:
        ...
