from __future__ import annotations

__all__ = ['Synth', 'SuperColliderSynth']

from abc import ABC, abstractmethod
from numbers import Number
from typing import Any, Literal, Self

from .sc import SuperCollider
from .utils import PathLike


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
        self._ensure_ready()
        self.sc.note_on(note_id, midi_note, velocity)

    def note_off(self, note_id: int) -> None:
        """Release a note."""
        self._ensure_ready()
        self.sc.note_off(note_id)

    def play(self, name: str) -> None:
        """Play or resume a SC Tdef sequence."""
        self._ensure_ready()
        self.sc.tdef_play(name)

    def stop(self, name: str) -> None:
        """Stop a SC Tdef sequence."""
        self._ensure_ready()
        self.sc.tdef_stop(name)

    def pause(self, name: str) -> None:
        """Pause a SC Tdef sequence."""
        self._ensure_ready()
        self.sc.tdef_pause(name)

    @staticmethod
    def _unpack_param_name(
            name: str) -> tuple[Literal['ndef', 'tdef'], str, str]:
        s = name.split('.')
        if len(s) != 3:
            raise ValueError(
                'Parameter name must be in the format `type.name.param_name`')

        if s[0] not in ('ndef', 'tdef'):
            raise ValueError('Parameter is not a valid Ndef or Tdef parameter')

        return s[0], s[1], s[2]  # type: ignore[return-value]

    def set_param(self, name: str, value: Number) -> None:
        """Set a SC synth parameter (Ndef or Tdef attribute). The parameter
        name is given by the joint definition type, name of the definition and
        its argument, e.g. `set_param('ndef.filter.freq', 1000)`.
        """
        self._ensure_ready()

        def_type, def_name, param_name = self._unpack_param_name(name)
        self._register_param(name, value)

        match def_type:
            case 'ndef':
                self.sc.ndef_set(def_name, **{param_name: value})
            case 'tdef':
                self.sc.tdef_set(def_name, **{param_name: value})

    def set_params(self, params: dict[str, Number]) -> None:
        """Set multiple SC synth parameters at once."""
        def_params: dict[Literal['ndef', 'tdef'],
                         dict[str, dict[str, Number]]] = {}
        for name, value in params.items():
            def_type, def_name, param_name = self._unpack_param_name(name)
            self._register_param(name, value)

            if def_type not in def_params:
                def_params[def_type] = {}

            if def_name not in def_params[def_type]:
                def_params[def_type][def_name] = {}

            def_params[def_type][def_name][param_name] = value

        for def_type, defs in def_params.items():
            for def_name, params in defs.items():
                match def_type:
                    case 'ndef':
                        self.sc.ndef_set(def_name, **params)
                    case 'tdef':
                        self.sc.tdef_set(def_name, **params)
