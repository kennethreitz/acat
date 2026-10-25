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
