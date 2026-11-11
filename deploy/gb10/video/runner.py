"""Media probing and subprocess helpers for the original video pipeline."""

import json

import math

from pathlib import Path

import subprocess

def validate_probe(probe, kind, max_duration):
    streams = [item for item in probe.get("streams", []) if item.get("codec_type") == kind]
    if not streams:
        raise ValueError("Input has no " + kind + " stream")
    stream = streams[0]
    try:
        duration = float(probe.get("format", {}).get("duration", stream.get("duration", "nan")))
    except (ValueError, TypeError):
        raise ValueError("Cannot determine input duration") from None
    if not math.isfinite(duration) or not 0 < duration <= max_duration:
        raise ValueError("Input duration must be positive and at most %.1f seconds" % max_duration)
    metadata = {"duration": duration}
    if kind == "video":
        try:
            width, height = int(stream["width"]), int(stream["height"])
            rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate", "0/0")
            numerator, denominator = rate.split("/")
            fps = float(numerator) / float(denominator)
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            raise ValueError("Invalid video dimensions or frame rate") from None
        if width < 2 or height < 2 or not math.isfinite(fps) or not 0 < fps <= 240:
            raise ValueError("Invalid video dimensions or frame rate")
        metadata.update(width=width, height=height, fps=fps)
    return metadata

def run_command(arguments, timeout):
    """Never interpolate a media filename into shell code."""
    result = subprocess.run([str(arg) for arg in arguments], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace")[-3000:]
        raise RuntimeError(Path(str(arguments[0])).name + " failed: " + detail)
    return result.stdout

def probe_media(path, kind, max_duration):
    output = run_command(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                          "-of", "json", path], 30)
    return validate_probe(json.loads(output), kind, max_duration)
