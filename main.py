#!/usr/bin/env python3
"""
FFmpeg-based video silence trimming script
Detects and removes silent portions from video files, exporting to a new file.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple


def run_command(
    cmd: List[str], check: bool = True, verbose: bool = False
) -> subprocess.CompletedProcess:
    """Run command and return result."""
    if verbose:
        print(f"Running: {' '.join(cmd)}")

    try:
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check
        )
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"Error output: {e.stderr}", file=sys.stderr)
        raise


def detect_silence(
    input_file: str, threshold_db: float, min_duration: float, verbose: bool = False
) -> List[Tuple[float, float]]:
    """Detect silent segments in the input file."""
    if verbose:
        print(
            f"Detecting silence (threshold: {threshold_db}dB, min duration: {min_duration}s)..."
        )

    cmd = [
        "ffmpeg",
        "-i",
        input_file,
        "-af",
        f"silencedetect=n={threshold_db}dB:d={min_duration}",
        "-f",
        "null",
        "-",
    ]

    result = run_command(cmd, check=False, verbose=False)

    # Parse silence detection output
    silences = []
    silence_start = None

    start_pattern = re.compile(r"silence_start: ([\d.]+)")
    end_pattern = re.compile(r"silence_end: ([\d.]+)")

    for line in result.stderr.split("\n"):
        if "silencedetect" not in line:
            continue

        start_match = start_pattern.search(line)
        if start_match:
            silence_start = float(start_match.group(1))
            continue

        end_match = end_pattern.search(line)
        if end_match and silence_start is not None:
            silence_end = float(end_match.group(1))
            silences.append((silence_start, silence_end))
            silence_start = None

    print(f"Found {len(silences)} silent segments")

    return silences


def get_video_duration(input_file: str) -> float:
    """Get the duration of the video file."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        input_file,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def create_keep_segments(
    silences: List[Tuple[float, float]],
    duration: float,
    padding: float,
    verbose: bool = False,
) -> List[Tuple[float, float]]:
    """Convert silent segments to segments to keep."""
    if not silences:
        return [(0, duration)]

    keep_segments = []
    current_pos = 0

    for silence_start, silence_end in silences:
        padded_start = max(0, silence_start - padding)
        padded_end = min(duration, silence_end + padding)

        if current_pos < padded_start:
            keep_segments.append((current_pos, padded_start))

        current_pos = padded_end

    if current_pos < duration:
        keep_segments.append((current_pos, duration))

    if verbose:
        print(f"Created {len(keep_segments)} segments to keep")

    return keep_segments


def trim_video(
    input_file: str,
    output_file: str,
    keep_segments: List[Tuple[float, float]],
    verbose: bool = False,
) -> None:
    """Trim video by keeping only specified segments."""
    if not keep_segments:
        print("Error: No segments to keep. Output would be empty.")
        sys.exit(1)

    # Create temporary directory for segments
    with tempfile.TemporaryDirectory(prefix="trim_silence_") as temp_dir:
        temp_path = Path(temp_dir)

        if len(keep_segments) == 1:
            # Simple case: single segment
            start, end = keep_segments[0]
            duration = end - start

            print(f"Extracting single segment ({start:.2f}s - {end:.2f}s)...")

            cmd = [
                "ffmpeg",
                "-v",
                "info" if verbose else "warning",
                "-i",
                input_file,
                "-ss",
                str(start),
                "-t",
                str(duration),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-y",
                output_file,
            ]

            run_command(cmd, verbose=verbose)

        else:
            # Multiple segments
            print(f"Extracting {len(keep_segments)} segments...")

            segment_files = []

            for i, (start, end) in enumerate(keep_segments):
                duration = end - start
                segment_file = temp_path / f"segment_{i:04d}.ts"
                segment_files.append(segment_file)

                if verbose or (i + 1) % 10 == 0:
                    print(
                        f"  Segment {i + 1}/{len(keep_segments)}: {start:.2f}s - {end:.2f}s"
                    )

                cmd = [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    input_file,
                    "-ss",
                    str(start),
                    "-t",
                    str(duration),
                    "-c",
                    "copy",
                    "-avoid_negative_ts",
                    "make_zero",
                    "-y",
                    str(segment_file),
                ]

                try:
                    run_command(cmd, verbose=False)
                except subprocess.CalledProcessError:
                    print(
                        f"Warning: Failed to extract segment {i + 1}, retrying with re-encoding..."
                    )
                    # Retry with re-encoding
                    cmd = [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        input_file,
                        "-ss",
                        str(start),
                        "-t",
                        str(duration),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-c:a",
                        "aac",
                        "-y",
                        str(segment_file),
                    ]
                    run_command(cmd, verbose=False)

            # Create concat list
            concat_file = temp_path / "concat_list.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for segment_file in segment_files:
                    f.write(f"file '{segment_file.absolute()}'\n")

            print("Concatenating segments...")

            cmd = [
                "ffmpeg",
                "-v",
                "info" if verbose else "warning",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-y",
                output_file,
            ]

            try:
                run_command(cmd, verbose=verbose)
            except subprocess.CalledProcessError:
                print("Warning: Concat with copy failed, retrying with re-encoding...")
                cmd = [
                    "ffmpeg",
                    "-v",
                    "warning",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-y",
                    output_file,
                ]
                run_command(cmd, verbose=verbose)


