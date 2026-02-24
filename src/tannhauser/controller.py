__all__ = ['Controller', 'PianoUIController']

from abc import ABC, abstractmethod
import curses
import logging
from math import log10
import threading
from typing import Callable, Self, Literal

pynput = None
keyboard = None


def _load_pynput():
    global pynput, keyboard
    if pynput is None:
        import importlib
        try:
            pynput = importlib.import_module('pynput')
            keyboard = pynput.keyboard
        except ImportError as e:
            raise ImportError(
                '`pynput` library is required for keyboard input. Install with'
                ' `pip install pynput`.') from e


from .synth import Synth, _SynthProtocol

logger = logging.getLogger(__name__)


class Controller(ABC):
    """Abstract base class for a controller. Defines the interface for handling
    input events and mapping them to synthesizer actions.
    """

    @abstractmethod
    def start(self) -> Self:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class PianoUIController(Controller):
    """Terminal UI to send MIDI notes callbacks based on PC keyboard input."""

    # Map keyboard keys to semitone offsets from C.
    NOTE_KEY_MAP = {
        'a': 0,
        'w': 1,
        's': 2,
        'e': 3,
        'd': 4,
        'f': 5,
        't': 6,
        'g': 7,
        'y': 8,
        'h': 9,
        'u': 10,
        'j': 11,
        'k': 12,
        'o': 13,
        'l': 14,
        'p': 15
    }
    # Map numbers from 1 to 9 to modulation linear range from 0.0 to 1.0
    MOD_KEY_MAP = {
        '1': 0.0,
        '2': 0.125,
        '3': 0.25,
        '4': 0.375,
        '5': 0.5,
        '6': 0.625,
        '7': 0.75,
        '8': 0.875,
        '9': 1.0
    }
    OCTAVE_UP_KEY = '+'
    OCTAVE_DOWN_KEY = '-'
    QUIT_KEY = 'q'

    KEY_NAMES = [
        'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B', 'C',
        'C#', 'D', 'D#'
    ]

    def __init__(self,
                 on_press: Callable[[int, int, float], None] | None = None,
                 on_release: Callable[[int], None] | None = None,
                 on_mod: Callable[[float], None] | None = None,
                 velocity: float = 0.8,
                 mod_func: Literal['linear', 'log', 'invlog'] = 'linear',
                 mod_range: tuple[float, float] = (0.0, 1.0)):
        _load_pynput()

        self.on_press = on_press
        self.on_release = on_release
        self.on_mod = on_mod

        self.velocity = velocity
        self.mod_func = mod_func
        self.mod_range = mod_range

        # Start at C4 (MIDI note 60)
        self.offset = 60

        self.pressed_keys: set[tuple[
            int, int, int]] = set()  # Semitone, MIDI note, note ID
        assert keyboard is not None
        self.listener = keyboard.Listener(on_press=self._handle_key_press,
                                          on_release=self._handle_key_release)

        self.mod_value: float | None = None

        self._free_ids = set(range(1024))  # Hopefully enough for any use case

        self.stdscr: curses.window | None = None
        self._ui_thread: threading.Thread | None = None
        self._running = False

    def mount(self, synth: Synth, mod_param: str | None = None) -> None:
        """Mount a synthesizer to this controller. The controller will call the
        appropriate methods on the synth when keys are pressed and released.
        """
        self.on_press = synth.note_on
        self.on_release = synth.note_off

        if mod_param:

            def on_mod(value: float) -> None:
                synth.set_param(mod_param, value)

            self.on_mod = on_mod

    def _generate_id(self) -> int:
        if not self._free_ids:
            raise RuntimeError('No more free IDs available')

        return self._free_ids.pop()

    def _release_id(self, i: int) -> None:
        self._free_ids.add(i)

    def _eval_mod_value(self, x: float) -> float:
        if self.mod_func == 'linear':
            m = x
        elif self.mod_func == 'log':
            m = log10(9 * x + 1)
        elif self.mod_func == 'invlog':
            m = 1 - log10(9 * (1 - x) + 1)
        else:
            raise ValueError(f'Unknown mod function: {self.mod_func}')

        min_val, max_val = self.mod_range
        return min_val + m * (max_val - min_val)

    def _handle_key_press(self, key) -> None:
        try:
            char = key.char.lower()
        except AttributeError:
            return  # Ignore special keys

        if char == self.OCTAVE_UP_KEY:
            self.offset += 12
            self.offset = min(self.offset, 108)  # Limit to C8

            self._update_display()
        elif char == self.OCTAVE_DOWN_KEY:
            self.offset -= 12
            self.offset = max(self.offset, 12)  # Limit to C0

            self._update_display()
        elif char in self.NOTE_KEY_MAP:
            semitone = self.NOTE_KEY_MAP[char]

            for s, _, _ in self.pressed_keys:
                if s == semitone:
                    # Key is already pressed, ignore repeat
                    return

            midi_note = self.offset + semitone
            note_id = self._generate_id()
            # Store tuple to keep track of octave changes.
            self.pressed_keys.add((semitone, midi_note, note_id))

            self._update_display()

            if self.on_press:
                self.on_press(note_id, midi_note, self.velocity)
        elif char in self.MOD_KEY_MAP:
            m = self.MOD_KEY_MAP[char]
            self.mod_value = self._eval_mod_value(m)

            self._update_display()

            if self.on_mod:
                self.on_mod(self.mod_value)

    def _handle_key_release(self, key) -> None:
        try:
            char = key.char.lower()
        except AttributeError:
            return  # Ignore special keys

        if char in self.NOTE_KEY_MAP:
            semitone = self.NOTE_KEY_MAP[char]
            # Handle case where key is pressed and then octave is changed
            # before release: release should still trigger for the original
            # note.
            for s, midi_note, note_id in list(self.pressed_keys):
                if s == semitone:
                    self.pressed_keys.remove((s, midi_note, note_id))
                    self._update_display()
                    if self.on_release:
                        self.on_release(note_id)
                    self._release_id(note_id)

    @property
    def octave(self) -> int:
        """Calculate current octave based on offset."""
        return (self.offset - 12) // 12

    def _get_note_name(self, midi_note: int) -> str:
        semitone = midi_note % 12
        octave = (midi_note // 12) - 1
        return f'{self.KEY_NAMES[semitone]}{octave}'

    def _update_display(self) -> None:
        if not self.stdscr:
            return

        try:
            self.stdscr.clear()
            _, width = self.stdscr.getmaxyx()

            title_line = "Piano"
            title_x = (width - len(title_line)) // 2
            self.stdscr.addstr(1, max(0, title_x), title_line,
                               curses.A_BOLD | curses.A_UNDERLINE)

            octave_line = f'Octave: {self.octave}'
            octave_x = (width - len(octave_line)) // 2
            self.stdscr.addstr(3, max(0, octave_x), octave_line)

            if self.pressed_keys:
                sorted_keys = sorted(self.pressed_keys, key=lambda x: x[1])
                notes_str = ', '.join([
                    self._get_note_name(midi_note)
                    for _, midi_note, _ in sorted_keys
                ])
                pressed_line = f'Pressed: {notes_str}'
            else:
                pressed_line = 'Pressed: —'

            pressed_x = (width - len(pressed_line)) // 2
            self.stdscr.addstr(4, max(0, pressed_x), pressed_line)

            if self.mod_value is not None:
                mod_line = f'Mod: {self.mod_value:.2f}'
            else:
                mod_line = 'Mod: —'

            mod_x = (width - len(mod_line)) // 2
            self.stdscr.addstr(5, max(0, mod_x), mod_line)

            instr_line = (
                f'Press {self.QUIT_KEY} to quit, [{self.OCTAVE_UP_KEY}'
                f'{self.OCTAVE_DOWN_KEY}] to change octave,'
                f" [{''.join(self.NOTE_KEY_MAP.keys())}] to play notes,"
                f" [{''.join(self.MOD_KEY_MAP.keys())}] to modulate")
            instr_x = (width - len(instr_line)) // 2
            self.stdscr.addstr(7, max(0, instr_x), instr_line, curses.A_DIM)

            self.stdscr.refresh()
        except curses.error:
            pass

    def _run_ui(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        curses.curs_set(0)  # Hide cursor
        self.stdscr.nodelay(True)  # Non-blocking input

        self._update_display()

        while self._running:
            try:
                key = self.stdscr.getch()
                if key == ord(self.QUIT_KEY):
                    self._running = False
                    break
                # Detect window resize
                elif key == curses.KEY_RESIZE:
                    self._update_display()
            except curses.error:
                # Window was resized, update display
                self._update_display()
            except:
                pass

            threading.Event().wait(0.05)

        self.stdscr = None

    def start(self) -> Self:
        """Start keyboard listener and terminal UI."""
        logger.info('Starting piano UI')
        self._running = True
        self.listener.start()

        # Run curses UI in main thread (curses requirement)
        curses.wrapper(self._run_ui)

        logger.info('Piano UI stopped')
        return self

    def stop(self) -> None:
        """Stop keyboard listener and UI."""
        logger.info('Stopping piano UI')
        self._running = False
        if self.listener.is_alive():
            self.listener.stop()


class PianoUISynthMixin:
    """Add a `piano_ui` method to a `Synth` class to easily create a bound
    `PianoUIController`.
    """

    def piano_ui(self: _SynthProtocol,
                 mod_param: str | None = None,
                 **controller_kwargs) -> PianoUIController:
        """Create a `PianoUIController` bound to this synth. The controller will
        call the appropriate methods on the synth when keys are pressed and
        released.
        """
        controller = PianoUIController(**controller_kwargs)

        controller.on_press = self.note_on
        controller.on_release = self.note_off

        if mod_param:

            def on_mod(value: float) -> None:
                self.set_param(mod_param, value)

            controller.on_mod = on_mod

        return controller
