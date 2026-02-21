import pytest
from unittest.mock import Mock, patch

from tannhauser.synth import Synth, SuperColliderSynth


class TestSynth:
    """Test the abstract `Synth` base class."""

    def test_is_abstract(self):
        """Test that `Synth` cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Synth()

    def test_context_manager(self):
        """Test that `Synth` can be used as context manager."""

        class ConcreteSynth(Synth):

            def __init__(self):
                super().__init__()
                self.quit_called = False

            def note_on(self, note_id, midi_note, velocity=0.8):
                pass

            def note_off(self, note_id):
                pass

            def play(self, name):
                pass

            def stop(self, name):
                pass

            def set_param(self, name, value):
                pass

            def quit(self):
                super().quit()
                self.quit_called = True

        synth = ConcreteSynth()
        with synth as s:
            assert s is synth
            assert not synth.quit_called

        assert synth.quit_called

    def test_boot_sets_ready(self, concrete_synth):
        """Test that calling `boot` sets ready flag."""
        assert not concrete_synth.ready

        concrete_synth.boot()
        assert concrete_synth.ready

    def test_quit_unsets_ready(self, concrete_synth):
        """Test that calling `quit` unsets ready flag."""
        concrete_synth.boot()
        assert concrete_synth.ready

        concrete_synth.quit()
        assert not concrete_synth.ready

    def test_register_param(self, concrete_synth):
        """Test that `_register_param` stores parameters."""
        concrete_synth.set_param('test_param', 100)
        assert concrete_synth._params['test_param'] == 100

    def test_ensure_ready_raises_when_not_ready(self, concrete_synth):
        """Test that `_ensure_ready` raises `RuntimeError` when not booted."""
        assert not concrete_synth.ready

        with pytest.raises(RuntimeError, match='not ready'):
            concrete_synth._ensure_ready()

    def test_ensure_ready_passes_when_ready(self, concrete_synth):
        """Test that `_ensure_ready` doesn't raise when booted."""
        concrete_synth.boot()
        assert concrete_synth.ready

        # Should not raise
        concrete_synth._ensure_ready()


