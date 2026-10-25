"""acat: like cat, but for your ears."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from . import __version__, player

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


VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv",
    ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp", ".ogv",
}

# Players that can pull the audio straight out of a video file.
VIDEO_BACKENDS = ("ffplay", "mpv")


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def video_backend() -> list[str] | None:
    """A backend that plays video audio directly, or None."""
    for name, cmd in BACKENDS:
        if name in VIDEO_BACKENDS and shutil.which(cmd[0]):
            return list(cmd)
    return None


def extract_audio(path: str) -> str | None:
    """Pull a video's audio track into a temp WAV with ffmpeg. None on failure."""
    fd, out = tempfile.mkstemp(prefix="acat-", suffix=".wav")
    os.close(fd)
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", path,
         "-vn", out],
        stdout=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        os.unlink(out)
        return None
    return out


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


def play_ui(files: list[str]) -> int:
    """Interactive mode: progress bar and controls, n/p moves between files."""
    status, i = 0, 0
    while 0 <= i < len(files):
        path = files[i]
        if not os.path.isfile(path):
            error(f"{path}: No such file")
            status = 1
            i += 1
            continue
        action = player.play_interactive(path)
        if action == "interrupt":
            return 130
        if action == "quit":
            return status
        i = max(0, i - 1) if action == "prev" else i + 1
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="acat",
        description="Play audio files in sequence, the way cat prints text.",
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="audio or video files to play ('-' or nothing reads stdin)")
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

    files = args.files or ["-"]
    if (not args.quiet and "-" not in files and sys.stdin.isatty()
            and sys.stderr.isatty() and player.available()):
        return play_ui(files)

    backend = find_backend()
    if backend is None:
        error("no audio player found. Install one of: "
              + ", ".join(name for name, _ in BACKENDS))
        return 1

    status = 0
    temps: list[str] = []
    try:
        for path in files:
            if path == "-":
                path = _stdin_to_tempfile()
                temps.append(path)
            elif not os.path.isfile(path):
                error(f"{path}: No such file")
                status = 1
                continue
            cmd = backend
            if path not in temps and is_video(path):
                direct = video_backend()
                if direct:
                    cmd = direct
                elif shutil.which("ffmpeg"):
                    extracted = extract_audio(path)
                    if extracted is None:
                        error(f"{path}: could not read audio from video")
                        status = 1
                        continue
                    temps.append(extracted)
                    path = extracted
                else:
                    error(f"{path}: playing video needs ffmpeg "
                          "(try: brew install ffmpeg)")
                    status = 1
                    continue
            if play(path, cmd, args.quiet) != 0:
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
