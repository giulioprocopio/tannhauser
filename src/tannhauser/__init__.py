import sys

if not sys.version_info >= (3, 11):
    raise RuntimeError('Python 3.11 or higher is required')

__all__: list[str] = []

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('tannhauser')
except PackageNotFoundError:
    __version__ = 'unknown'
