# acat

**audio $ cat.** `cat` prints files. `acat` plays them.

```console
$ acat song.mp3
$ acat intro.wav verse.mp3 outro.flac   # one after another, like cat
$ curl -s https://example.com/beep.wav | acat
$ acat talk.mp4                         # videos too: plays the audio track
```

In a terminal, acat shows a progress bar with elapsed / total time and
takes a few keys:

```
  ▶ 0:36 / 46:52  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  vol 100%
  [←/→] ∓5s  [a/d] ∓30s  [space] pause  [↑/↓] volume  [n] next  [p] prev  [q] quit
```

That mode decodes with `ffmpeg` and plays through `sounddevice`, so it
needs ffmpeg installed (`brew install ffmpeg`). Without ffmpeg, with `-q`,
or when piped (stdin or a non-terminal), acat stays plain: it finds a
player you already have (`afplay` on macOS, then `ffplay`, `mpv`,
`paplay`, or `aplay`) and gets out of the way.

Videos (mp4, mov, mkv, webm, avi, m4v, and friends) play their audio
through `ffplay` or `mpv` when present; otherwise acat extracts the audio
with `ffmpeg` to a temp file and plays that. No ffmpeg, no video.

## Usage

```
acat [-q] FILE...     play files in order (-q: no progress bar or controls) ('-' or no files reads stdin)
acat --list-backends  show which players acat can use
acat --version
```

`q` stops (exit 0); Ctrl-C stops (exit 130). A missing or unplayable file prints an
error and exits nonzero, after playing the rest.

## Install

```console
$ uv tool install .
```

## Development

```console
$ uv run pytest
```

MIT licensed. Made for humans, and their ears.
