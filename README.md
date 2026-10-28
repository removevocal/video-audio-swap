# Video Audio Swap

**Extract the soundtrack from any music video, then put an instrumental back in, without re-encoding the picture.**

This is a tiny, dependency-free Python CLI around ffmpeg for the two steps every karaoke-video, cover-video and remix-video workflow needs:

1. **`extract`**: pull the audio out of an MP4, MOV, MKV, WebM or AVI as lossless WAV or FLAC.
2. **`replace`**: drop a new soundtrack (for example the instrumental) back into the video. The video stream is **copied byte-for-byte**, so there is zero quality loss and it finishes in seconds.

![python](https://img.shields.io/badge/python-3.9%2B-blue) ![ffmpeg](https://img.shields.io/badge/requires-ffmpeg-informational) ![license](https://img.shields.io/badge/license-MIT-green)

---

## The workflow

```
music_video.mp4
      │  extract
      ▼
music_video_audio.wav ──► vocal remover / stem splitter ──► instrumental.wav
                                                                  │  replace
music_video.mp4 ──────────────────────────────────────────────────┴──► karaoke_video.mp4
```

For the middle step you can use any separation tool. Our [online AI vocal remover](https://remove-vocal.com/) accepts the extracted WAV, or even the video file directly, and returns vocals, instrumental, drums, bass and more (2, 4 or 6 stems) as WAV or MP3.

## Install

```bash
git clone https://github.com/removevocal/video-audio-swap.git
cd video-audio-swap
# nothing to pip install: standard library only
ffmpeg -version   # make sure ffmpeg + ffprobe are installed
```

Get ffmpeg from [ffmpeg.org](https://ffmpeg.org/download.html), `brew install ffmpeg`, `sudo apt install ffmpeg` or `winget install ffmpeg`.

## Usage

### Inspect a file

```bash
python video_audio_swap.py info concert.mp4
# concert.mp4  (3:42.10)
#   video  h264  1920x1080  30/1 fps
#   audio  aac  48000 Hz  2 ch
```

### Extract audio

```bash
# Single file -> concert_audio.wav (24-bit PCM)
python video_audio_swap.py extract concert.mp4

# A whole folder of videos -> FLAC in ./audio
python video_audio_swap.py extract videos/ -o audio -f flac

# Resample to 44.1 kHz, take the 2nd audio track
python video_audio_swap.py extract film.mkv --sample-rate 44100 --stream 1
```

### Replace the soundtrack

```bash
# Karaoke video: original picture + instrumental -> concert_swapped.mp4
python video_audio_swap.py replace concert.mp4 instrumental.wav

# Choose the output name and nudge the audio 120 ms later to fix sync
python video_audio_swap.py replace concert.mp4 instrumental.wav -o concert_karaoke.mp4 --offset 0.12

# Keep a little of the original (crowd noise, room) under the new mix
python video_audio_swap.py replace live.mp4 instrumental.wav --keep-original --original-gain -20
```

| `replace` option | Default | Description |
|---|---|---|
| `-o, --output` | `<video>_swapped.<ext>` | Output file (`.mp4`, `.mov`, `.mkv`, `.webm`) |
| `--offset` | `0` | Shift the new audio by N seconds (negative = earlier) |
| `--keep-original` | off | Mix a quiet copy of the original audio underneath |
| `--original-gain` | `-18` | Level of that original copy in dB |
| `--bitrate` | `320k` | Audio bitrate (AAC; Opus for WebM) |

The output is trimmed to the shorter of video and audio (`-shortest`). MP4 and MOV outputs get `+faststart`, so they start playing instantly on the web.

## Use from Python

```python
from pathlib import Path
import video_audio_swap as vas

wav = vas.extract(Path("clip.mp4"))                      # clip_audio.wav
# ... separate vocals here ...
vas.replace(Path("clip.mp4"), Path("clip_instrumental.wav"), Path("clip_karaoke.mp4"))
```

## Why not just re-export from a video editor?

Re-encoding the picture costs time and quality. This tool copies the video stream as-is with `-c:v copy` and only encodes the audio. A 4K video swaps in seconds and looks identical to the source.

## Tests

```bash
pip install pytest
pytest -q   # generates test clips with ffmpeg's lavfi sources
```

## Related tools

- [`classic-vocal-remover`](https://github.com/removevocal/classic-vocal-remover): offline phase-cancellation karaoke maker
- [`stem-mixer`](https://github.com/removevocal/stem-mixer): remix separated stems into karaoke and practice tracks
- [Remove Vocal](https://remove-vocal.com/): AI vocal remover and video vocal remover in the browser

## Support

Open an issue for bugs and ideas, or email **[support@remove-vocal.com](mailto:support@remove-vocal.com)**.

## License

MIT. See [LICENSE](LICENSE). Respect copyright: only process videos and music you have the rights to use or publish.
