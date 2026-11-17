# AGENTS.md

This file provides guidance to AI coding agents (including Google Antigravity) when working with code in this repository.

## Project Overview

Govassist automates the collection and transcription of public meeting records (Youngsville City Council sessions) across two main pipelines:

1. **Audio & Video Transcription (`main.py`)**: Fetches the meeting recording playlist from the `sheenomo.live` archive embed, downloads meeting audio directly (or extracts audio from MP4 video via `moviepy` as a fallback), and transcribes recordings to text using OpenAI Whisper.
2. **Meeting Document Scraper (`scrape.py`)**: Scrapes `HTML Agenda` and `HTML Packet` documents from the Municode meeting archive, saves cleaned text files to `meeting_documents/`, and combines them into `notebooklm_source.txt`.

## Common Commands

### Setup and Installation

```bash
# Install Python dependencies (Python 3.11 recommended)
pip install -r requirements.txt

# FFmpeg is required as a system dependency for Whisper and MoviePy
# macOS: brew install ffmpeg
# Ubuntu/Debian: sudo apt-get install ffmpeg
# Windows: Download from ffmpeg.org and add to PATH
```

**Critical dependency note**: The project uses `openai-whisper` (not the PyPI `whisper` package). If you encounter `AttributeError: module 'whisper' has no attribute 'load_model'`, run:
```bash
pip uninstall whisper
pip install openai-whisper
```

### Running the Pipelines

```bash
# Run the meeting audio download & Whisper transcription pipeline
python main.py

# Run the Municode agenda/packet scraper and generate notebooklm_source.txt
python scrape.py
```

### Development with DevContainer

`.devcontainer/devcontainer.json` is configured for Python 3 with automatic FFmpeg installation and virtual environment activation.

## Architecture and Code Structure

### 1. Transcription Pipeline (`main.py`)

Sequential workflow orchestrated by `process_meetings()`:
1. **Playlist Fetch (`fetch_playlist`)**: Fetches `ARCHIVE_EMBED_URL` (`cache.stl.sheenomo.live`) and extracts the `_SCIO.config.playerSetup.originalPlaylist` JSON array.
2. **Filename Normalization (`make_filename_from_playlist_entry`)**: Parses `pubdate_formatted`, `pubtime_formatted`, and `title` into sanitized ISO-8601-prefixed filenames.
3. **Download & Audio Extraction (`download_file`, `extract_audio_func`)**: Downloads MP3 directly via `audioDownloadURL` when available; falls back to downloading `videoDownloadURL` to `mp4_downloads/`, extracting MP3 (192k bitrate) with `moviepy`, and deleting the temporary MP4.
4. **Transcription (`transcribe_audio`)**: Runs Whisper (`"base"` model, `fp16=False`) on the audio file in `audio_extracts/` and writes the transcript to `transcriptions/`.

**Key design patterns**:
- **Idempotent / incremental processing**: Skips meetings whose final `.txt` transcription already exists in `transcriptions/`.
- **Diagnostic startup check**: Validates at import time (`main.py:16-31`) that `openai-whisper` (with `whisper.load_model`) is installed rather than the incompatible `whisper` package.

### 2. Document Scraper (`scrape.py`)

Sequential workflow orchestrated by `main()`:
1. Iterates through `TOTAL_PAGES` (4 pages) of the Municode archive (`BASE_URL`).
2. Finds `adaHtmlDocument` links whose image alt text starts with `"HTML Agenda"` or `"HTML Packet"`.
3. Extracts clean text via BeautifulSoup (stripping `script`, `style`, `nav`, `footer`, `header`), formats meeting dates in ISO 8601, and writes individual files to `meeting_documents/`.
4. Combines all scraped documents into `notebooklm_source.txt`.

### Output Directories & Files

- `mp4_downloads/`: Temporary video storage (cleaned up after audio extraction)
- `audio_extracts/`: Downloaded or extracted MP3 files
- `transcriptions/`: Final Whisper text transcriptions
- `meeting_documents/`: Individual scraped HTML Agenda and HTML Packet text files
- `notebooklm_source.txt`: Combined meeting documents formatted for NotebookLM

## GitHub Actions Automation

- `.github/workflows/transcribe.yml`: Runs `main.py` on a schedule (monthly on the 1st at midnight UTC) or manual trigger (`workflow_dispatch`) and auto-commits new transcriptions.
- `.github/workflows/scrape_meetings.yml`: Automates running `scrape.py` to update scraped meeting documents.
