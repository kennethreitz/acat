"""acat: audio $ cat. Plays audio files, the way cat prints text."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("acat")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0"
