import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from tannhauser.sc import (SuperCollider, SuperColliderStatus,
                           SuperColliderSynth, ENV_SCPORT, ENV_PYPORT,
                           ENV_INCLUDES, ENV_DEBUG)


class TestSuperColliderStatus:
    """Test the `SuperColliderStatus` dataclass."""

    def test_create_status(self):
        """Test creating a `SuperColliderStatus` instance."""
        status = SuperColliderStatus(server_running=True,
                                     num_groups=5,
                                     num_synths=10,
                                     num_ugens=100,
                                     avg_cpu=0.15,
                                     peak_cpu=0.25,
                                     load=0.1,
                                     nominal_rate=44100.0,
                                     actual_rate=44099.8,
                                     sched_latency=0.2)

        assert status.server_running is True
        assert status.num_groups == 5
        assert status.num_synths == 10
        assert status.num_ugens == 100
        assert status.avg_cpu == 0.15
        assert status.peak_cpu == 0.25
        assert status.load == 0.1
        assert status.nominal_rate == 44100.0
        assert status.actual_rate == 44099.8
        assert status.sched_latency == 0.2


class TestSuperCollider:
    """Test the `SuperCollider` interface class."""

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_init_default_values(self, mock_udp_client):
        """Test initialization with default values."""
        sc = SuperCollider()

        assert sc.host == '127.0.0.1'
        assert sc.sc_port == 57120
        assert sc.py_port == 57121
        assert sc.boot_timeout == 15.0
        assert sc.msg_timeout == 1.0
        assert sc.include_scd_files == []
        assert not sc.ready
        mock_udp_client.assert_called_once_with('127.0.0.1', 57120)

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_init_custom_values(self, mock_udp_client):
        """Test initialization with custom values."""
        scd_files = ['file1.scd', 'file2.scd']
        sc = SuperCollider(host='192.168.1.1',
                           sc_port=57130,
                           py_port=57131,
                           boot_timeout=20.0,
                           msg_timeout=2.0,
                           include_scd_files=scd_files,
                           debug=True)

        assert sc.host == '192.168.1.1'
        assert sc.sc_port == 57130
        assert sc.py_port == 57131
        assert sc.boot_timeout == 20.0
        assert sc.msg_timeout == 2.0
        assert len(sc.include_scd_files) == 2
        assert all(isinstance(p, Path) for p in sc.include_scd_files)
        assert sc.debug is True
        assert not sc.ready
        mock_udp_client.assert_called_once_with('192.168.1.1', 57130)

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_context_manager(self, mock_udp_client):
        """Test `SuperCollider` as context manager."""
        sc = SuperCollider()
        sc.quit = Mock()

        with sc as s:
            assert s is sc

        sc.quit.assert_called_once()

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    @patch('tannhauser.sc.osc_server.ThreadingOSCUDPServer')
    def test_start_osc_server(self, mock_osc_server, mock_udp_client):
        """Test starting the OSC server."""
        sc = SuperCollider()
        mock_server_instance = Mock()
        mock_osc_server.return_value = mock_server_instance

        sc._start_osc_server()

        mock_osc_server.assert_called_once()
        assert sc._osc_server is mock_server_instance
        assert sc._osc_thread is not None
        assert sc._osc_thread.daemon is True

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    @patch('tannhauser.sc.osc_server.ThreadingOSCUDPServer')
    def test_start_osc_server_already_running(self, mock_osc_server,
                                              mock_udp_client):
        """Test starting OSC server when already running logs warning."""
        sc = SuperCollider()
        sc._osc_server = Mock()

        with patch('tannhauser.sc.logger') as mock_logger:
            sc._start_osc_server()
            mock_logger.warning.assert_called_once()

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_stop_osc_server(self, mock_udp_client):
        """Test stopping the OSC server."""
        sc = SuperCollider()
        mock_osc = Mock()
        sc._osc_server = mock_osc
        sc._osc_thread = Mock()

        sc._stop_osc_server()

        mock_osc.shutdown.assert_called_once()
        mock_osc.server_close.assert_called_once()
        assert sc._osc_server is None
        assert sc._osc_thread is None

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    @patch('tannhauser.sc.subprocess.run')
    def test_has_sclang_available(self, mock_run, mock_udp_client):
        """Test checking if sclang is available."""
        mock_run.return_value = Mock()
        sc = SuperCollider()

        assert sc._has_sclang() is True
        mock_run.assert_called_once()

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    @patch('tannhauser.sc.subprocess.run')
    def test_has_sclang_not_available(self, mock_run, mock_udp_client):
        """Test checking if sclang is not available."""
        mock_run.side_effect = FileNotFoundError()
        sc = SuperCollider()

        assert sc._has_sclang() is False

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_on_status_callback(self, mock_udp_client):
        """Test status callback puts data in queue."""
        sc = SuperCollider()
        status_data = (1, 5, 10, 100, 0.15, 0.25, 0.1, 44100.0, 44099.8)

        sc._on_status('/status.reply', *status_data)

        assert not sc._status_queue.empty()
        assert sc._status_queue.get_nowait() == status_data

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_status_success(self, mock_udp_client):
        """Test querying status successfully."""
        sc = SuperCollider()
        status_data = (1.0, 5.0, 10.0, 100.0, 0.15, 0.25, 0.1, 44100.0,
                       44099.8, 0.2)

        # Mock the queue to return status data after `send_message` is called
        def mock_get(timeout):
            return status_data

        with patch.object(sc._status_queue, 'get', side_effect=mock_get):
            status = sc.get_status()

        assert status is not None
        assert status.server_running is True
        assert status.num_groups == 5
        assert status.num_synths == 10
        assert status.num_ugens == 100
        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/status', [])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_status_timeout(self, mock_udp_client):
        """Test status query timeout."""
        sc = SuperCollider()
        sc.msg_timeout = 0.1

        status = sc.get_status()

        assert status is None

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_is_sc_alive_true(self, mock_udp_client):
        """Test checking if SC is alive when it is."""
        sc = SuperCollider()

        # Mock the queue to return status data
        def mock_get(timeout):
            return (1.0, 5.0, 10.0, 100.0, 0.15, 0.25, 0.1, 44100.0, 44099.8,
                    0.2)

        with patch.object(sc._status_queue, 'get', side_effect=mock_get):
            assert sc._is_sc_alive() is True

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_is_sc_alive_false(self, mock_udp_client):
        """Test checking if SC is alive when it isn't."""
        sc = SuperCollider()
        sc.msg_timeout = 0.1

        assert sc._is_sc_alive() is False

    @patch('time.time')
    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_measure_rtt(self, mock_udp_client, mock_time):
        """Test measuring round-trip time."""
        sc = SuperCollider()
        sc.ready = True  # Bypass `_ensure_ready` check
        sc.msg_timeout = 0.1

        # Mock `time.time` to return increasing values. Each iteration calls it
        # twice. We simulate 0.1s delay for each of the 5 samples.
        mock_time.side_effect = [
            0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9
        ]

        # Mock `queue.get` to return immediately
        with patch.object(sc._status_queue, 'get') as mock_queue_get:
            mock_queue_get.return_value = 'status_data'  # Dummy data

            rtt = sc.measure_rtt(samples=5)

            # Expected RTT to average around 0.1s based on our mock time values
            assert rtt == pytest.approx(0.1)

            assert mock_queue_get.call_count == 5
            assert mock_udp_client.return_value.send_message.call_count == 5

    @patch('tannhauser.sc.SuperCollider.get_status')
    @patch('tannhauser.sc.SuperCollider.measure_rtt')
    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_estimate_latency(self, mock_udp_client, mock_measure_rtt,
                              mock_get_status):
        """Test estimating latency."""
        sc = SuperCollider()
        mock_get_status.return_value = SuperColliderStatus(
            server_running=True,
            num_groups=5,
            num_synths=10,
            num_ugens=100,
            avg_cpu=0.15,
            peak_cpu=0.25,
            load=0.1,
            nominal_rate=44100.0,
            actual_rate=44099.8,
            sched_latency=0.2)
        mock_measure_rtt.return_value = 0.1

        latency = sc.estimate_latency()

        assert latency == pytest.approx(0.25)
        mock_measure_rtt.assert_called_once()

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_set_env_vars(self, mock_udp_client):
        """Test setting environment variables."""
        scd_files = [Path('file1.scd'), Path('file2.scd')]
        sc = SuperCollider(sc_port=57130,
                           py_port=57131,
                           include_scd_files=scd_files,
                           debug=True)

        sc._set_env_vars()

        assert os.environ[ENV_SCPORT] == '57130'
        assert os.environ[ENV_PYPORT] == '57131'
        assert ENV_INCLUDES in os.environ
        assert 'file1.scd' in os.environ[ENV_INCLUDES]
        assert 'file2.scd' in os.environ[ENV_INCLUDES]
        assert ENV_DEBUG in os.environ

        os.environ.pop(ENV_SCPORT, None)
        os.environ.pop(ENV_PYPORT, None)
        os.environ.pop(ENV_INCLUDES, None)
        os.environ.pop(ENV_DEBUG, None)

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_set_env_vars_no_includes(self, mock_udp_client):
        """Test setting environment variables without includes."""
        sc = SuperCollider()

        # Set a dummy value to ensure it gets removed
        os.environ[ENV_INCLUDES] = 'dummy'

        sc._set_env_vars()

        assert ENV_INCLUDES not in os.environ

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_cleanup_process(self, mock_udp_client):
        """Test cleaning up sclang process."""
        sc = SuperCollider()
        mock_process = Mock()
        sc._sclang_process = mock_process

        sc._cleanup_process()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert sc._sclang_process is None

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    @patch('tannhauser.sc.psutil.process_iter')
    def test_quit_force(self, mock_process_iter, mock_udp_client):
        """Test forcefully quitting `SuperCollider`."""
        sc = SuperCollider()
        sc._stop_osc_server = Mock()
        sc._cleanup_process = Mock()

        mock_proc = Mock()
        mock_proc.info = {'pid': 1234, 'name': 'sclang', 'cmdline': ['sclang']}
        mock_process_iter.return_value = [mock_proc]

        sc.quit(force=True)

        mock_proc.kill.assert_called_once()
        sc._cleanup_process.assert_called_once()
        sc._stop_osc_server.assert_called_once()
        assert not sc.ready

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_ensure_ready_raises_when_not_ready(self, mock_udp_client):
        """Test that `_ensure_ready` raises `RuntimeError` when not booted."""
        sc = SuperCollider()
        assert not sc.ready

        with pytest.raises(RuntimeError, match='not ready'):
            sc._ensure_ready()

    @pytest.mark.parametrize('method_name,args,kwargs', [
        ('test', (), {}),
        ('scope', (), {}),
        ('freqscope', (), {}),
        ('ndef_set', ('filter', ), {
            'freq': 1000
        }),
        ('note_on', (1, 60, 0.8), {}),
        ('note_off', (1, ), {}),
        ('tdef_play', ('sequence', ), {}),
        ('tdef_stop', ('sequence', ), {}),
        ('tdef_pause', ('sequence', ), {}),
        ('tdef_set', ('sequence', ), {
            'tempo': 120
        }),
    ],
                             ids=[
                                 'test', 'scope', 'freqscope', 'ndef_set',
                                 'note_on', 'note_off', 'tdef_play',
                                 'tdef_stop', 'tdef_pause', 'tdef_set'
                             ])
    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_methods_not_ready(self, mock_udp_client, method_name, args,
                               kwargs):
        """Test that `SuperCollider` methods raise `RuntimeError` when not
        ready.
        """
        sc = SuperCollider()

        method = getattr(sc, method_name)
        with pytest.raises(RuntimeError, match='not ready'):
            method(*args, **kwargs)

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_test_message(self, mock_udp_client):
        """Test sending test message."""
        sc = SuperCollider()
        sc.ready = True

        sc.test(freq=440.0, amp=0.2, dur=1.0)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/test', [440.0, 0.2, 1.0])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_scope_message(self, mock_udp_client):
        """Test sending scope message."""
        sc = SuperCollider()
        sc.ready = True

        sc.scope(num_channels=2)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/scope', [2])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_freqscope_message(self, mock_udp_client):
        """Test sending freqscope message."""
        sc = SuperCollider()
        sc.ready = True

        sc.freqscope(num_channels=2)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/freqscope', [2])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_ndef_set_single_param(self, mock_udp_client):
        """Test setting single Ndef parameter."""
        sc = SuperCollider()
        sc.ready = True

        sc.ndef_set('filter', freq=1000)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/ndef/set', ['filter', 'freq', 1000.0])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_ndef_set_multiple_params(self, mock_udp_client):
        """Test setting multiple Ndef parameters."""
        sc = SuperCollider()
        sc.ready = True

        sc.ndef_set('filter', freq=1000, res=0.5)

        args = mock_udp_client.return_value.send_message.call_args[0][1]
        assert args[0] == 'filter'
        assert 'freq' in args
        assert 1000.0 in args
        assert 'res' in args
        assert 0.5 in args

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_note_on(self, mock_udp_client):
        """Test sending note on message."""
        sc = SuperCollider()
        sc.ready = True

        sc.note_on(1, 60, 0.8)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/note/on', [1, 60.0, 0.8])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_note_on_fractional_midi(self, mock_udp_client):
        """Test sending note on with fractional MIDI note."""
        sc = SuperCollider()
        sc.ready = True

        sc.note_on(1, 60.5, 0.8)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/note/on', [1, 60.5, 0.8])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_note_off(self, mock_udp_client):
        """Test sending note off message."""
        sc = SuperCollider()
        sc.ready = True

        sc.note_off(1)

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/note/off', [1])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_tdef_play(self, mock_udp_client):
        """Test sending Tdef play message."""
        sc = SuperCollider()
        sc.ready = True

        sc.tdef_play('sequence')

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/tdef/play', ['sequence'])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_tdef_stop(self, mock_udp_client):
        """Test sending Tdef stop message."""
        sc = SuperCollider()
        sc.ready = True

        sc.tdef_stop('sequence')

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/tdef/stop', ['sequence'])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_tdef_pause(self, mock_udp_client):
        """Test sending Tdef pause message."""
        sc = SuperCollider()
        sc.ready = True

        sc.tdef_pause('sequence')

        mock_udp_client.return_value.send_message.assert_called_once_with(
            '/tdef/pause', ['sequence'])

    @patch('tannhauser.sc.udp_client.SimpleUDPClient')
    def test_tdef_set(self, mock_udp_client):
        """Test setting Tdef parameters."""
        sc = SuperCollider()
        sc.ready = True

        sc.tdef_set('sequence', tempo=120, amp=0.8)

        args = mock_udp_client.return_value.send_message.call_args[0][1]
        assert args[0] == 'sequence'
        assert 'tempo' in args
        assert 120.0 in args
        assert 'amp' in args
        assert 0.8 in args


