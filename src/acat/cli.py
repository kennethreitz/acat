"""acat: like cat, but for your ears."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from . import __version__

# Backends in order of preference: (name, command prefix).
BACKENDS = [
    ("afplay", ["afplay"]),
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error"]),
    ("mpv", ["mpv", "--no-video", "--really-quiet"]),
    ("paplay", ["paplay"]),
    ("aplay", ["aplay", "-q"]),
]


def available_backends() -> list[str]:
    """Names of the playback backends found on this machine."""
    return [name for name, cmd in BACKENDS if shutil.which(cmd[0])]


def find_backend() -> list[str] | None:
    """The command prefix of the first available backend, or None."""
    for name, cmd in BACKENDS:
        if shutil.which(cmd[0]):
            return list(cmd)
    return None


def play(path: str, backend: list[str], quiet: bool = False) -> int:
    """Play one file. Returns the backend's exit code."""
    out = subprocess.DEVNULL if quiet else None
    return subprocess.run([*backend, path], stdout=out, stderr=out).returncode


def _stdin_to_tempfile() -> str:
    with tempfile.NamedTemporaryFile(prefix="acat-", delete=False) as f:
        shutil.copyfileobj(sys.stdin.buffer, f)
        return f.name


def error(msg: str) -> None:
    print(f"acat: {msg}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acat",
        description="Play audio files in sequence, the way cat prints text.",
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="audio files to play ('-' or nothing reads stdin)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="hide the player's own output")
    parser.add_argument("--list-backends", action="store_true",
                        help="show which players acat can use, then exit")
    parser.add_argument("--version", action="version",
                        version=f"acat {__version__}")
    args = parser.parse_args(argv)

    if args.list_backends:
        found = available_backends()
        for name, _ in BACKENDS:
            print(f"{name}\t{'yes' if name in found else 'no'}")
        return 0 if found else 1

    backend = find_backend()
    if backend is None:
        error("no audio player found. Install one of: "
              + ", ".join(name for name, _ in BACKENDS))
        return 1

    status = 0
    temps: list[str] = []
    try:
        for path in args.files or ["-"]:
            if path == "-":
                path = _stdin_to_tempfile()
                temps.append(path)
            elif not os.path.isfile(path):
                error(f"{path}: No such file")
                status = 1
                continue
            if play(path, backend, args.quiet) != 0:
                error(f"{path}: could not play")
                status = 1
    except KeyboardInterrupt:
        return 130
    finally:
        for t in temps:
            try:
                os.unlink(t)
            except OSError:
                pass
    return status


if __name__ == "__main__":
    sys.exit(main())
