# FFmpeg-SkipSilence

Automatically detect and remove silent portions from video files using FFmpeg. This is a standalone tool inspired by the mpv-skipsilence script, but designed for batch processing video files.

## Features

- **Automatic Silence Detection**: Uses FFmpeg's `silencedetect` filter to identify silent portions
- **Configurable Parameters**: Adjust threshold, minimum duration, and padding
- **Batch Processing**: Process any video file format supported by FFmpeg
- **Progress Reporting**: Real-time feedback on processing status
- **Unicode Support**: Works with non-ASCII filenames (Thai, Chinese, Arabic, etc.)
- **Fallback Encoding**: Automatically re-encodes if stream copy fails
- **Statistics**: Detailed breakdown of time saved and file size reduction
- **No External Dependencies**: Only requires FFmpeg (beyond Python standard library)

## Installation

### Requirements

- Python 3.6 or higher
- FFmpeg with libx264 and AAC support
- FFprobe (comes with FFmpeg)

### Installing FFmpeg

**Arch Linux:**

```bash
sudo pacman -S ffmpeg
```

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**

```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use:

```bash
choco install ffmpeg  # using Chocolatey
```

### Setup

```bash
# Clone or download the repository
cd FFmpeg-SkipSilence

# Make the script executable (Linux/macOS)
chmod +x main.py

# Or just run it with Python
python3 main.py --help
```

## Usage

### Basic Usage

```bash
# Process a video file (output will be named with _trimmed suffix)
python3 main.py input.mp4

# Specify output filename
python3 main.py input.mp4 -o output.mp4

# Thai or Unicode filenames work fine
python3 main.py "อินพุต.mp4" -o "เอาต์พุต.mp4"
```

### Advanced Options

```bash
# Adjust silence threshold (more negative = quieter sounds detected as silence)
python3 main.py input.mp4 -t -35

# Set minimum silence duration (in seconds)
python3 main.py input.mp4 -d 1.0

# Add padding around silence (keeps a bit of silence between segments)
python3 main.py input.mp4 -p 0.2

# Verbose output showing all processing steps
python3 main.py input.mp4 -v

# Change output filename suffix
python3 main.py input.mp4 -s "_no_silence"

# All options combined
python3 main.py input.mp4 -o output.mp4 -t -40 -d 0.3 -p 0.15 -v
```

### Command Line Arguments

| Short | Long             | Default                 | Description                                               |
| ----- | ---------------- | ----------------------- | --------------------------------------------------------- |
| `-o`  | `--output`       | `{input}_trimmed.{ext}` | Output video file path                                    |
| `-t`  | `--threshold`    | `-30`                   | Silence threshold in dB (lower = quieter sounds detected) |
| `-d`  | `--min-duration` | `0.5`                   | Minimum silence duration in seconds                       |
| `-p`  | `--padding`      | `0.1`                   | Time to preserve around silence (seconds)                 |
| `-s`  | `--suffix`       | `_trimmed`              | Suffix for auto-generated output filename                 |
| `-v`  | `--verbose`      | `false`                 | Show detailed processing information                      |
| `-h`  | `--help`         | -                       | Show help message                                         |

## Examples

### Remove Long Pauses from Lecture Recording

```bash
python3 main.py lecture.mp4 -t -35 -d 2.0
```

This removes pauses longer than 2 seconds that are quieter than -35dB.

### Compress Podcast (Remove All Silence)

```bash
python3 main.py podcast.mp4 -t -25 -d 0.3 -p 0.05
```

This aggressively removes silence and adds minimal padding.

### Process Noisy Video

```bash
python3 main.py noisy_video.mp4 -t -40 -d 1.0
```

For videos with background noise, use a more negative threshold (-40 or lower).

### Batch Process Multiple Files

```bash
for file in *.mp4; do
    python3 main.py "$file" -t -30 -d 0.5
done
```

### Create Archive of Compressed Videos

```bash
mkdir -p trimmed
for file in *.mp4; do
    python3 main.py "$file" -o "trimmed/${file%.mp4}_trimmed.mp4" -v
