import pytest
from tannhauser.utils import midi_to_freq


class TestMidiToFreq:
    """Test the `midi_to_freq` function."""

    @pytest.mark.parametrize('midi_note,expected_freq,description', [
        (69, 440.0, 'A4 reference note'),
        (60, 440.0 * (2.0 ** (-9 / 12)), 'C4, 9 semitones below A4'),
        (0, 440.0 * (2.0 ** (-69 / 12)), 'C0, lowest standard MIDI'),
        (127, 440.0 * (2.0 ** (58 / 12)), 'MIDI 127, highest standard'),
        (-12, 440.0 * (2.0 ** (-81 / 12)), 'C-1, one octave below C0'),
        (81, 880.0, 'A5, one octave above A4'),
        (57, 220.0, 'A3, one octave below A4'),
    ], ids=lambda x: x if isinstance(x, str) else '')
    def test_specific_midi_notes(self, midi_note, expected_freq, description):
        """Test specific MIDI note to frequency conversions."""
        assert pytest.approx(midi_to_freq(midi_note), rel=1e-9) == expected_freq

    def test_octave_relationship(self):
        """Test that notes an octave apart have frequency ratio of 2:1."""
        freq_a3 = midi_to_freq(57)  # A3
        freq_a4 = midi_to_freq(69)  # A4
        freq_a5 = midi_to_freq(81)  # A5

        assert pytest.approx(freq_a4 / freq_a3, rel=1e-9) == 2.0
        assert pytest.approx(freq_a5 / freq_a4, rel=1e-9) == 2.0

    def test_semitone_relationship(self):
        """Test that adjacent semitones have ratio of 2^(1/12)."""
        freq_c4 = midi_to_freq(60)  # C4
        freq_c_sharp_4 = midi_to_freq(61)  # C#4

        expected_ratio = 2.0**(1 / 12)
        assert pytest.approx(freq_c_sharp_4 / freq_c4,
                             rel=1e-9) == expected_ratio

    def test_fractional_midi_note(self):
        """Test microtonal support with fractional MIDI notes."""
        freq_60 = midi_to_freq(60.0)
        freq_60_5 = midi_to_freq(60.5)  # Quarter-tone above C4
        freq_61 = midi_to_freq(61.0)

        # 60.5 should be geometric mean of 60 and 61
        expected_60_5 = 440.0 * (2.0**(-8.5 / 12))
        assert pytest.approx(midi_to_freq(60.5), rel=1e-9) == expected_60_5

        # Verify 60.5 is between 60 and 61
        assert freq_60 < freq_60_5 < freq_61
