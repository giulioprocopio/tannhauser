__all__ = ['MidiController', 'MidiSynthMixin']

import logging
from typing import Any, Callable, Self

from .controller import Controller
from .synth import _SynthProtocol

logger = logging.getLogger(__name__)

mido = None


def _load_mido():
    global mido
    if mido is None:
        import importlib
        try:
            mido = importlib.import_module('mido')
        except ImportError as e:
            raise ImportError(
                '`mido` library is required for MIDI input. Install with'
                ' `pip install mido python-rtmidi`') from e


class MidiController(Controller):
    """Listen for MIDI input from a hardware keyboard and forward note,
    control-change, sustain pedal, and pitch-wheel events to callbacks.

    `start()` is non-blocking: it opens the port and registers a background
    callback, then returns immediately. Call `stop()` (or use as a context
    manager) to close the port.
    """

    def __init__(self,
                 port_name: str | None = None,
                 on_press: Callable[[int, int, float], None] | None = None,
                 on_release: Callable[[int], None] | None = None,
                 on_cc_map: dict[int, Callable[[float], None]] | None = None,
                 on_sustain: Callable[[bool], None] | None = None,
                 on_pitch: Callable[[float], None] | None = None,
                 wrap_sustain_pedal: bool = False):
        """If `port_name` is `None`, opens the first available port. Use
        `MidiController.list_ports()` to enumerate options.

        `on_cc_map` maps CC number to callback modulation with a float from 0 
        to 1. `on_sustain` is called with sustain state whenever CC 64 toggles its state. `on_pitch` is called with float from −1 to 1 on pitchwheel 
        messages.

        When `wrap_sustain_pedal` is `True`, note-off events are held while CC 
        64 is active and released when the pedal lifts (Python-layer sustain
        logic).
        """
        _load_mido()

        self.port_name = port_name

        self.on_press = on_press
        self.on_release = on_release
        self.on_cc_map = on_cc_map
        self.on_sustain = on_sustain
        self.on_pitch = on_pitch

        self.wrap_sustain_pedal = wrap_sustain_pedal

        self._active_notes: dict[int, int] = {}
        self._free_ids = set(range(1024))
        self._sustained: bool = False
        self._pending_release: set[int] = set()

        self._port: Any = None

    @staticmethod
    def list_ports() -> list[str]:
        """Return the names of all available MIDI input ports."""
        _load_mido()
        assert mido is not None
        return mido.get_input_names()

    def _generate_id(self) -> int:
        if not self._free_ids:
            raise RuntimeError('No more free IDs available')
        return self._free_ids.pop()

    def _release_id(self, i: int) -> None:
        self._free_ids.add(i)

    def _handle_message(self, msg) -> None:
        if msg.type == 'note_on' and msg.velocity > 0:
            midi_note = msg.note
            if midi_note in self._active_notes:
                return  # Duplicate note trigger without release, ignore

            note_id = self._generate_id()
            self._active_notes[midi_note] = note_id

            if self.on_press:
                self.on_press(note_id, midi_note, msg.velocity / 127.0)
        elif msg.type == 'note_off' or (msg.type == 'note_on'
                                        and msg.velocity == 0):
            midi_note = msg.note
            if midi_note in self._active_notes:
                note_id = self._active_notes.pop(midi_note)
                if self.wrap_sustain_pedal and self._sustained:
                    self._pending_release.add(note_id)
                else:
                    if self.on_release:
                        self.on_release(note_id)
                    self._release_id(note_id)
        elif msg.type == 'control_change':
            if msg.control == 64:
                on = msg.value >= 64
                if self.wrap_sustain_pedal:
                    self._sustained = on
                    if not on:
                        for note_id in list(self._pending_release):
                            if self.on_release:
                                self.on_release(note_id)
                            self._release_id(note_id)
                    
                        self._pending_release.clear()
                if self.on_sustain:
                    self.on_sustain(on)

            if self.on_cc_map and msg.control in self.on_cc_map:
                self.on_cc_map[msg.control](msg.value / 127.0)
        elif msg.type == 'pitchwheel':
            if self.on_pitch:
                self.on_pitch(msg.pitch / 8192.0)

    def start(self) -> Self:
        """Open the MIDI port and start the background listener."""
        assert mido is not None
        logger.info(
            f'Opening MIDI input port: {self.port_name or "first available"}')
        self._port = mido.open_input(self.port_name,
                                     callback=self._handle_message)

        logger.info(f'MIDI controller listening on: {self._port.name}')
        return self

    def stop(self) -> None:
        """Close the MIDI port and release all active notes."""
        if self._port is not None:
            for note_id in list(self._pending_release):
                if self.on_release:
                    self.on_release(note_id)
                self._release_id(note_id)
            
            self._pending_release.clear()

            for note_id in list(self._active_notes.values()):
                if self.on_release:
                    self.on_release(note_id)

            self._active_notes.clear()

            self._port.close()
            self._port = None
            logger.info('MIDI controller stopped')


class MidiSynthMixin:
    """Mixin that adds `midi_device` to a `Synth` subclass, wiring note, params,
    pitch wheel and sustain callbacks automatically.
    """

    def midi_device(self: _SynthProtocol,
                    cc_params_map: dict[int, str] | None = None,
                    **controller_kwargs) -> MidiController:
        """Create a `MidiController` bound to this synth. `cc_params_map` maps 
        CC MIDI numbers to synth param name.
        """
        on_cc_map = {
            cc_num: (lambda p: lambda v: self.set_param(p, v))(param)
            for cc_num, param in cc_params_map.items()
        } if cc_params_map else None

        controller = MidiController(**controller_kwargs)

        controller.on_press = self.note_on
        controller.on_release = self.note_off
        controller.on_cc_map = on_cc_map
        controller.on_sustain = self.pedal_sustain
        #controller.on_pitch = ...

        return controller
