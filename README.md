# acat

**audio $ cat.** `cat` prints files. `acat` plays them.

```console
$ acat song.mp3
$ acat intro.wav verse.mp3 outro.flac   # one after another, like cat
$ curl -s https://example.com/beep.wav | acat
```

No dependencies, no config, no fuss. acat finds a player you already have
(`afplay` on macOS, then `ffplay`, `mpv`, `paplay`, or `aplay`) and gets out of the way.

## Usage

```
acat [-q] FILE...     play files in order ('-' or no files reads stdin)
acat --list-backends  show which players acat can use
acat --version
```

Ctrl-C stops playback (exit 130). A missing or unplayable file prints an
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
