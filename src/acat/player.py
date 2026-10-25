"""Interactive playback: progress bar, time, and keyboard controls.

Audio is decoded by ffmpeg (so anything ffmpeg reads works, video
included) and streamed into sounddevice. Seeking restarts ffmpeg at the
new offset, so memory stays flat no matter how long the file is.
"""

from __future__ import annotations

import json
import os
import queue
import select
import shutil
import subprocess
import sys
import threading

RATE = 44100
CHANNELS = 2
CHUNK = 2048  # frames per read from ffmpeg
SEEK = 5
BIG_SEEK = 30

CONTROLS = ("  [←/→] ∓5s  [a/d] ∓30s  [space] pause  [↑/↓] volume  "
            "[n] next  [p] prev  [q] quit")


def available() -> bool:
    """True if interactive playback can work here."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        import numpy  # noqa: F401
        import sounddevice  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def probe_duration(path: str) -> float:
    """Length in seconds via ffprobe, or 0.0 if unknown."""
    if not shutil.which("ffprobe"):
        return 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=10,
        ).stdout
        return float(json.loads(out)["format"]["duration"])
    except (ValueError, KeyError, subprocess.SubprocessError, OSError):
        return 0.0


def fmt(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_line(cur: float, total: float, playing: bool, volume: float,
                  bar_w: int = 40) -> str:
    pct = min(1.0, cur / total) if total > 0 else 0.0
    filled = int(pct * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)
    icon = "▶" if playing else "⏸"
    total_s = fmt(total) if total > 0 else "?:??"
    return f"  {icon} {fmt(cur)} / {total_s}  {bar}  vol {int(volume * 100)}% "


def read_key(fd: int, timeout: float) -> str | None:
    """One keypress (arrow keys become 'up'/'down'/'left'/'right')."""
    if not select.select([fd], [], [], timeout)[0]:
        return None
    ch = os.read(fd, 1).decode(errors="ignore")
    if ch != "\x1b":
        return ch
    seq = ""
    while len(seq) < 2 and select.select([fd], [], [], 0.01)[0]:
        seq += os.read(fd, 1).decode(errors="ignore")
    return {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}.get(seq, "esc")


class Stream:
    """ffmpeg → queue → sounddevice, with pause, seek, and volume."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.pos = 0  # frames played, from start of file
        self.playing = True
        self.volume = 1.0
        self.done = False
        self.proc = None
        self.q: queue.Queue = queue.Queue(maxsize=32)
        self.leftover = None

    def _spawn(self, start_frame: int) -> None:
        if self.proc:
            self.proc.kill()
            self.proc.wait()
        self.proc = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-loglevel", "error",
             "-ss", f"{start_frame / RATE:.3f}", "-i", self.path, "-vn",
             "-f", "f32le", "-ac", str(CHANNELS), "-ar", str(RATE), "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        q: queue.Queue = queue.Queue(maxsize=32)
        self.q, self.leftover, self.done = q, None, False
        threading.Thread(target=self._feed, args=(self.proc, q),
                         daemon=True).start()

    @staticmethod
    def _feed(proc, q) -> None:
        import numpy as np
        size = CHUNK * CHANNELS * 4
        while True:
            data = proc.stdout.read(size)
            if not data:
                q.put(None)
                return
            q.put(np.frombuffer(data, dtype=np.float32).reshape(-1, CHANNELS))

    def callback(self, outdata, frames, time_info, status) -> None:
        with self.lock:
            outdata[:] = 0
            if not self.playing or self.done:
                return
            filled = 0
            while filled < frames:
                block = self.leftover
                self.leftover = None
                if block is None:
                    try:
                        block = self.q.get_nowait()
                    except queue.Empty:
                        break  # decoder behind; output silence
                    if block is None:
                        self.done = True
                        break
                n = min(frames - filled, len(block))
                outdata[filled:filled + n] = block[:n] * self.volume
                if n < len(block):
                    self.leftover = block[n:]
                filled += n
            self.pos += filled

    def seek(self, seconds: float, total: float) -> None:
        with self.lock:
            target = self.pos + int(seconds * RATE)
            if total > 0:
                target = min(target, int(total * RATE))
            self.pos = max(0, target)
            self._spawn(self.pos)

    def close(self) -> None:
        if self.proc:
            self.proc.kill()
            self.proc.wait()


def play_interactive(path: str) -> str:
    """Play one file with the UI. Returns 'done', 'next', 'prev', 'quit', or 'interrupt'."""
    import sounddevice as sd
    import termios
    import tty

    total = probe_duration(path)
    s = Stream(path)
    s._spawn(0)

    print(f"\n  {os.path.basename(path)}", file=sys.stderr)
    print(CONTROLS, file=sys.stderr)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    action = "done"
    stream = sd.OutputStream(samplerate=RATE, channels=CHANNELS,
                             dtype="float32", blocksize=1024,
                             callback=s.callback)
    try:
        tty.setcbreak(fd)
        stream.start()
        while True:
            with s.lock:
                cur, playing, vol, done = (s.pos / RATE, s.playing,
                                           s.volume, s.done)
            sys.stderr.write("\r" + progress_line(cur, total, playing, vol))
            sys.stderr.flush()
            if done:
                break
            key = read_key(fd, 0.1)
            if key in ("q", "\x03"):
                action = "quit"
                break
            elif key == " ":
                with s.lock:
                    s.playing = not s.playing
            elif key in ("right", "f"):
                s.seek(SEEK, total)
            elif key in ("left", "s"):
                s.seek(-SEEK, total)
            elif key == "d":
                s.seek(BIG_SEEK, total)
            elif key == "a":
                s.seek(-BIG_SEEK, total)
            elif key in ("up", "+", "="):
                with s.lock:
                    s.volume = min(2.0, round(s.volume + 0.1, 1))
            elif key in ("down", "-"):
                with s.lock:
                    s.volume = max(0.0, round(s.volume - 0.1, 1))
            elif key == "n":
                action = "next"
                break
            elif key == "p":
                action = "prev"
                break
    except KeyboardInterrupt:
        action = "interrupt"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        stream.stop()
        stream.close()
        s.close()
        sys.stderr.write("\n")
    return action
