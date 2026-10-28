import shutil
import subprocess
from pathlib import Path

import pytest

import video_audio_swap as vas

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_video(path: Path, seconds: int = 2) -> Path:
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=25:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True)
    return path


def make_audio(path: Path, seconds: int = 3) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=220:duration={seconds}", str(path)], check=True)
    return path


def test_extract_wav(tmp_path):
    video = make_video(tmp_path / "clip.mp4")
    wav = vas.extract(video)
    info = vas.probe(wav)
    assert wav.exists() and info["streams"][0]["codec_name"] == "pcm_s24le"


def test_replace_copies_video_stream(tmp_path):
    video = make_video(tmp_path / "clip.mp4")
    audio = make_audio(tmp_path / "inst.wav")
    out = vas.replace(video, audio)
    info = vas.probe(out)
    kinds = sorted(s["codec_type"] for s in info["streams"])
    assert kinds == ["audio", "video"]
    vcodec = next(s for s in info["streams"] if s["codec_type"] == "video")["codec_name"]
    assert vcodec == "h264"                                  # copied, not re-encoded
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.15)  # -shortest


def test_replace_keep_original(tmp_path):
    video = make_video(tmp_path / "clip.mp4")
    audio = make_audio(tmp_path / "inst.wav")
    out = vas.replace(video, audio, tmp_path / "mixed.mp4", keep_original=True)
    assert vas.has_stream(vas.probe(out), "audio")


def test_missing_audio_stream_errors(tmp_path):
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=1",
                    "-pix_fmt", "yuv420p", str(silent)], check=True)
    with pytest.raises(vas.SwapError):
        vas.extract(silent)


def test_cli_info(tmp_path, capsys):
    video = make_video(tmp_path / "clip.mp4")
    assert vas.main(["info", str(video)]) == 0
    assert "video  h264" in capsys.readouterr().out
