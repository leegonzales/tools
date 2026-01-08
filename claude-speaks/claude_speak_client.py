#!/usr/bin/env python3
"""
claude-speak client: Lightweight CLI that talks to the daemon.

This is the fast path - just sends text to the already-running daemon.
Falls back to direct generation if daemon isn't running.
"""

import argparse
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
SOCKET_PATH = RUNTIME_DIR / "claude-speak.sock"

DEFAULT_VOICE = "bm_george"
MAX_TEXT_LENGTH = 5000  # ~1000 words, about 2-3 minutes of speech


def speak_via_daemon(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0, timeout: float = 300.0) -> dict:
    """Send speak request to daemon."""
    if not SOCKET_PATH.exists():
        return {"success": False, "error": "daemon_not_running"}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(SOCKET_PATH))

        request = {
            "command": "speak",
            "text": text,
            "voice": voice,
            "speed": speed,
        }
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        sock.close()

        if data:
            return json.loads(data.decode("utf-8").strip())
        return {"success": False, "error": "No response from daemon"}

    except socket.timeout:
        return {"success": False, "error": "Request timed out"}
    except ConnectionRefusedError:
        return {"success": False, "error": "daemon_not_running"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Speak text using claude-speak daemon",
        epilog="Example: claude-speak-client 'Hello world'"
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to speak (or pipe via stdin)"
    )
    parser.add_argument(
        "-v", "--voice",
        default=DEFAULT_VOICE,
        help=f"Voice to use (default: {DEFAULT_VOICE})"
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=1.0,
        help="Speech speed (default: 1.0)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress output on success"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=300.0,
        help="Timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"Allow text longer than {MAX_TEXT_LENGTH} chars"
    )

    args = parser.parse_args()

    # Get text
    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        parser.print_help()
        return 1

    if not text:
        if not args.quiet:
            print("Error: No text provided", file=sys.stderr)
        return 1

    # Guard against very long text (prevents accidental massive dumps)
    if len(text) > MAX_TEXT_LENGTH and not args.force:
        print(f"Error: Text too long ({len(text)} chars, max {MAX_TEXT_LENGTH})", file=sys.stderr)
        print("Use --force to override this limit", file=sys.stderr)
        return 1

    # Try daemon first
    result = speak_via_daemon(text, voice=args.voice, speed=args.speed, timeout=args.timeout)

    if result.get("success"):
        return 0

    # If daemon not running, provide helpful message
    error = result.get("error", "Unknown error")
    if error == "daemon_not_running":
        print("Daemon not running. Start it with:", file=sys.stderr)
        print("  claude-speak-daemon start", file=sys.stderr)
        return 2
    else:
        if not args.quiet:
            print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
