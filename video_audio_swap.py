#!/usr/bin/env python3
"""
video-audio-swap
================

Two everyday jobs around music videos, done with ffmpeg and without re-encoding
the picture:

  extract  -- pull the soundtrack out of a video as lossless WAV/FLAC
              (ready for vocal removal or stem separation)
  replace  -- put a new soundtrack (e.g. an instrumental) back into the video,
              copying the video stream untouched so there is no quality loss
  info     -- show the streams of a file

Only the Python standard library is used; ffmpeg/ffprobe must be on PATH.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

__version__ = "1.0.0"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


class SwapError(RuntimeError):
    pass


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SwapError(f"{name} not found. Install ffmpeg (https://ffmpeg.org) and make sure it is on your PATH.")
    return path


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SwapError(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "ffmpeg failed")
    return proc


def probe(path: Path) -> dict:
    """Return ffprobe's JSON description of a media file."""
    out = _run([_tool("ffprobe"), "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path)]).stdout
    return json.loads(out)


def has_stream(info: dict, kind: str) -> bool:
    return any(s.get("codec_type") == kind for s in info.get("streams", []))


def extract(video: Path, dst: Path | None = None, fmt: str = "wav", sample_rate: int | None = None,
            stream: int = 0) -> Path:
    """Extract an audio stream from a video as WAV (24-bit) or FLAC."""
    info = probe(video)
    if not has_stream(info, "audio"):
        raise SwapError(f"{video} has no audio stream")
    dst = dst or video.with_name(f"{video.stem}_audio.{fmt}")
    codec = ["-c:a", "pcm_s24le"] if fmt == "wav" else ["-c:a", "flac"]
    cmd = [_tool("ffmpeg"), "-y", "-v", "error", "-i", str(video), "-map", f"0:a:{stream}", "-vn", *codec]
    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    _run(cmd + [str(dst)])
    return dst


def replace(video: Path, audio: Path, dst: Path | None = None, offset: float = 0.0,
            keep_original: bool = False, original_gain_db: float = -18.0,
            audio_codec: str = "aac", bitrate: str = "320k") -> Path:
    """Replace (or underlay) a video's soundtrack. The video stream is copied, never re-encoded."""
    vinfo = probe(video)
    if not has_stream(vinfo, "video"):
        raise SwapError(f"{video} has no video stream")
    if not has_stream(probe(audio), "audio"):
        raise SwapError(f"{audio} has no audio stream")
    dst = dst or video.with_name(f"{video.stem}_swapped{video.suffix if video.suffix.lower() != '.avi' else '.mp4'}")

    cmd = [_tool("ffmpeg"), "-y", "-v", "error", "-i", str(video)]
    if offset:
        cmd += ["-itsoffset", f"{offset}"]
    cmd += ["-i", str(audio)]

    if keep_original and has_stream(vinfo, "audio"):
        # Mix the new audio with a quiet copy of the original (e.g. to keep crowd noise).
        filt = (f"[0:a:0]volume={original_gain_db}dB[orig];"
                f"[1:a:0][orig]amix=inputs=2:duration=first:normalize=0[aout]")
        cmd += ["-filter_complex", filt, "-map", "0:v:0", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]

    if dst.suffix.lower() == ".webm":
        audio_codec = "libopus"
    cmd += ["-c:v", "copy", "-c:a", audio_codec, "-b:a", bitrate, "-shortest"]
    if dst.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        cmd += ["-movflags", "+faststart"]
    _run(cmd + [str(dst)])
    return dst


def _duration(info: dict) -> str:
    try:
        seconds = float(info["format"]["duration"])
    except (KeyError, ValueError):
        return "?"
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:05.2f}"


def cmd_info(args) -> None:
    for path in args.files:
        info = probe(path)
        print(f"{path}  ({_duration(info)})")
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                print(f"  video  {s.get('codec_name')}  {s.get('width')}x{s.get('height')}  {s.get('r_frame_rate')} fps")
            elif s.get("codec_type") == "audio":
                print(f"  audio  {s.get('codec_name')}  {s.get('sample_rate')} Hz  {s.get('channels')} ch")


def cmd_extract(args) -> None:
    files = []
    for p in args.inputs:
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXT) if p.is_dir() else [p]
    for video in files:
        dst = None
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            dst = args.out_dir / f"{video.stem}_audio.{args.format}"
        print(f"{video} -> {extract(video, dst, args.format, args.sample_rate, args.stream)}")


def cmd_replace(args) -> None:
    dst = replace(args.video, args.audio, args.output, args.offset, args.keep_original,
                  args.original_gain, bitrate=args.bitrate)
    print(f"{args.video} + {args.audio} -> {dst}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="video_audio_swap", description="Extract and replace video soundtracks losslessly with ffmpeg.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("info", help="show streams of media files")
    i.add_argument("files", nargs="+", type=Path)
    i.set_defaults(func=cmd_info)

    e = sub.add_parser("extract", help="extract audio from videos (files or folders)")
    e.add_argument("inputs", nargs="+", type=Path)
    e.add_argument("-o", "--out-dir", type=Path)
    e.add_argument("-f", "--format", choices=["wav", "flac"], default="wav")
    e.add_argument("--sample-rate", type=int, help="resample, e.g. 44100")
    e.add_argument("--stream", type=int, default=0, help="audio stream index (default: 0)")
    e.set_defaults(func=cmd_extract)

    r = sub.add_parser("replace", help="put a new soundtrack into a video")
    r.add_argument("video", type=Path)
    r.add_argument("audio", type=Path)
    r.add_argument("-o", "--output", type=Path)
    r.add_argument("--offset", type=float, default=0.0, help="delay the new audio by N seconds (negative = earlier)")
    r.add_argument("--keep-original", action="store_true", help="mix in a quiet copy of the original audio")
    r.add_argument("--original-gain", type=float, default=-18.0, help="level of the original audio in dB (default: -18)")
    r.add_argument("--bitrate", default="320k")
    r.set_defaults(func=cmd_replace)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SwapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
