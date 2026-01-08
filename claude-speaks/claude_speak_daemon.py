#!/usr/bin/env python3
"""
claude-speak daemon: Keeps the TTS model loaded for instant speech generation.

Usage:
    # Start daemon
    claude-speak-daemon start

    # Stop daemon
    claude-speak-daemon stop

    # Check status
    claude-speak-daemon status
"""

import argparse
import json
import os
import queue
import signal
import socket
import sys
import tempfile
import threading
from pathlib import Path

# Socket and PID file locations
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
SOCKET_PATH = RUNTIME_DIR / "claude-speak.sock"
PID_FILE = RUNTIME_DIR / "claude-speak.pid"

DEFAULT_VOICE = "bm_george"
DEFAULT_MODEL = "mlx-community/Kokoro-82M-bf16"


class TTSDaemon:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model = None
        self.running = False
        self.server_socket = None
        # Queue for sequential request processing (prevents audio overlap)
        self.request_queue = queue.Queue()
        self.worker_thread = None

    def load_model(self):
        """Load the TTS model into memory."""
        print(f"Loading model: {self.model_name}...")

        from mlx_audio.tts.utils import load_model
        self.model = load_model(self.model_name)

        print("Model loaded and ready.")

    def generate_and_play(self, text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> dict:
        """Generate speech and stream it in real-time (low latency)."""
        try:
            import sounddevice as sd
            import numpy as np

            chunks_played = 0

            # Stream audio chunks as they're generated (24kHz for Kokoro)
            with sd.OutputStream(samplerate=24000, channels=1, dtype=np.float32) as stream:
                for result in self.model.generate(text, voice=voice, speed=speed):
                    # Convert MLX array to numpy and write directly to audio stream
                    audio_chunk = np.array(result.audio.tolist(), dtype=np.float32)
                    stream.write(audio_chunk)
                    chunks_played += 1

            if chunks_played == 0:
                return {"success": False, "error": "No audio generated"}

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _worker_loop(self):
        """Process speak requests sequentially (prevents audio overlap)."""
        while self.running:
            try:
                # Wait for request with timeout (allows clean shutdown)
                try:
                    request, response_queue = self.request_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process the speak request
                result = self.generate_and_play(
                    text=request.get("text", ""),
                    voice=request.get("voice", DEFAULT_VOICE),
                    speed=request.get("speed", 1.0),
                )

                # Send result back to the client handler
                response_queue.put(result)
                self.request_queue.task_done()

            except Exception as e:
                print(f"Worker error: {e}")

    def handle_client(self, conn: socket.socket):
        """Handle a single client connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            if not data:
                return

            request = json.loads(data.decode("utf-8").strip())

            if request.get("command") == "speak":
                # Queue the request and wait for response (sequential processing)
                response_queue = queue.Queue()
                self.request_queue.put((request, response_queue))
                # Wait for worker to process (with timeout)
                try:
                    result = response_queue.get(timeout=60.0)
                except queue.Empty:
                    result = {"success": False, "error": "Request timed out"}
            elif request.get("command") == "ping":
                result = {"success": True, "status": "ready"}
            else:
                result = {"success": False, "error": "Unknown command"}

            conn.sendall((json.dumps(result) + "\n").encode("utf-8"))

        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            try:
                conn.sendall((json.dumps(error_response) + "\n").encode("utf-8"))
            except:
                pass
        finally:
            conn.close()

    def start(self):
        """Start the daemon server."""
        # Remove old socket if exists
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        # Load the model
        self.load_model()

        # Start worker thread for sequential audio processing
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("Worker thread started.")

        # Create Unix socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(SOCKET_PATH))
        self.server_socket.listen(5)

        # Make socket accessible
        os.chmod(SOCKET_PATH, 0o600)

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        print(f"Daemon listening on {SOCKET_PATH}")

        # Handle shutdown signals
        def shutdown(signum, frame):
            print("\nShutting down...")
            self.running = False
            if self.server_socket:
                self.server_socket.close()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        # Accept connections
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    conn, _ = self.server_socket.accept()
                    # Handle in thread to allow concurrent requests
                    thread = threading.Thread(target=self.handle_client, args=(conn,))
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    continue
            except OSError:
                break

        # Cleanup
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        if PID_FILE.exists():
            PID_FILE.unlink()

        print("Daemon stopped.")


def send_command(command: dict, timeout: float = 30.0) -> dict:
    """Send a command to the daemon and get response."""
    if not SOCKET_PATH.exists():
        return {"success": False, "error": "Daemon not running"}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(SOCKET_PATH))

        sock.sendall((json.dumps(command) + "\n").encode("utf-8"))

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
        return {"success": False, "error": "No response"}

    except socket.timeout:
        return {"success": False, "error": "Request timed out"}
    except ConnectionRefusedError:
        return {"success": False, "error": "Daemon not running"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def daemon_status() -> dict:
    """Check if daemon is running and responsive."""
    if not SOCKET_PATH.exists():
        return {"running": False, "reason": "Socket not found"}

    if not PID_FILE.exists():
        return {"running": False, "reason": "PID file not found"}

    pid = int(PID_FILE.read_text().strip())

    # Check if process exists
    try:
        os.kill(pid, 0)
    except OSError:
        return {"running": False, "reason": "Process not found"}

    # Ping daemon
    result = send_command({"command": "ping"}, timeout=5.0)
    if result.get("success"):
        return {"running": True, "pid": pid, "status": result.get("status", "unknown")}

    return {"running": False, "reason": result.get("error", "Unknown")}


def stop_daemon():
    """Stop the running daemon."""
    if not PID_FILE.exists():
        print("Daemon not running (no PID file)")
        return False

    pid = int(PID_FILE.read_text().strip())

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to daemon (PID {pid})")
        return True
    except OSError as e:
        print(f"Failed to stop daemon: {e}")
        # Clean up stale files
        if PID_FILE.exists():
            PID_FILE.unlink()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="claude-speak daemon manager")
    parser.add_argument(
        "action",
        choices=["start", "stop", "status", "restart"],
        help="Action to perform"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model to load (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't daemonize)"
    )

    args = parser.parse_args()

    if args.action == "status":
        status = daemon_status()
        if status["running"]:
            print(f"Daemon is running (PID {status['pid']}, status: {status.get('status', 'unknown')})")
        else:
            print(f"Daemon is not running: {status.get('reason', 'unknown')}")
        return 0 if status["running"] else 1

    elif args.action == "stop":
        if stop_daemon():
            return 0
        return 1

    elif args.action == "restart":
        stop_daemon()
        import time
        time.sleep(1)
        # Fall through to start
        args.action = "start"

    if args.action == "start":
        status = daemon_status()
        if status["running"]:
            print(f"Daemon already running (PID {status['pid']})")
            return 1

        if args.foreground:
            # Run in foreground
            daemon = TTSDaemon(model_name=args.model)
            daemon.start()
        else:
            # Fork to background
            pid = os.fork()
            if pid > 0:
                # Parent - wait a moment then check status
                import time
                time.sleep(3)
                status = daemon_status()
                if status["running"]:
                    print(f"Daemon started (PID {status['pid']})")
                    return 0
                else:
                    print(f"Daemon failed to start: {status.get('reason', 'unknown')}")
                    return 1
            else:
                # Child - become daemon
                os.setsid()

                # Redirect stdout/stderr to log file
                log_path = RUNTIME_DIR / "claude-speak.log"
                sys.stdout = open(log_path, "a")
                sys.stderr = sys.stdout

                daemon = TTSDaemon(model_name=args.model)
                daemon.start()

    return 0


if __name__ == "__main__":
    sys.exit(main())
