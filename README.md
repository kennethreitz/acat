<div align="center">

# acat

**`cat` prints files. `acat` plays them.**

Audio and video in your terminal, for humans.

</div>

```console
$ acat song.mp3
  ▶ 1:42 / 3:58  ███████████████████░░░░░░░░░░░░░░░░░░░░░  vol 100%
  [←/→] ∓5s  [a/d] ∓30s  [space] pause  [↑/↓] volume  [n] next  [p] prev  [q] quit
```

## Install

```console
$ uv tool install acat-player
```

Or `pipx install acat-player`. The command is `acat`.

acat uses [ffmpeg](https://ffmpeg.org) for the player and for video
(`brew install ffmpeg`, `apt install ffmpeg`).

## Usage

```console
$ acat song.mp3                          # play a file
$ acat talk.mp4                          # videos play their audio track
$ acat intro.wav verse.mp3 outro.flac    # one after another, like cat
$ curl -s https://example.com/beep.wav | acat
$ acat -q song.mp3                       # no bar, no controls, just sound
```

Anything ffmpeg can read works: mp3, wav, flac, m4a, ogg, mp4, mov, mkv,
webm, avi, and friends.

## Controls

| Key | Does |
| --- | --- |
| `space` | pause / resume |
| `←` `→` | back / forward 5s |
| `a` `d` | back / forward 30s |
| `↑` `↓` | volume |
| `n` `p` | next / previous file |
| `q` | quit |

When piped, quiet, or without ffmpeg, acat falls back to a player you
already have (`afplay`, `ffplay`, `mpv`, `paplay`, or `aplay`) and just plays.

## Development

```console
$ uv run pytest
```

## License

ISC. Made for humans, and their ears.
