import pytest
from unittest.mock import Mock, patch, MagicMock

from tannhauser.controller import Controller, PianoUIController


class TestController:
    """Test the abstract `Controller` base class."""

    def test_is_abstract(self):
        """Test that `Controller` cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Controller()

    def test_context_manager(self):
        """Test that `Controller` can be used as context manager."""

        class ConcreteController(Controller):

            def __init__(self):
                self.stopped = False

            def start(self):
                return self

            def stop(self):
                self.stopped = True

        controller = ConcreteController()
        with controller as c:
            assert c is controller
            assert not controller.stopped

        assert controller.stopped


class TestPianoUIController:
    """Test the `PianoUIController` class."""

    def test_key_maps_no_collisions(self):
        """Test that all keyboard mappings do not collide."""
        note_keys = set(PianoUIController.NOTE_KEY_MAP.keys())
        mod_keys = set(PianoUIController.MOD_KEY_MAP.keys())
        control_keys = {
            PianoUIController.QUIT_KEY, PianoUIController.OCTAVE_UP_KEY,
            PianoUIController.OCTAVE_DOWN_KEY
        }

        # Ensure no overlaps between different key groups
        assert not note_keys & mod_keys
        assert not note_keys & control_keys
        assert not mod_keys & control_keys

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_init_default_values(self, mock_keyboard, mock_load_pynput):
        """Test initialization with default values."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()

        assert controller.velocity == 0.8
        assert controller.mod_func == 'linear'
        assert controller.mod_range == (0.0, 1.0)
        assert controller.offset == 60  # Start at C4
        assert len(controller._free_ids) == 1024

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_init_custom_values(self, mock_keyboard, mock_load_pynput):
        """Test initialization with custom values."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        on_mod = Mock()

        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release,
                                       on_mod=on_mod,
                                       velocity=0.5,
                                       mod_func='log',
                                       mod_range=(0.1, 0.9))

        assert controller.on_press is on_press
        assert controller.on_release is on_release
        assert controller.on_mod is on_mod
        assert controller.velocity == 0.5
        assert controller.mod_func == 'log'
        assert controller.mod_range == (0.1, 0.9)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_generate_and_release_id(self, mock_keyboard, mock_load_pynput):
        """Test ID generation and release."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        initial_count = len(controller._free_ids)

        # Generate an ID
        id1 = controller._generate_id()
        assert isinstance(id1, int)
        assert len(controller._free_ids) == initial_count - 1

        # Generate another ID
        id2 = controller._generate_id()
        assert id2 != id1
        assert len(controller._free_ids) == initial_count - 2

        # Release an ID
        controller._release_id(id1)
        assert len(controller._free_ids) == initial_count - 1

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_eval_mod_value_linear(self, mock_keyboard, mock_load_pynput):
        """Test mod value evaluation with linear function."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(mod_func='linear', mod_range=(0.0, 1.0))

        assert controller._eval_mod_value(0.0) == 0.0
        assert controller._eval_mod_value(0.5) == 0.5
        assert controller._eval_mod_value(1.0) == 1.0

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_eval_mod_value_log(self, mock_keyboard, mock_load_pynput):
        """Test mod value evaluation with log function."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(mod_func='log', mod_range=(0.0, 1.0))

        assert controller._eval_mod_value(0.0) == 0.0
        assert abs(controller._eval_mod_value(1.0) - 1.0) < 0.001
        # Log function should be non-linear
        mid = controller._eval_mod_value(0.5)
        assert mid > 0.5  # Log should be above linear at midpoint

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_eval_mod_value_invlog(self, mock_keyboard, mock_load_pynput):
        """Test mod value evaluation with invlog function."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(mod_func='invlog', mod_range=(0.0, 1.0))

        assert controller._eval_mod_value(0.0) == 0.0
        assert abs(controller._eval_mod_value(1.0) - 1.0) < 0.001
        # Invlog function should be non-linear (inverted from log)
        mid = controller._eval_mod_value(0.5)
        assert mid < 0.5  # Invlog should be below linear at midpoint

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_eval_mod_value_custom_range(self, mock_keyboard,
                                         mock_load_pynput):
        """Test mod value evaluation with custom range."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(mod_func='linear',
                                       mod_range=(100.0, 1000.0))

        assert controller._eval_mod_value(0.0) == 100.0
        assert controller._eval_mod_value(0.5) == 550.0
        assert controller._eval_mod_value(1.0) == 1000.0

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_eval_mod_value_invalid_func(self, mock_keyboard,
                                         mock_load_pynput):
        """Test mod value evaluation with invalid function raises error."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        controller.mod_func = 'invalid'

        with pytest.raises(ValueError, match='Unknown mod function'):
            controller._eval_mod_value(0.5)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_octave_property(self, mock_keyboard, mock_load_pynput):
        """Test octave property calculation."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()

        controller.offset = 60  # C4
        assert controller.octave == 4

        controller.offset = 48  # C3
        assert controller.octave == 3

        controller.offset = 72  # C5
        assert controller.octave == 5

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_get_note_name(self, mock_keyboard, mock_load_pynput):
        """Test getting note name from MIDI number."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()

        assert controller._get_note_name(60) == 'C4'
        assert controller._get_note_name(61) == 'C#4'
        assert controller._get_note_name(69) == 'A4'
        assert controller._get_note_name(72) == 'C5'
        assert controller._get_note_name(48) == 'C3'

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_octave_up(self, mock_keyboard, mock_load_pynput):
        """Test handling octave up key press."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        controller._update_display = Mock()
        controller.offset = 60  # C4

        mock_key = Mock()
        mock_key.char = PianoUIController.OCTAVE_UP_KEY

        controller._handle_key_press(mock_key)

        assert controller.offset == 72  # C5
        controller._update_display.assert_called_once()

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_octave_down(self, mock_keyboard, mock_load_pynput):
        """Test handling octave down key press."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        controller._update_display = Mock()
        controller.offset = 60  # C4

        mock_key = Mock()
        mock_key.char = PianoUIController.OCTAVE_DOWN_KEY

        controller._handle_key_press(mock_key)

        assert controller.offset == 48  # C3
        controller._update_display.assert_called_once()

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_octave_limits(self, mock_keyboard, mock_load_pynput):
        """Test octave change respects limits."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        controller._update_display = Mock()

        # Test upper limit
        controller.offset = 108  # C8
        mock_key_up = Mock()
        mock_key_up.char = PianoUIController.OCTAVE_UP_KEY
        controller._handle_key_press(mock_key_up)
        assert controller.offset == 108  # Should not exceed C8

        # Test lower limit
        controller.offset = 12  # C0
        mock_key_down = Mock()
        mock_key_down.char = PianoUIController.OCTAVE_DOWN_KEY
        controller._handle_key_press(mock_key_down)
        assert controller.offset == 12  # Should not go below C0

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_note_press(self, mock_keyboard, mock_load_pynput):
        """Test handling note key press."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        controller = PianoUIController(on_press=on_press)
        controller._update_display = Mock()

        mock_key = Mock()
        key = list(PianoUIController.NOTE_KEY_MAP.keys())[0]
        mock_key.char = key

        controller._handle_key_press(mock_key)

        assert len(controller.active_keys) == 1
        semitone, midi_note, note_id = list(controller.active_keys)[0]
        assert semitone == PianoUIController.NOTE_KEY_MAP[key]
        assert midi_note == controller.offset + semitone
        on_press.assert_called_once_with(note_id, midi_note,
                                         controller.velocity)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_note_press_ignores_repeat(self, mock_keyboard,
                                              mock_load_pynput):
        """Test that repeated key press is ignored."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        controller = PianoUIController(on_press=on_press)
        controller._update_display = Mock()

        mock_key = Mock()
        mock_key.char = list(PianoUIController.NOTE_KEY_MAP.keys())[0]

        # Press once
        controller._handle_key_press(mock_key)
        assert on_press.call_count == 1

        # Press again (should be ignored)
        controller._handle_key_press(mock_key)
        assert on_press.call_count == 1

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_note_release(self, mock_keyboard, mock_load_pynput):
        """Test handling note key release."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release)
        controller._update_display = Mock()

        mock_key = Mock()
        mock_key.char = list(PianoUIController.NOTE_KEY_MAP.keys())[0]

        # Press and release
        controller._handle_key_press(mock_key)
        note_id = list(controller.active_keys)[0][2]

        controller._handle_key_release(mock_key)

        assert len(controller.active_keys) == 0
        on_release.assert_called_once_with(note_id)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_mod_key(self, mock_keyboard, mock_load_pynput):
        """Test handling modulation key press."""
        mock_keyboard.Listener = MagicMock()

        on_mod = Mock()
        controller = PianoUIController(on_mod=on_mod)
        controller._update_display = Mock()

        mock_key = Mock()
        key = list(PianoUIController.MOD_KEY_MAP.keys())[4]  # Any mod key
        mock_key.char = key

        controller._handle_key_press(mock_key)

        mod_value = controller._eval_mod_value(
            PianoUIController.MOD_KEY_MAP[key])
        assert controller.mod_value == mod_value
        on_mod.assert_called_once_with(mod_value)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_handle_special_key_ignored(self, mock_keyboard, mock_load_pynput):
        """Test that special keys without char attribute are ignored."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        controller._update_display = Mock()

        mock_key = Mock()
        mock_key.char = Mock(side_effect=AttributeError)

        # Should not raise an error
        controller._handle_key_press(mock_key)
        controller._handle_key_release(mock_key)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_max_voices_default_is_none(self, mock_keyboard, mock_load_pynput):
        """Test that `max_voices` defaults to None (unlimited)."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController()
        assert controller.max_voices is None

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_max_voices_stored(self, mock_keyboard, mock_load_pynput):
        """Test that `max_voices` is stored correctly."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(max_voices=4)
        assert controller.max_voices == 4

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_voice_stealing_releases_oldest(self, mock_keyboard,
                                            mock_load_pynput):
        """Test that the oldest voice is stolen when `max_voices` is reached."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release,
                                       max_voices=2)
        controller._update_display = Mock()

        keys = list(PianoUIController.NOTE_KEY_MAP.keys())
        mock_key_a = Mock()
        mock_key_a.char = keys[0]
        mock_key_b = Mock()
        mock_key_b.char = keys[1]
        mock_key_c = Mock()
        mock_key_c.char = keys[2]

        controller._handle_key_press(mock_key_a)
        controller._handle_key_press(mock_key_b)
        oldest_id = list(controller.active_keys)[0][2]

        # Third press should steal the oldest voice
        controller._handle_key_press(mock_key_c)

        assert len(controller.active_keys) == 2
        on_release.assert_called_once_with(oldest_id)

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_voice_stealing_mono(self, mock_keyboard, mock_load_pynput):
        """Test monophonic mode steals on every new note."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release,
                                       max_voices=1)
        controller._update_display = Mock()

        keys = list(PianoUIController.NOTE_KEY_MAP.keys())
        for i in range(3):
            mock_key = Mock()
            mock_key.char = keys[i]
            controller._handle_key_press(mock_key)

        assert len(controller.active_keys) == 1
        assert on_press.call_count == 3
        assert on_release.call_count == 2  # Stolen twice

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_voice_stealing_recycles_id(self, mock_keyboard, mock_load_pynput):
        """Test that stolen voice IDs are returned to the free pool."""
        mock_keyboard.Listener = MagicMock()

        controller = PianoUIController(max_voices=1)
        controller._update_display = Mock()
        initial_free = len(controller._free_ids)

        keys = list(PianoUIController.NOTE_KEY_MAP.keys())
        for i in range(3):
            mock_key = Mock()
            mock_key.char = keys[i]
            controller._handle_key_press(mock_key)

        # Only 1 ID in use; the other two were recycled
        assert len(controller._free_ids) == initial_free - 1

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_note_memory_retriggers_on_release(self, mock_keyboard,
                                               mock_load_pynput):
        """Releasing the current note retriggers the previously held note."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release,
                                       max_voices=1)
        controller._update_display = Mock()

        keys = list(PianoUIController.NOTE_KEY_MAP.keys())
        mock_key_a = Mock()
        mock_key_a.char = keys[0]
        mock_key_b = Mock()
        mock_key_b.char = keys[1]

        controller._handle_key_press(mock_key_a)
        id_a = list(controller.active_keys)[0][2]

        controller._handle_key_press(mock_key_b)  # Steals A
        on_release.assert_called_once_with(id_a)
        id_b = list(controller.active_keys)[0][2]

        controller._handle_key_release(mock_key_b)  # A should retrigger

        on_release.assert_called_with(id_b)
        assert len(controller.active_keys) == 1
        _, midi_note, _ = controller.active_keys[0]
        assert midi_note == controller.offset + PianoUIController.NOTE_KEY_MAP[keys[0]]
        assert on_press.call_count == 3  # A, B, A retrigger

    @patch('tannhauser.controller._load_pynput')
    @patch('tannhauser.controller.keyboard')
    def test_note_memory_silent_release_no_side_effects(
            self, mock_keyboard, mock_load_pynput):
        """Releasing a held-but-stolen note does not call on_release or retrigger."""
        mock_keyboard.Listener = MagicMock()

        on_press = Mock()
        on_release = Mock()
        controller = PianoUIController(on_press=on_press,
                                       on_release=on_release,
                                       max_voices=1)
        controller._update_display = Mock()

        keys = list(PianoUIController.NOTE_KEY_MAP.keys())
        mock_key_a = Mock()
        mock_key_a.char = keys[0]
        mock_key_b = Mock()
        mock_key_b.char = keys[1]

        controller._handle_key_press(mock_key_a)
        controller._handle_key_press(mock_key_b)  # Steals A
        on_press.reset_mock()
        on_release.reset_mock()

        controller._handle_key_release(mock_key_a)  # A is held-but-silent

        assert len(controller.active_keys) == 1
        assert controller.active_keys[0][0] == PianoUIController.NOTE_KEY_MAP[keys[1]]
        on_release.assert_not_called()
        on_press.assert_not_called()