class TestSuperColliderSynth:
    """Test the `SuperColliderSynth` class."""

    def test_init(self, mock_supercollider):
        """Test initialization with `SuperCollider` instance."""
        synth = SuperColliderSynth(mock_supercollider)
        assert synth.sc is mock_supercollider

    def test_from_scd_files(self):
        """Test creating synth from SCD files."""
        with patch('tannhauser.synth.SuperCollider') as mock_sc_class:
            mock_sc_instance = Mock()
            mock_sc_class.return_value = mock_sc_instance

            scd_files = ['file1.scd', 'file2.scd']
            synth = SuperColliderSynth.from_scd_files(scd_files)

            mock_sc_class.assert_called_once_with(include_scd_files=scd_files)
            assert synth.sc is mock_sc_instance

    def test_boot_starts_sc(self, mock_supercollider):
        """Test that calling synth `boot` starts `SuperCollider` if not ready.
        """
        mock_supercollider.ready = False
        synth = SuperColliderSynth(mock_supercollider)

        synth.boot()

        mock_supercollider.boot.assert_called_once()
        assert synth.ready

    def test_boot_skips_if_sc_ready(self, mock_supercollider):
        """Test that `boot` doesn't restart SC if already ready."""
        mock_supercollider.ready = True
        synth = SuperColliderSynth(mock_supercollider)

        synth.boot()

        mock_supercollider.boot.assert_not_called()
        assert synth.ready

    def test_quit_stops_sc(self, mock_supercollider):
        """Test that `quit` stops `SuperCollider`."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.quit()

        mock_supercollider.quit.assert_called_once()
        assert not synth.ready

    @pytest.mark.parametrize(
        'method_name,args,kwargs', [
            ('note_on', (1, 60, 0.8), {}),
            ('note_off', (1, ), {}),
            ('play', ('sequence', ), {}),
            ('stop', ('sequence', ), {}),
            ('pause', ('sequence', ), {}),
            ('set_param', ('ndef.filter.freq', 1000), {}),
        ],
        ids=['note_on', 'note_off', 'play', 'stop', 'pause', 'set_param'])
    def test_methods_not_ready(self, mock_supercollider, method_name, args,
                               kwargs):
        """Test that methods raise `RuntimeError` when synth is not ready."""
        synth = SuperColliderSynth(mock_supercollider)

        method = getattr(synth, method_name)
        with pytest.raises(RuntimeError, match='not ready'):
            method(*args, **kwargs)

    def test_note_on(self, mock_supercollider):
        """Test triggering note on."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.note_on(1, 60, 0.8)

        mock_supercollider.note_on.assert_called_once_with(1, 60, 0.8)

    def test_note_off(self, mock_supercollider):
        """Test triggering note off."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.note_off(1)

        mock_supercollider.note_off.assert_called_once_with(1)

    def test_play(self, mock_supercollider):
        """Test playing Tdef sequence."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.play('sequence')

        mock_supercollider.tdef_play.assert_called_once_with('sequence')

    def test_stop(self, mock_supercollider):
        """Test stopping Tdef sequence."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.stop('sequence')

        mock_supercollider.tdef_stop.assert_called_once_with('sequence')

    def test_pause(self, mock_supercollider):
        """Test pausing Tdef sequence."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.pause('sequence')

        mock_supercollider.tdef_pause.assert_called_once_with('sequence')

    def test_unpack_param_name_ndef(self):
        """Test unpacking Ndef parameter name."""
        result = SuperColliderSynth._unpack_param_name('ndef.filter.freq')
        assert result == ('ndef', 'filter', 'freq')

    def test_unpack_param_name_tdef(self):
        """Test unpacking Tdef parameter name."""
        result = SuperColliderSynth._unpack_param_name('tdef.sequence.tempo')
        assert result == ('tdef', 'sequence', 'tempo')

    def test_unpack_param_name_invalid_format(self):
        """Test that invalid parameter format raises error."""
        with pytest.raises(ValueError, match='must be in the format'):
            SuperColliderSynth._unpack_param_name('invalid.format')

        with pytest.raises(ValueError, match='must be in the format'):
            SuperColliderSynth._unpack_param_name('too.many.dots.here')

    def test_unpack_param_name_invalid_type(self):
        """Test that invalid definition type raises error."""
        with pytest.raises(ValueError, match='not a valid Ndef or Tdef'):
            SuperColliderSynth._unpack_param_name('invalid.name.param')

    def test_set_param_ndef(self, mock_supercollider):
        """Test setting Ndef parameter."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.set_param('ndef.filter.freq', 1000)

        mock_supercollider.ndef_set.assert_called_once_with('filter',
                                                            freq=1000)
        assert synth._params['ndef.filter.freq'] == 1000

    def test_set_param_tdef(self, mock_supercollider):
        """Test setting Tdef parameter."""
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        synth.set_param('tdef.sequence.tempo', 120)

        mock_supercollider.tdef_set.assert_called_once_with('sequence',
                                                            tempo=120)
        assert synth._params['tdef.sequence.tempo'] == 120

    def test_set_params_multiple_ndef(self, mock_supercollider):
        """Test setting multiple Ndef parameters."""
        synth = SuperColliderSynth(mock_supercollider)

        params = {'ndef.filter.freq': 1000, 'ndef.filter.res': 0.5}
        synth.set_params(params)

        # Should batch parameters for the same definition
        mock_supercollider.ndef_set.assert_called_once_with('filter',
                                                            freq=1000,
                                                            res=0.5)

    def test_set_params_multiple_definitions(self, mock_supercollider):
        """Test setting parameters for different definitions."""
        synth = SuperColliderSynth(mock_supercollider)

        params = {
            'ndef.filter.freq': 1000,
            'ndef.amp.gain': 0.5,
            'tdef.sequence.tempo': 120
        }
        synth.set_params(params)

        # Should call `ndef_set` twice (once for filter, once for amp)
        assert mock_supercollider.ndef_set.call_count == 2
        assert mock_supercollider.tdef_set.call_count == 1

    def test_set_params_mixed_types(self, mock_supercollider):
        """Test setting mix of Ndef and Tdef parameters."""
        synth = SuperColliderSynth(mock_supercollider)

        params = {
            'ndef.filter.freq': 1000,
            'tdef.sequence.tempo': 120,
            'tdef.sequence.amp': 0.8
        }
        synth.set_params(params)

        mock_supercollider.ndef_set.assert_called_once()
        # Tdef params should be batched
        mock_supercollider.tdef_set.assert_called_once_with('sequence',
                                                            tempo=120,
                                                            amp=0.8)
