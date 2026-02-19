import pytest
from tannhauser.utils import midi_to_freq


class TestMidiToFreq:
    """Test the `midi_to_freq` function."""

    def test_a4_reference(self):
        """Test that MIDI note 69 (A4) returns 440 Hz."""
        assert midi_to_freq(69) == 440.0

    def test_c4(self):
        """Test that MIDI note 60 (C) returns correct frequency."""
        # C4 is 9 semitones below A4: 440 * 2^(-9/12)
        expected = 440.0 * (2.0**(-9 / 12))
        assert pytest.approx(midi_to_freq(60), rel=1e-9) == expected

    def test_c0(self):
        """Test that MIDI note 0 (C0) returns correct frequency."""
        # C0 is 69 semitones below A4
        expected = 440.0 * (2.0**(-69 / 12))
        assert pytest.approx(midi_to_freq(0), rel=1e-9) == expected

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

    def test_high_midi_note(self):
        """Test very high MIDI note (e.g., 127, highest MIDI value)."""
        freq = midi_to_freq(127)
        # 127 is 58 semitones above A4
        expected = 440.0 * (2.0**(58 / 12))
        assert pytest.approx(freq, rel=1e-9) == expected

    def test_negative_midi_note(self):
        """Test negative MIDI note (below C0)."""
        freq = midi_to_freq(-12)  # C-1, one octave below C0
        # -12 is 81 semitones below A4
        expected = 440.0 * (2.0**(-81 / 12))
        assert pytest.approx(freq, rel=1e-9) == expected

    def test_a5_double_a4(self):
        """Test that A5 (81) is exactly double the frequency of A4 (69)."""
        assert pytest.approx(midi_to_freq(81), rel=1e-9) == 880.0

    def test_a3_half_a4(self):
        """Test that A3 (57) is exactly half the frequency of A4 (69)."""
        assert pytest.approx(midi_to_freq(57), rel=1e-9) == 220.0