class TestSuperColliderSynth:
    """Test the `SuperColliderSynth` class."""

    def test_init(self, mock_supercollider):
        """Test initialization with `SuperCollider` instance."""
        synth = SuperColliderSynth(mock_supercollider)
        assert synth.sc is mock_supercollider

    def test_from_scd_files(self):
        """Test creating synth from SCD files."""
        with patch('tannhauser.sc.SuperCollider') as mock_sc_class:
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

    def test_piano_ui_method_signature(self, mock_supercollider):
        """Test that `piano_ui` method has correct signature and returns a
        `PianoUIController` instance bound to this synth.
        """
        synth = SuperColliderSynth(mock_supercollider)
        synth.boot()

        # Just test that the method exists and can be called with expected args
        with patch('tannhauser.controller.PianoUIController'
                   ) as mock_controller_class:
            mock_controller_instance = Mock()
            mock_controller_class.return_value = mock_controller_instance

            controller = synth.piano_ui(mod_param='filter.freq',
                                        some_kwarg=123)

            # `piano_ui` creates controller with kwargs only (no synth arg)
            mock_controller_class.assert_called_once_with(some_kwarg=123)
            # Then binds callbacks
            assert mock_controller_instance.on_press == synth.note_on
            assert mock_controller_instance.on_release == synth.note_off
            assert controller is mock_controller_instance
