#!/usr/bin/env python3
"""
claude-speak: A CLI tool for high-quality text-to-speech.
Designed for Claude to vocalize its thoughts using MLX-Audio on Apple Silicon.
"""

import argparse
import sys
import subprocess
import os


VOICES = {
    # American English Female
    "af_heart": "Warm, friendly female voice",
    "af_bella": "Clear, professional female voice",
    "af_nova": "Energetic female voice",
    "af_sky": "Light, airy female voice",
    # American English Male
    "am_adam": "Deep, authoritative male voice",
    "am_echo": "Smooth male voice",
    # British English
    "bf_alice": "British female voice",
    "bf_emma": "British female voice",
    "bm_daniel": "British male voice",
    "bm_george": "British male voice",
}

DEFAULT_VOICE = "bm_george"
DEFAULT_MODEL = "mlx-community/Kokoro-82M-bf16"


def speak(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    output: str | None = None,
    model: str = DEFAULT_MODEL,
) -> bool:
    """Generate and play speech from text using MLX-Audio."""
    cmd = [
        sys.executable, "-m", "mlx_audio.tts.generate",
        "--model", model,
        "--text", text,
        "--voice", voice,
        "--speed", str(speed),
    ]

    if output:
        cmd.extend(["--file_prefix", output.replace(".wav", "")])
    else:
        cmd.append("--play")

    # Run in the directory where the venv is
    env = os.environ.copy()

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            env=env,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating speech: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: mlx_audio not found. Run: pip install mlx-audio", file=sys.stderr)
        return False


def list_voices():
    """List available voices."""
    print("Available voices:\n")
    print("American English Female:")
    for v in ["af_heart", "af_bella", "af_nova", "af_sky"]:
        print(f"  {v:12} - {VOICES[v]}")
    print("\nAmerican English Male:")
    for v in ["am_adam", "am_echo"]:
        print(f"  {v:12} - {VOICES[v]}")
    print("\nBritish English:")
    for v in ["bf_alice", "bf_emma", "bm_daniel", "bm_george"]:
        print(f"  {v:12} - {VOICES[v]}")


def main():
    parser = argparse.ArgumentParser(
        description="High-quality text-to-speech CLI using MLX-Audio",
        epilog="Example: claude-speak 'Hello, I am thinking out loud.'"
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to speak (or pipe via stdin)"
    )
    parser.add_argument(
        "-v", "--voice",
        default=DEFAULT_VOICE,
        help=f"Voice preset (default: {DEFAULT_VOICE}). Use --list-voices for options."
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=1.0,
        help="Speech speed multiplier (default: 1.0)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save to WAV file instead of playing"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"MLX model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices"
    )

    args = parser.parse_args()

    if args.list_voices:
        list_voices()
        return 0

    # Get text from argument or stdin
    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        parser.print_help()
        return 1

    if not text:
        print("Error: No text provided", file=sys.stderr)
        return 1

    success = speak(
        text,
        voice=args.voice,
        speed=args.speed,
        output=args.output,
        model=args.model,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
