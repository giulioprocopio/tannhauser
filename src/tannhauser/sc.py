from __future__ import annotations

__all__ = ['SoundEngine', 'SuperCollider']

from abc import ABC
from dataclasses import asdict, dataclass
import logging
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

import psutil
from pythonosc import dispatcher, osc_server, udp_client

from .utils import PathLike

logger = logging.getLogger(__name__)

DIR = Path(__file__).parent
DEFAULT_SC_BOOT_SCRIPT = DIR / 'sc_boot.scd'


class SoundEngine(ABC):
    pass


@dataclass
class SuperColliderStatus:
    server_running: bool  # Whether the server is running
    num_groups: int  # Number of groups on the server
    num_synths: int  # Number of synths currently running
    num_ugens: int  # Number of UGens currently in use
    avg_cpu: float  # Average CPU usage by SC (fraction)
    peak_cpu: float  # Peak CPU usage (fraction)
    load: float  # Server load (fraction)
    nominal_rate: float  # Nominal audio sample rate
    actual_rate: float  # Actual audio sample rate


class SuperCollider(SoundEngine):

    def __init__(self,
                 host: str = '127.0.0.1',
                 sc_port: int = 57120,
                 py_port: int = 57121,
                 sc_boot_script: PathLike = DEFAULT_SC_BOOT_SCRIPT,
                 boot_timeout: float = 15,
                 msg_timeout: float = 1.0,
                 include_scd_files: list[PathLike] | None = None):
        self.host = host
        self.sc_port = sc_port
        self.py_port = py_port
        self.sc_boot_script = Path(sc_boot_script)
        self.boot_timeout = boot_timeout
        self.msg_timeout = msg_timeout
        self.include_scd_files = [Path(p) for p in include_scd_files
                                  ] if include_scd_files else []

        self._sclang_process: subprocess.Popen | None = None

        self.client = udp_client.SimpleUDPClient(host, sc_port)

        self._dispatcher = dispatcher.Dispatcher()
        self._osc_server: osc_server.ThreadingOSCUDPServer | None = None
        self._osc_thread: threading.Thread | None = None

        self._status_queue = queue.Queue()
        self._dispatcher.map('/status.reply', self._on_status)

        logger.info(f'SuperCollider interface initialized (SC port {sc_port}'
                    f', listen port {py_port})')

    def _start_osc_server(self) -> None:
        if self._osc_server is not None:
            logger.warning('OSC server already running')
            return

        try:
            self._osc_server = osc_server.ThreadingOSCUDPServer(
                (self.host, self.py_port), self._dispatcher)

            self._osc_thread = threading.Thread(
                target=self._osc_server.serve_forever,
                daemon=True,
                name='SC-OSC-server')
            self._osc_thread.start()

            logger.info(f'OSC server started on {self.host}:{self.py_port}')
        except OSError as e:
            logger.error(
                f'Failed to start OSC server on port {self.py_port}: {e}')
            raise RuntimeError(
                f'Could not bind OSC server to port {self.py_port}.'
                ' Port may be in use by another application.') from e

    def _stop_osc_server(self) -> None:
        if self._osc_server is not None:
            logger.info('Stopping OSC server')
            self._osc_server.shutdown()
            self._osc_server.server_close()
            self._osc_server = None
            self._osc_thread = None
            logger.info('OSC server stopped')

    def _have_sclang(self) -> bool:
        """Check if `sclang` is available in `PATH`."""
        try:
            subprocess.run(['sclang', '--version'],
                           check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=3.0)
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f'`sclang` not found: {e}')
            return False

    def _on_status(self, addr: str, *args) -> None:
        self._status_queue.put(args)

    def status(self) -> SuperColliderStatus | None:
        """Query SuperCollider for its current status."""
        while not self._status_queue.empty():
            self._status_queue.get_nowait()

        try:
            self.client.send_message('/status', [])
            args = self._status_queue.get(timeout=self.msg_timeout)

            # Sometimes the `pythonosc` library fails to decode mixed integer/
            # float arrays correctly, so we pass everything as float and convert
            # to integer where needed.
            status = SuperColliderStatus(server_running=bool(args[0]),
                                         num_groups=int(args[1]),
                                         num_synths=int(args[2]),
                                         num_ugens=int(args[3]),
                                         avg_cpu=args[4],
                                         peak_cpu=args[5],
                                         load=args[6],
                                         nominal_rate=args[7],
                                         actual_rate=args[8])

            logger.debug(f'Received status reply: {asdict(status)}')
            return status
        except queue.Empty:
            logger.debug('No status reply received (probably not ready)')
            return None

    def _is_sc_alive(self) -> bool:
        status = self.status()
        return status is not None and status.server_running

    def _log_sc_output(self) -> None:
        assert self._sclang_process is not None

        for line in self._sclang_process.stdout:
            logger.info(f'[SC] {line.rstrip()}')

    def _set_includes_env(self) -> None:
        if self.include_scd_files:
            includes_str = ';'.join(
                str(p.absolute()) for p in self.include_scd_files)
            os.environ['TNHSR_INCLUDES'] = includes_str
            logger.info(f'Including {len(self.include_scd_files)} SCD file(s)')
        else:
            logger.info('No additional SCD files to include')
            os.environ.pop('TNHSR_INCLUDES', None)

    def boot(self) -> SuperCollider:
        """Boot SuperCollider if not already running."""
        self._start_osc_server()

        if self._is_sc_alive():
            logger.info('SuperCollider is already running')
            return

        if not self.sc_boot_script:
            raise RuntimeError(
                'SuperCollider is not running and no boot script provided')

        if not self.sc_boot_script.is_file():
            raise FileNotFoundError(
                f'Boot script not found: {self.sc_boot_script}')

        if not self._have_sclang():
            raise RuntimeError(
                '`sclang` is not available in `PATH`. Please install'
                ' SuperCollider and ensure sclang is accessible.')

        logger.info(
            f'Booting SuperCollider with script: {self.sc_boot_script}')

        self._set_includes_env()

        try:
            self._sclang_process = subprocess.Popen(
                ['sclang', str(self.sc_boot_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1)

            logger.info(f'sclang started (PID: {self._sclang_process.pid})')

            output_thread = threading.Thread(target=self._log_sc_output,
                                             daemon=True)
            output_thread.start()
        except Exception as e:
            logger.error(f'Failed to start `sclang` process: {e}')
            raise RuntimeError(f'Could not start `sclang`: {e}') from e

        start = time.time()
        while time.time() - start < self.boot_timeout:
            if self._is_sc_alive():
                logger.info('SuperCollider booted successfully')
                # Allow using this method inside a `with` statement for
                # automatic cleanup on failure
                return self
            time.sleep(0.5)

        logger.error('SuperCollider failed to boot within timeout')
        self._cleanup_process()
        raise RuntimeError(
            f'SuperCollider failed to boot within {self.boot_timeout} seconds.'
            ' Check that the boot script is correct and SC is properly'
            ' installed.')

    def _cleanup_process(self) -> None:
        if self._sclang_process:
            try:
                self._sclang_process.terminate()
                self._sclang_process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._sclang_process.kill()

            self._sclang_process = None

    def quit(self, force: bool = False) -> None:
        """Quit SuperCollider gracefully and forcefully if needed."""
        logger.info('Shutting down SuperCollider')

        if not force:
            # Try graceful shutdown via OSC
            try:
                self.client.send_message('/quit', [])
                logger.debug('Sent quit message to SuperCollider')

                # Wait briefly for graceful shutdown
                if self._sclang_process:
                    try:
                        # Assume quit times is similar to boot timeout.
                        self._sclang_process.wait(timeout=self.boot_timeout)
                        logger.info('SuperCollider shut down gracefully')
                    except subprocess.TimeoutExpired:
                        logger.warning(
                            'SuperCollider did not respond to quit, forcing'
                            ' shutdown')
                        force = True
            except Exception as e:
                logger.warning(f'Error sending quit message: {e}')
                force = True

        if force:
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'sclang' in proc.info['name'] or (
                            proc.info['cmdline']
                            and 'sclang' in proc.info['cmdline'][0]):
                        proc.kill()
                        killed_count += 1
                        logger.debug(
                            f'Killed sclang process (PID: {proc.pid})')
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f'Could not kill process: {e}')

            logger.info(f'Forcefully killed {killed_count} sclang process(es)')

        self._cleanup_process()
        self._stop_osc_server()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return self

    def test(self,
             freq: float = 440.0,
             amp: float = 0.2,
             dur: float = 1.0) -> None:
        """Play a simple sample sine synth on the SC server."""
        self.client.send_message(
            '/test',
            [float(freq), float(amp), float(dur)])

    def scope(self, num_channels: int = 2) -> None:
        """Open SuperCollider scope window."""
        self.client.send_message('/scope', [float(num_channels)])

    def freqscope(self, num_channels: int = 2) -> None:
        """Open the SuperCollider frequency scope window."""
        self.client.send_message('/freqscope', [float(num_channels)])