done
```

## How It Works

### Process Flow

1. **Silence Detection**: Analyzes the audio stream using FFmpeg's `silencedetect` filter
2. **Segment Calculation**: Determines which portions of the video to keep (non-silent parts)
3. **Segment Extraction**: Extracts each non-silent segment as a separate file
4. **Concatenation**: Joins all segments into a single output video
5. **Cleanup**: Removes temporary files automatically

### Stream Copy vs Re-encoding

- **Single Segment**: Uses stream copy (very fast, no quality loss)
- **Multiple Segments**:
  - First tries stream copy concatenation (fast)
  - Falls back to re-encoding if copy fails (slower, but ensures compatibility)

### Temporary Files

The script uses Python's `tempfile` module which automatically:

- Creates isolated temporary directories
- Cleans up all files after processing completes
- Handles permission issues automatically

## Performance Tips

- **Faster Processing**:
  - Use higher `-d` values (minimum duration) to reduce number of cuts
  - Process on faster hardware for re-encoding
  - Use `-p 0` if you don't need padding around silence

- **Better Quality**:
  - Use lower `-t` values to detect more silence accurately
  - Use shorter `-d` values to catch all silent segments
  - For single-segment results, stream copy preserves original quality

- **GPU Acceleration** (if available):
  - Modify the script to use `h264_nvenc` or `h264_qsv` codecs instead of `libx264`
  - Requires NVIDIA or Intel GPU support

## Troubleshooting

### "FFmpeg not found"

Install FFmpeg (see Installation section above).

### "FFprobe not found"

FFprobe comes with FFmpeg. Reinstall FFmpeg.

### Processing is Very Slow

This is normal for videos with many short silent segments. Options:

- Increase `-d` to reduce number of cuts: `python3 main.py input.mp4 -d 1.0`
- Disable verbose output (slightly faster)
- Use a faster computer or GPU

### Audio/Video Out of Sync

Try increasing padding:

```bash
python3 main.py input.mp4 -p 0.3
```

### "Too Much Removed" or "Too Little Removed"

Adjust the threshold:

- **Too much removed**: Use less negative threshold: `-t -25` (default is `-t -30`)
- **Too little removed**: Use more negative threshold: `-t -40`

### Output File is Larger Than Input

This can happen when:

- Re-encoding at higher quality than original
- Video has high compression and re-encoding is less efficient

Solutions:

- Accept larger file size (video is higher quality)
- Re-encode with lower CRF: Edit script and change `-crf 23` to `-crf 28`
- Use different codec (e.g., VP9, HEVC)

### Memory Issues on Large Files

If you run out of RAM during processing:

- Reduce number of parallel operations (current script is sequential)
- Use a machine with more RAM
- Split input file and process separately

## Parameters Guide

### Silence Threshold (`-t`)

The threshold in dB determines what volume level counts as silence.

- **`-25`**: Aggressive (detects quiet speech, music)
- **`-30`**: Moderate (default, good for most content)
- **`-40`**: Conservative (only removes very quiet silence, good for background noise)
- **`-50`**: Very conservative (removes almost nothing)

**Tips**:

- For podcasts: `-25` to `-30`
- For lectures: `-30` to `-35`
- For music: `-40` or lower
- For noisy environments: `-40` or lower

### Minimum Duration (`-d`)

Minimum length of silence to detect and remove (in seconds).

- **`0.3`**: Remove short pauses (sensitive)
- **`0.5`**: Default, good balance
- **`1.0`**: Remove long pauses (less aggressive)
- **`2.0`**: Only remove very long pauses

**Tips**:

- Shorter durations = more cuts = slower processing
- Longer durations = faster processing, but less silence removed

### Padding (`-p`)

Time to preserve around each silent segment (in seconds).

- **`0`**: No padding (remove silence completely)
- **`0.05`**: Minimal padding (fast speech flow)
- **`0.1`**: Default (natural speech flow)
- **`0.3`**: Heavy padding (preserve more natural pauses)

## File Format Support

Works with any video format supported by FFmpeg:

- **Video Codecs**: H.264, H.265, VP8, VP9, AV1, ProRes, etc.
- **Audio Codecs**: AAC, MP3, OPUS, FLAC, etc.
- **Containers**: MP4, MKV, AVI, MOV, WebM, etc.

Note: Output will be re-encoded to H.264/AAC if stream copy fails.

## Common Issues & Solutions

**Q: How do I process videos in a specific folder?**

```bash
python3 main.py /path/to/folder/*.mp4
# For multiple files:
for file in /path/to/folder/*.mp4; do
    python3 main.py "$file"
done
```

## See Also

- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [mpv-skipsilence](https://codeberg.org/ferreum/mpv-skipsilence/) - The original inspiration
- [FFmpeg silencedetect filter](https://ffmpeg.org/ffmpeg-filters.html#silencedetect)
