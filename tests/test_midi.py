from unittest.mock import Mock, patch
import pytest

import tannhauser.midi as midi_module
from tannhauser.midi import MidiController, MidiSynthMixin


@pytest.fixture(autouse=True)
def mock_mido():
    mock = Mock()
    with patch.object(midi_module, 'mido', mock):
        yield mock


def make_msg(type_, **kwargs):
    msg = Mock()
    msg.type = type_
    for k, v in kwargs.items():
        setattr(msg, k, v)
    return msg


class TestMidiController:
    """Test the `MidiController` class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        mc = MidiController()

        assert mc.port_name is None
        assert mc.on_press is None
        assert mc.on_release is None
        assert mc.on_cc_map is None
        assert mc.on_sustain is None
        assert mc.on_pitch is None
        assert mc.wrap_sustain_pedal is False
        assert mc._active_notes == {}
        assert len(mc._free_ids) == 1024
        assert mc._sustained is False
        assert mc._pending_release == set()
        assert mc._port is None

    def test_generate_id_raises_when_exhausted(self):
        """Test that `_generate_id` raises `RuntimeError` when no IDs remain."""
        mc = MidiController()
        mc._free_ids.clear()

        with pytest.raises(RuntimeError):
            mc._generate_id()

    def test_release_id_returns_to_free_ids(self):
        """Test that `_release_id` returns the ID to the free pool."""
        mc = MidiController()
        note_id = mc._generate_id()

        assert note_id not in mc._free_ids
        mc._release_id(note_id)
        assert note_id in mc._free_ids

    def test_note_on_calls_on_press(self):
        """Test that note-on calls `on_press` with the normalised velocity."""
        on_press = Mock()
        mc = MidiController(on_press=on_press)

        mc._handle_message(make_msg('note_on', note=60, velocity=100))

        on_press.assert_called_once()
        args = on_press.call_args[0]
        assert isinstance(args[0], int)
        assert args[1] == 60
        assert abs(args[2] - 100 / 127.0) < 1e-9

    def test_note_on_duplicate_ignored(self):
        """Test that a duplicate note-on for the same note is ignored."""
        on_press = Mock()
        mc = MidiController(on_press=on_press)
        msg = make_msg('note_on', note=60, velocity=100)

        mc._handle_message(msg)
        mc._handle_message(msg)

        assert on_press.call_count == 1

    def test_note_on_velocity_zero_treated_as_note_off(self):
        """Test that note-on with velocity zero is treated as note-off."""
        on_press = Mock()
        on_release = Mock()
        mc = MidiController(on_press=on_press, on_release=on_release)

        mc._handle_message(make_msg('note_on', note=60, velocity=80))
        mc._handle_message(make_msg('note_on', note=60, velocity=0))

        assert on_press.call_count == 1
        assert on_release.call_count == 1

    def test_note_off_calls_on_release_with_note_id(self):
        """Test that note-off calls `on_release` with the correct note ID."""
        on_press = Mock()
        on_release = Mock()
        mc = MidiController(on_press=on_press, on_release=on_release)
        mc._handle_message(make_msg('note_on', note=60, velocity=80))
        note_id = on_press.call_args[0][0]

        mc._handle_message(make_msg('note_off', note=60, velocity=0))

        on_release.assert_called_once_with(note_id)

    def test_note_off_unknown_note_ignored(self):
        """Test that note-off for an unknown note is ignored."""
        on_release = Mock()
        mc = MidiController(on_release=on_release)

        mc._handle_message(make_msg('note_off', note=60, velocity=0))

        on_release.assert_not_called()

    def test_note_off_with_sustain_held_defers_release(self):
        """Test that note-off while sustain is held defers release."""
        on_release = Mock()
        mc = MidiController(on_release=on_release, wrap_sustain_pedal=True)
        mc._handle_message(make_msg('control_change', control=64, value=127))
        mc._handle_message(make_msg('note_on', note=60, velocity=80))

        mc._handle_message(make_msg('note_off', note=60, velocity=0))

        on_release.assert_not_called()
        assert len(mc._pending_release) == 1

    def test_note_off_without_wrap_sustain_immediate(self):
        """Test that note-off is immediate when `wrap_sustain_pedal` is `False`."""
        on_release = Mock()
        mc = MidiController(on_release=on_release, wrap_sustain_pedal=False)
        mc._handle_message(make_msg('note_on', note=60, velocity=80))
        mc._handle_message(make_msg('control_change', control=64, value=127))

        mc._handle_message(make_msg('note_off', note=60, velocity=0))

        on_release.assert_called_once()

    def test_sustain_on_calls_on_sustain_true(self):
        """Test that CC 64 calls `on_sustain` with `True`."""
        on_sustain = Mock()
        mc = MidiController(on_sustain=on_sustain)

        mc._handle_message(make_msg('control_change', control=64, value=64))

        on_sustain.assert_called_once_with(True)

    def test_sustain_off_flushes_pending_and_calls_on_sustain_false(self):
        """Test that CC 64 flushes pending releases and calls `on_sustain` with `False`.
        """
        on_release = Mock()
        on_sustain = Mock()
        mc = MidiController(on_release=on_release, on_sustain=on_sustain,
                            wrap_sustain_pedal=True)
        mc._handle_message(make_msg('control_change', control=64, value=127))
        mc._handle_message(make_msg('note_on', note=60, velocity=80))
        mc._handle_message(make_msg('note_off', note=60, velocity=0))
        on_release.assert_not_called()

        mc._handle_message(make_msg('control_change', control=64, value=0))

        on_release.assert_called_once()
        on_sustain.assert_called_with(False)
        assert mc._pending_release == set()

    def test_cc_map_callback_called_with_normalised_value(self):
        """Test that a mapped CC callback receives a normalised value."""
        cb = Mock()
        mc = MidiController(on_cc_map={74: cb})

        mc._handle_message(make_msg('control_change', control=74, value=127))

        cb.assert_called_once_with(1.0)

    def test_cc_map_unmapped_control_ignored(self):
        """Test that an unmapped CC number is ignored."""
        cb = Mock()
        mc = MidiController(on_cc_map={74: cb})

        mc._handle_message(make_msg('control_change', control=1, value=64))

        cb.assert_not_called()

    def test_pitchwheel_calls_on_pitch_normalised(self):
        """Test that pitchwheel calls `on_pitch` with a normalised value."""
        on_pitch = Mock()
        mc = MidiController(on_pitch=on_pitch)

        mc._handle_message(make_msg('pitchwheel', pitch=8192))

        on_pitch.assert_called_once_with(1.0)

    def test_start_opens_port(self, mock_mido):
        """Test that `start` opens the MIDI input port."""
        mc = MidiController(port_name='TestPort')

        mc.start()

        mock_mido.open_input.assert_called_once_with(
            'TestPort', callback=mc._handle_message)

    def test_start_returns_self(self):
        """Test that `start` returns `self`."""
        mc = MidiController()

        result = mc.start()

        assert result is mc

    def test_stop_releases_active_and_pending_notes(self):
        """Test that `stop` releases all active and pending notes."""
        on_release = Mock()
        mc = MidiController(on_release=on_release, wrap_sustain_pedal=True)
        mc.start()
        mc._handle_message(make_msg('control_change', control=64, value=127))
        mc._handle_message(make_msg('note_on', note=60, velocity=80))
        mc._handle_message(make_msg('note_on', note=62, velocity=80))
        mc._handle_message(make_msg('note_off', note=60, velocity=0))

        mc.stop()

        assert on_release.call_count == 2

    def test_stop_closes_port(self, mock_mido):
        """Test that `stop` closes the MIDI port."""
        mc = MidiController()
        mc.start()
        port = mc._port

        mc.stop()

        port.close.assert_called_once()
        assert mc._port is None

    def test_stop_when_not_started_is_noop(self):
        """Test that `stop` before `start` is a no-op."""
        on_release = Mock()
        mc = MidiController(on_release=on_release)

        mc.stop()

        on_release.assert_not_called()

    def test_list_ports(self, mock_mido):
        """Test that `list_ports` delegates to `mido.get_input_names`."""
        MidiController.list_ports()

        mock_mido.get_input_names.assert_called_once()


class TestMidiSynthMixin:
    """Test the `MidiSynthMixin` mixin class."""

    @pytest.fixture
    def synth(self):
        class FakeSynth(MidiSynthMixin):
            note_on = Mock()
            note_off = Mock()
            pedal_sustain = Mock()
            set_param = Mock()

        return FakeSynth()

    def test_midi_device_returns_controller(self, synth):
        """Test that `midi_device` returns a `MidiController`."""
        ctrl = synth.midi_device()

        assert isinstance(ctrl, MidiController)

    def test_midi_device_wires_callbacks(self, synth):
        """Test that `midi_device` wires synth methods as callbacks."""
        ctrl = synth.midi_device()

        assert ctrl.on_press is synth.note_on
        assert ctrl.on_release is synth.note_off
        assert ctrl.on_sustain is synth.pedal_sustain

    def test_midi_device_no_cc_params_map(self, synth):
        """Test that `on_cc_map` is None when no `cc_params_map` is given."""
        ctrl = synth.midi_device()

        assert ctrl.on_cc_map is None

    def test_midi_device_cc_params_map_calls_set_param(self, synth):
        """Test that a CC callback calls `set_param` with the mapped param name."""
        ctrl = synth.midi_device(cc_params_map={74: 'cutoff'})

        ctrl.on_cc_map[74](0.5)

        synth.set_param.assert_called_once_with('cutoff', 0.5)

    def test_midi_device_cc_closure_per_param(self, synth):
        """Test that each CC number closes over its own param name."""
        ctrl = synth.midi_device(cc_params_map={74: 'cutoff', 71: 'resonance'})

        ctrl.on_cc_map[74](0.5)
        ctrl.on_cc_map[71](0.8)

        params_called = {c[0][0] for c in synth.set_param.call_args_list}
        assert 'cutoff' in params_called
        assert 'resonance' in params_called
