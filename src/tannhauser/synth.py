from __future__ import annotations

__all__ = ['Synth', 'SuperColliderSynth']

from abc import ABC, abstractmethod
from numbers import Number
from typing import Any, Self

from .sc import SuperCollider
from .utils import PathLike


class Synth(ABC):
    """Abstract base class for a synthesizer. Defines the interface for playing 
    notes, starting and stopping sequences, and setting parameters.
    """

    def __init__(self):
        self._params = {}
        self.ready = False

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


class SuperColliderSynth(Synth):
    """`Synth` SuperCollider implementation that uses an OSC client to send 
    messages to a SuperCollider server.
    """

    def __init__(self, sc: SuperCollider):
        super().__init__()
        self.sc = sc

    @classmethod
    def from_scd_files(cls, scd_files: list[PathLike]) -> SuperColliderSynth:
        """Create a `SuperColliderSynth` instance from a list of SuperCollider
        files. The files will be loaded into the SuperCollider server on boot.
        """
        sc = SuperCollider(include_scd_files=scd_files)
        return cls(sc)

    def boot(self) -> Self:
        """Start the SuperCollider server and load synth definitions."""
        super().boot()
        if not self.sc.ready:
            self.sc.boot()
        return self

    def quit(self) -> None:
        """Stop the SuperCollider server."""
        super().quit()
        self.sc.quit()

    def note_on(self,
                note_id: int,
                midi_note: int,
                velocity: float = 0.8) -> None:
        """Press a note."""
        self.sc.note_on(note_id, midi_note, velocity)

    def note_off(self, note_id: int) -> None:
        """Release a note."""
        self.sc.note_off(note_id)

    def play(self, name: str) -> None:
        """Play or resume a SC Tdef sequence."""
        self.sc.tdef_play(name)

    def stop(self, name: str) -> None:
        """Stop a SC Tdef sequence."""
        self.sc.tdef_stop(name)

    def pause(self, name: str) -> None:
        """Pause a SC Tdef sequence."""
        self.sc.tdef_pause(name)

    @staticmethod
    def _unpack_param_name(name: str) -> tuple[str, str]:
        s = name.split('.')
        if len(s) != 2:
            raise ValueError(
                "Parameter name must be in the format `ndef_name.param_name`")

        return s[0], s[1]

    def set_param(self, name: str, value: Number) -> None:
        """Set a SC synth parameter (Ndef attribute). The paramenter name is
        given by the joint name of the Ndef and its argument, e.g.
        `set_param('filter.freq', 1000)`.
        """
        ndef_name, param_name = self._unpack_param_name(name)
        self._register_param(name, value)

        self.sc.ndef_set(ndef_name, **{param_name: value})

    def set_params(self, params: dict[str, Number]) -> None:
        """Set multiple SC synth parameters at once."""
        ndef_params = {}
        for name, value in params.items():
            ndef_name, param_name = self._unpack_param_name(name)
            self._register_param(name, value)

            if ndef_name not in ndef_params:
                ndef_params[ndef_name] = {}
            ndef_params[ndef_name][param_name] = value

        for ndef_name, params in ndef_params.items():
            self.sc.ndef_set(ndef_name, **params)
