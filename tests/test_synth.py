import pytest

from tannhauser.synth import Synth


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