def process_video(
    input_file: str,
    output_file: Optional[str] = None,
    threshold_db: float = -30,
    min_duration: float = 0.5,
    padding: float = 0.1,
    output_suffix: str = "_trimmed",
    verbose: bool = False,
) -> None:
    """Process a video file: detect silence and create trimmed output."""
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    if output_file is None:
        output_file = str(
            input_path.parent / f"{input_path.stem}{output_suffix}{input_path.suffix}"
        )

    print(f"Processing: {input_file}")
    print(f"Output: {output_file}")
    print()

    # Detect silence
    silences = detect_silence(input_file, threshold_db, min_duration, verbose)

    if not silences:
        print("No silence detected. No trimming needed.")
        print("Consider adjusting threshold (-t) or minimum duration (-d)")
        return

    # Get video duration
    try:
        duration = get_video_duration(input_file)
    except Exception as e:
        print(f"Error getting video duration: {e}")
        sys.exit(1)

    # Calculate segments to keep
    keep_segments = create_keep_segments(silences, duration, padding, verbose)

    # Calculate statistics
    total_removed = sum(end - start for start, end in silences)
    total_kept = sum(end - start for start, end in keep_segments)
    percentage = (total_removed / duration) * 100 if duration > 0 else 0

    print()
    print("Statistics:")
    print(f"  Original duration: {duration:.2f}s ({duration / 60:.1f} minutes)")
    print(f"  Silent segments detected: {len(silences)}")
    print(f"  Segments to keep: {len(keep_segments)}")
    print(f"  Time removed: {total_removed:.2f}s ({percentage:.1f}%)")
    print(f"  Final duration: {total_kept:.2f}s ({total_kept / 60:.1f} minutes)")
    print()

    # Trim video
    try:
        trim_video(input_file, output_file, keep_segments, verbose)
        print(f"\n✓ Done! Saved to: {output_file}")

        # Show file sizes
        input_size = input_path.stat().st_size / (1024 * 1024)
        output_size = Path(output_file).stat().st_size / (1024 * 1024)
        print(f"  Input size: {input_size:.1f} MB")
        print(f"  Output size: {output_size:.1f} MB")

    except Exception as e:
        print(f"\nError during trimming: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Trim silence from video files using FFmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.mp4
  %(prog)s input.mp4 -o output.mp4
  %(prog)s input.mp4 -t -35 -d 1.0 -v
  %(prog)s "ครั้งที่ 2.mp4" -o "ครั้งที่ 2 Trim.mp4"
        """,
    )

    parser.add_argument("input", help="Input video file")
    parser.add_argument("-o", "--output", help="Output video file")
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=-30,
        help="Silence threshold in dB (default: -30)",
    )
    parser.add_argument(
        "-d",
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum silence duration in seconds (default: 0.5)",
    )
    parser.add_argument(
        "-p",
        "--padding",
        type=float,
        default=0.1,
        help="Padding around silence in seconds (default: 0.1)",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="_trimmed",
        help="Output filename suffix (default: _trimmed)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Check for ffmpeg
    if not shutil.which("ffmpeg"):
        print("Error: FFmpeg not found. Please install FFmpeg.", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("ffprobe"):
        print("Error: FFprobe not found. Please install FFmpeg.", file=sys.stderr)
        sys.exit(1)

    process_video(
        input_file=args.input,
        output_file=args.output,
        threshold_db=args.threshold,
        min_duration=args.min_duration,
        padding=args.padding,
        output_suffix=args.suffix,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
