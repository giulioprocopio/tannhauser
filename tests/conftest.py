import pytest
from unittest.mock import Mock
from tannhauser.synth import Synth


@pytest.fixture
def mock_supercollider():
    sc = Mock()
    sc.host = '127.0.0.1'
    sc.sc_port = 57120
    sc.py_port = 57121
    sc.ready = True
    sc.note_on = Mock()
    sc.note_off = Mock()
    sc.ndef_set = Mock()
    sc.tdef_set = Mock()
    sc.tdef_play = Mock()
    sc.tdef_stop = Mock()
    sc.tdef_pause = Mock()
    return sc


class ConcreteSynth(Synth):

    def note_on(self, note_id, midi_note, velocity=0.8):
        pass

    def note_off(self, note_id):
        pass

    def play(self, name):
        pass

    def stop(self, name):
        pass

    def set_param(self, name, value):
        self._register_param(name, value)


@pytest.fixture
def concrete_synth():
    return ConcreteSynth()


@pytest.fixture
def mock_synth():
    synth = Mock()
    synth.note_on = Mock()
    synth.note_off = Mock()
    synth.set_param = Mock()
    synth.ready = True
    return synth
