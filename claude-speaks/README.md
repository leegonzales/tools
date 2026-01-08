# Claude Speaks

High-quality text-to-speech CLI for Apple Silicon using MLX-Audio and the Kokoro TTS model.

## Features

- **Instant response** - Daemon keeps model loaded in memory
- **High quality** - Kokoro 82M parameter model
- **Multiple voices** - 10 voice presets (American/British, male/female)
- **Native performance** - MLX framework optimized for Apple Silicon

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.10+ (native ARM, not Rosetta)
- espeak-ng: `brew install espeak-ng`

## Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/tools.git
cd tools/claude-speak

# Create virtual environment with native ARM Python
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Download spaCy model (required for text processing)
python -m spacy download en_core_web_sm
```

## Usage

### Quick Start

```bash
# Start the daemon (keeps model loaded)
claude-speak-daemon start

# Speak text instantly
claude-speak-client "Hello, I am Claude speaking to you."
```

### Direct Mode (No Daemon)

```bash
# Slower startup (3-5s) but no daemon needed
claude-speak "Hello world"
```

### Available Voices

| Voice | Description |
|-------|-------------|
| `bm_george` | British male, distinguished **(default)** |
| `bm_daniel` | British male, gentleman |
| `bf_emma` | British female, elegant |
| `bf_alice` | British female, refined |
| `am_adam` | American male, deep |
| `am_echo` | American male, smooth |
| `af_heart` | American female, warm |
| `af_bella` | American female, professional |
| `af_nova` | American female, energetic |
| `af_sky` | American female, airy |

### Options

```bash
# Different voice
claude-speak-client -v af_heart "Using a different voice"

# Adjust speed (0.5 = slower, 1.5 = faster)
claude-speak-client -s 1.2 "Speaking a bit faster"

# Save to file
claude-speak -o output.wav "Saving to file"
```

## Auto-Start on Login

Install the launchd service to start the daemon automatically:

```bash
cp com.claude-speak.daemon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claude-speak.daemon.plist
```

### Daemon Management

```bash
claude-speak-daemon status   # Check if running
claude-speak-daemon start    # Start daemon
claude-speak-daemon stop     # Stop daemon
claude-speak-daemon restart  # Restart daemon
```

## Architecture

```
┌─────────────────┐     Unix Socket     ┌─────────────────┐
│  claude-speak   │                     │     Daemon      │
│    -client      │ ──────────────────▶ │  (model hot)    │
│   (instant)     │                     │                 │
└─────────────────┘                     └────────┬────────┘
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │   MLX-Audio     │
                                        │  Kokoro 82M     │
                                        └─────────────────┘
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Daemon not running" | Run `claude-speak-daemon start` |
| Python architecture mismatch | Use `/opt/homebrew/bin/python3` not system Python |
| espeak errors | Install with `brew install espeak-ng` |
| No audio output | Check macOS sound settings |

## License

MIT
