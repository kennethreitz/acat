import io
import sys
from unittest import mock

import pytest

from acat import __version__, cli

AFPLAY = ["afplay"]


@pytest.fixture
def song(tmp_path):
    p = tmp_path / "song.mp3"
    p.write_bytes(b"fake")
    return str(p)


def run_ok(*a, **k):
    return mock.Mock(returncode=0)


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_plays_files_in_order(song, tmp_path):
    other = tmp_path / "b.wav"
    other.write_bytes(b"x")
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run", side_effect=run_ok) as run:
        assert cli.main([song, str(other)]) == 0
    assert [c.args[0] for c in run.call_args_list] == [
        ["afplay", song], ["afplay", str(other)]]


def test_missing_file(capsys):
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run") as run:
        assert cli.main(["nope.mp3"]) == 1
    run.assert_not_called()
    assert "nope.mp3: No such file" in capsys.readouterr().err


def test_unplayable_file(song, capsys):
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)):
        assert cli.main([song]) == 1
    assert "could not play" in capsys.readouterr().err


def test_no_backend(song, capsys):
    with mock.patch("shutil.which", return_value=None):
        assert cli.main([song]) == 1
    assert "no audio player found" in capsys.readouterr().err


def test_ctrl_c_exits_130(song):
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run", side_effect=KeyboardInterrupt):
        assert cli.main([song]) == 130


def test_stdin_is_buffered_and_cleaned_up(monkeypatch):
    stdin = mock.Mock(buffer=io.BytesIO(b"audio bytes"))
    monkeypatch.setattr(sys, "stdin", stdin)
    seen = {}

    def fake_run(cmd, **k):
        with open(cmd[-1], "rb") as f:
            seen["data"] = f.read()
        seen["path"] = cmd[-1]
        return mock.Mock(returncode=0)

    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run", side_effect=fake_run):
        assert cli.main([]) == 0
    assert seen["data"] == b"audio bytes"
    import os
    assert not os.path.exists(seen["path"])


def test_list_backends(capsys):
    with mock.patch("shutil.which", side_effect=lambda c: c == "mpv"):
        assert cli.main(["--list-backends"]) == 0
    out = capsys.readouterr().out
    assert "mpv\tyes" in out and "afplay\tno" in out


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "clip.MP4"
    p.write_bytes(b"fake")
    return str(p)


def test_video_prefers_ffplay(video):
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("shutil.which", side_effect=lambda c: c == "ffplay"), \
         mock.patch("subprocess.run", side_effect=run_ok) as run:
        assert cli.main([video]) == 0
    cmd = run.call_args.args[0]
    assert cmd[0] == "ffplay" and "-nodisp" in cmd and cmd[-1] == video


def test_video_extracts_with_ffmpeg_and_cleans_up(video):
    import os
    calls = []

    def fake_run(cmd, **k):
        calls.append(cmd)
        return mock.Mock(returncode=0)

    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("shutil.which", side_effect=lambda c: c == "ffmpeg"), \
         mock.patch("subprocess.run", side_effect=fake_run):
        assert cli.main([video]) == 0
    assert calls[0][0] == "ffmpeg" and video in calls[0]
    wav = calls[1][-1]
    assert calls[1][0] == "afplay" and wav.endswith(".wav")
    assert not os.path.exists(wav)


def test_video_without_ffmpeg(video, capsys):
    with mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("subprocess.run") as run:
        assert cli.main([video]) == 1
    run.assert_not_called()
    assert "needs ffmpeg" in capsys.readouterr().err


# --- interactive player -------------------------------------------------

from acat import player


def test_fmt():
    assert player.fmt(0) == "0:00"
    assert player.fmt(75.9) == "1:15"
    assert player.fmt(3725) == "1:02:05"


def test_progress_line():
    line = player.progress_line(30, 60, True, 1.0, bar_w=10)
    assert "▶ 0:30 / 1:00" in line and "█████░░░░░" in line and "vol 100%" in line
    assert "⏸" in player.progress_line(0, 0, False, 0.5)
    assert "?:??" in player.progress_line(0, 0, False, 0.5)


def test_read_key_arrows():
    import os
    r, w = os.pipe()
    os.write(w, b"\x1b[C q")
    assert player.read_key(r, 0.1) == "right"
    assert player.read_key(r, 0.1) == " "
    assert player.read_key(r, 0.1) == "q"
    assert player.read_key(r, 0.01) is None
    os.close(r); os.close(w)


