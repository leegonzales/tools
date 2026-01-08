#!/usr/bin/env python3
"""Tests for claude-speak CLI and daemon."""

import json
import os
import queue
import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

import pytest


class TestClientFunctions:
    """Test client-side functions."""

    def test_speak_via_daemon_socket_not_exists(self):
        """Test client gracefully handles missing socket."""
        from claude_speak_client import speak_via_daemon

        # Use a non-existent socket path
        with mock.patch("claude_speak_client.SOCKET_PATH", Path("/tmp/nonexistent.sock")):
            result = speak_via_daemon("Hello")
            assert result["success"] is False
            assert result["error"] == "daemon_not_running"

    def test_speak_via_daemon_connection_refused(self):
        """Test client handles connection refused or socket errors."""
        from claude_speak_client import speak_via_daemon

        # Create a regular file (not a socket) to trigger connection error
        with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
            sock_path = Path(f.name)

        try:
            with mock.patch("claude_speak_client.SOCKET_PATH", sock_path):
                result = speak_via_daemon("Hello")
                assert result["success"] is False
                # Can be various errors: daemon_not_running, connection refused, or socket error
                assert result["error"] is not None
        finally:
            sock_path.unlink(missing_ok=True)


class TestDaemonFunctions:
    """Test daemon-side functions."""

    def test_daemon_status_no_socket(self):
        """Test status check with no socket file."""
        from claude_speak_daemon import daemon_status

        with mock.patch("claude_speak_daemon.SOCKET_PATH", Path("/tmp/nonexistent.sock")):
            status = daemon_status()
            assert status["running"] is False
            assert "Socket not found" in status["reason"]

    def test_daemon_status_no_pid_file(self):
        """Test status check with socket but no PID file."""
        from claude_speak_daemon import daemon_status

        with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
            sock_path = Path(f.name)

        try:
            with mock.patch("claude_speak_daemon.SOCKET_PATH", sock_path):
                with mock.patch("claude_speak_daemon.PID_FILE", Path("/tmp/nonexistent.pid")):
                    status = daemon_status()
                    assert status["running"] is False
                    assert "PID file not found" in status["reason"]
        finally:
            sock_path.unlink(missing_ok=True)


class TestProtocol:
    """Test the socket protocol."""

    def test_request_format(self):
        """Test speak request JSON format."""
        request = {
            "command": "speak",
            "text": "Hello world",
            "voice": "bm_george",
            "speed": 1.0,
        }
        encoded = json.dumps(request) + "\n"
        decoded = json.loads(encoded.strip())

        assert decoded["command"] == "speak"
        assert decoded["text"] == "Hello world"
        assert decoded["voice"] == "bm_george"
        assert decoded["speed"] == 1.0

    def test_response_format_success(self):
        """Test success response format."""
        response = {"success": True}
        encoded = json.dumps(response) + "\n"
        decoded = json.loads(encoded.strip())

        assert decoded["success"] is True

    def test_response_format_error(self):
        """Test error response format."""
        response = {"success": False, "error": "Something went wrong"}
        encoded = json.dumps(response) + "\n"
        decoded = json.loads(encoded.strip())

        assert decoded["success"] is False
        assert decoded["error"] == "Something went wrong"

    def test_ping_command(self):
        """Test ping command format."""
        request = {"command": "ping"}
        response = {"success": True, "status": "ready"}

        assert json.loads(json.dumps(request))["command"] == "ping"
        assert json.loads(json.dumps(response))["status"] == "ready"


class TestVoices:
    """Test voice configuration."""

    def test_all_voices_defined(self):
        """Test all expected voices are defined."""
        from claude_speak import VOICES

        expected_voices = [
            "af_heart", "af_bella", "af_nova", "af_sky",
            "am_adam", "am_echo",
            "bf_alice", "bf_emma", "bm_daniel", "bm_george",
        ]

        for voice in expected_voices:
            assert voice in VOICES, f"Missing voice: {voice}"

    def test_default_voice(self):
        """Test default voice is set correctly."""
        from claude_speak import DEFAULT_VOICE

        assert DEFAULT_VOICE == "bm_george"


class TestQueueWorker:
    """Test the queue-based worker pattern."""

    def test_queue_sequential_processing(self):
        """Test that requests are processed sequentially."""
        request_queue = queue.Queue()
        results = []

        def mock_worker():
            while True:
                try:
                    item, response_q = request_queue.get(timeout=0.5)
                except queue.Empty:
                    break
                results.append(item)
                response_q.put({"success": True})
                request_queue.task_done()

        # Start worker
        worker = threading.Thread(target=mock_worker)
        worker.start()

        # Queue multiple requests
        for i in range(3):
            response_q = queue.Queue()
            request_queue.put((f"request_{i}", response_q))

        # Wait for all to be processed
        request_queue.join()
        worker.join(timeout=1.0)

        # Verify order preserved
        assert results == ["request_0", "request_1", "request_2"]


class TestCLI:
    """Test CLI argument parsing."""

    def test_speak_cli_help(self):
        """Test that CLI shows help without error."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "claude_speak", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "text-to-speech" in result.stdout.lower()

    def test_client_cli_help(self):
        """Test that client CLI shows help without error."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "claude_speak_client", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0

    def test_daemon_cli_help(self):
        """Test that daemon CLI shows help without error."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "claude_speak_daemon", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "start" in result.stdout or "stop" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
