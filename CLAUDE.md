# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Govassist automates the downloading, audio extraction, and transcription of video recordings from public meetings (city council sessions). It scrapes video links from meeting archives, extracts audio tracks, and uses OpenAI Whisper for speech-to-text conversion.

**Core workflow**: Web scraping → Video download → Audio extraction → Transcription → Cleanup

## Common Commands

### Setup and Installation

```bash
# Initial setup
pip install -r requirements.txt

# FFmpeg is required (system dependency)
# macOS: brew install ffmpeg
# Ubuntu/Debian: sudo apt-get install ffmpeg
# Windows: Download from ffmpeg.org
```

**Critical dependency note**: The project uses `openai-whisper` (not the `whisper` package). If you encounter `AttributeError: module 'whisper' has no attribute 'load_model'`, run:
```bash
pip uninstall whisper
pip install openai-whisper
```

### Running the Application

```bash
# Run the full transcription pipeline
python main.py
```

This processes 5 pages of meeting archives (configurable in `main.py:187`), downloading videos from the configured `BASE_URL` and `VIDEO_DOMAIN`.

### Development with DevContainer

The `.devcontainer/devcontainer.json` is configured for Python 3 with automatic FFmpeg installation and virtual environment activation.

## Architecture and Code Structure

### Single-File Architecture

The entire application is contained in `main.py` with a clear sequential workflow:

1. **Scraping (`process_page`)**: Fetches HTML from municode meeting pages, extracts video links using BeautifulSoup
2. **Download (`download_file`)**: Streams video files from storage domain
3. **Audio Extraction (`extract_audio_func`)**: Uses moviepy to extract MP3 audio (192k bitrate)
4. **Transcription (`transcribe_audio`)**: Uses Whisper "base" model with fp16=False for compatibility
5. **Cleanup**: Removes large video files after processing, retains audio and transcriptions

### Key Design Patterns

- **Incremental processing**: Each function checks if output files exist before processing (idempotent)
- **Resource management**: Uses context managers (`with` statements) for VideoFileClip to ensure proper file handle cleanup
- **Diagnostic tooling**: Lines 10-29 in `main.py` include a diagnostic block that validates the correct Whisper library is installed
- **Logging**: Structured logging with timestamps throughout the pipeline (see line 34-38)

### Output Structure

- `mp4_downloads/`: Temporary video storage (cleaned up after processing)
- `audio_extracts/`: Extracted MP3 files (192k bitrate, retained)
- `transcriptions/`: Final text transcriptions with sanitized filenames

### Configuration Points

- `BASE_URL` (line 47): Municode meeting archive URL template with `{}` page number placeholder
- `VIDEO_DOMAIN` (line 48): Video storage domain for link filtering
- `total_pages` (line 187): Number of archive pages to process
- Whisper model size (line 111): Currently "base", can upgrade to "small", "medium", or "large" for accuracy

## GitHub Actions Automation

`.github/workflows/transcribe.yml` runs the pipeline automatically:
- **Schedule**: Monthly on the 1st at midnight UTC (`0 0 1 * *`)
- **Manual trigger**: Available via workflow_dispatch
- **Auto-commit**: Commits new transcriptions back to the repository using github-actions bot
- **Python version**: Pinned to 3.11 for compatibility

## Python Version

Use Python 3.11 as specified in the GitHub Actions workflow and devcontainer configuration.

## Troubleshooting

### Whisper AttributeError
The diagnostic block at the start of `main.py` will identify if the wrong whisper package is installed. Follow the printed instructions to fix.

### MoviePy/FFmpeg Errors
Ensure FFmpeg is installed and available in your system PATH. The error handling in `extract_audio_func` (line 92-96) provides diagnostic messages.

### Empty Audio Files
If videos have no audio track, a warning is logged (line 92) and processing continues.