def test_ui_used_on_tty(song, tmp_path):
    other = str(tmp_path / "b.mp4"); open(other, "w").close()
    seen = []
    actions = iter(["next", "prev", "done", "done"])

    def fake(path):
        seen.append(path)
        return next(actions)

    with mock.patch.object(player, "available", return_value=True), \
         mock.patch.object(player, "play_interactive", side_effect=fake), \
         mock.patch.object(cli.sys, "stdin", mock.Mock(isatty=lambda: True)), \
         mock.patch.object(cli.sys, "stderr", mock.Mock(isatty=lambda: True)):
        assert cli.main([song, other]) == 0
    assert seen == [song, other, song, other]


def test_ui_quit_and_interrupt(song):
    with mock.patch.object(player, "available", return_value=True), \
         mock.patch.object(cli.sys, "stdin", mock.Mock(isatty=lambda: True)), \
         mock.patch.object(cli.sys, "stderr", mock.Mock(isatty=lambda: True)):
        with mock.patch.object(player, "play_interactive", return_value="quit"):
            assert cli.main([song, song]) == 0
        with mock.patch.object(player, "play_interactive", return_value="interrupt"):
            assert cli.main([song]) == 130


def test_quiet_skips_ui(song):
    with mock.patch.object(player, "available", return_value=True), \
         mock.patch.object(player, "play_interactive") as ui, \
         mock.patch.object(cli.sys, "stdin", mock.Mock(isatty=lambda: True)), \
         mock.patch.object(cli.sys, "stderr", mock.Mock(isatty=lambda: True)), \
         mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("subprocess.run", side_effect=run_ok):
        assert cli.main(["-q", song]) == 0
    ui.assert_not_called()


def test_controls_under_progress():
    assert player.CONTROLS == ("[←/→] ∓5s  [a/d] ∓30s  [space] pause  "
                               "[↑/↓] volume  [n] next  [p] prev  [q] quit")
    first = player.frame("BAR", True)
    assert first.index("BAR") < first.index(player.CONTROLS)
    assert "\033[1A" not in first
    assert player.frame("BAR", False).startswith("\033[1A\r\033[2K")


def test_clear_wipes_both_lines():
    assert player.CLEAR.count("\033[2K") == 2 and "\033[1A" in player.CLEAR


def test_version_flags(capsys):
    for flag in ("--version", "-V"):
        with pytest.raises(SystemExit) as e:
            cli.main([flag])
        assert e.value.code == 0
        assert capsys.readouterr().out.strip() == "acat 0.1.0"


@pytest.mark.parametrize("platform,tools,expected", [
    ("darwin", {"brew"}, "brew install ffmpeg"),
    ("darwin", set(), "https://ffmpeg.org/download.html"),
    ("linux", {"dnf"}, "sudo dnf install ffmpeg"),
    ("linux", {"apt", "dnf"}, "sudo apt install ffmpeg"),
    ("linux", set(), "https://ffmpeg.org/download.html"),
    ("win32", set(), "winget install ffmpeg"),
])
def test_ffmpeg_install_hint(platform, tools, expected):
    with mock.patch.object(cli.sys, "platform", platform), \
         mock.patch("shutil.which", side_effect=lambda c: c in tools):
        assert expected in cli.ffmpeg_install_hint()


def test_hint_on_tty_without_ffmpeg(song, capsys):
    with mock.patch.object(player, "available", return_value=False), \
         mock.patch.object(cli.sys, "stdin", mock.Mock(isatty=lambda: True)), \
         mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch.object(cli, "ffmpeg_install_hint", return_value="HINT"), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("subprocess.run", side_effect=run_ok):
        cli.sys.stderr.isatty = lambda: True
        assert cli.main([song]) == 0
        err = capsys.readouterr().err
    assert err.count("ffmpeg not found, so no progress bar or controls. HINT") == 1


def test_no_hint_when_quiet(song, capsys):
    with mock.patch.object(player, "available", return_value=False), \
         mock.patch.object(cli, "find_backend", return_value=AFPLAY), \
         mock.patch("shutil.which", return_value=None), \
         mock.patch("subprocess.run", side_effect=run_ok):
        assert cli.main(["-q", song]) == 0
    assert "ffmpeg" not in capsys.readouterr().err
