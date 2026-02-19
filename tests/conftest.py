"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_synth():
    """Create a mock synth for testing controllers."""
    synth = Mock()
    synth.note_on = Mock()
    synth.note_off = Mock()
    synth.set_param = Mock()
    synth.ready = True
    return synth


@pytest.fixture
def mock_supercollider():
    """Create a mock `SuperCollider` instance for testing."""
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
