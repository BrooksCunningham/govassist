
# Govassist

Govassist is a utility designed to automate the process of downloading, extracting, and transcribing video recordings—primarily from public meetings such as city council sessions. The tool is particularly useful for generating searchable, text-based archives of civic meetings.

## Features

- **Download Video Recordings**: Fetches video files from a designated source (e.g., municipal meeting archives).
- **Audio Extraction**: Automatically extracts audio tracks from downloaded video files.
- **Speech-to-Text Transcription**: Converts extracted audio into accurate, timestamped text using advanced speech recognition libraries.
- **Chunked Transcriptions**: Stores meeting transcriptions in manageable text file chunks for easy review and downstream processing.
- **Meeting Document Scraper**: Automatically scrapes HTML Agenda and HTML Packet documents from meeting archives and consolidates them into a single NotebookLM-ready file.
- **Error Handling**: Provides clear diagnostic messages and pip installation hints for common issues.

## Use Cases

- Creating searchable records of city council and public hearings.
- Assisting journalists, researchers, or civic technologists in reviewing meeting content.
- Archiving local government proceedings for transparency and accessibility.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BrooksCunningham/govassist.git
   cd govassist
   ```

2. **Install dependencies:**
   Govassist requires Python and several packages, including `openai-whisper` and `moviepy`.

   ```bash
   pip uninstall whisper         # Remove any non-compatible 'whisper' installations
   pip install openai-whisper
   pip install moviepy
   ```

3. **Other dependencies:**
   - Ensure `ffmpeg` is installed and available in your system PATH (required by `moviepy` and `openai-whisper`).
   - Additional requirements may be listed in a `requirements.txt` file or specified in the code.

## Usage

The core logic is implemented in `main.py`. To run the tool:

```bash
python main.py
```

- The script will prompt or be configured to download specific meeting videos using a predefined `BASE_URL`.
- Audio is extracted from each video and automatically transcribed.
- Transcriptions are saved in `transcriptions_chunks/` as text files.

## Configuration

- The video source URL can be set or modified in `main.py` via the `BASE_URL` constant.
- Logging is enabled to provide timestamped, leveled output for script progress and troubleshooting.
- Warnings from dependencies are suppressed for a cleaner console experience.

## Troubleshooting

If you encounter issues related to the `whisper` library, follow the instructions printed in the script output to ensure `openai-whisper` is installed.

## Example Output

Transcriptions are saved as plain text files, containing chunked dialogue from the meetings, such as:

```
tax policy and budget expert because I think what the families of Lafayette parents need...
```

Each file represents a segment of a meeting for easier navigation and review.

## Meeting Document Scraper

The `scrape.py` script provides automated scraping of meeting agendas and packets from Youngsville municipal websites.

### Features

- Scrapes HTML Agenda and HTML Packet documents from all pages of meeting archives
- Extracts clean text content (removes navigation, scripts, and styles)
- Combines all documents into a single `notebooklm_source.txt` file for use with NotebookLM
- Includes source URLs and document metadata in the output
- Respects rate limiting with 1-second delays between requests

### Usage

```bash
python scrape.py
```

The script will:
1. Create a `scraped_content/` directory for intermediate files
2. Fetch all pages from the Youngsville meeting archive
3. Download and extract text from each HTML Agenda and HTML Packet
4. Generate `notebooklm_source.txt` with all combined content

### Automated Monthly Updates

A GitHub Action runs automatically on the 1st of each month to:
- Scrape the latest meeting documents
- Update `notebooklm_source.txt` if new meetings are found
- Commit changes back to the repository

You can also trigger the workflow manually from the Actions tab.

### Configuration

- `BASE_URL`: The municode iframe URL (currently configured for Youngsville, LA)
- `TOTAL_PAGES`: Number of pages to scrape (default: 4)
- `TARGET_LINK_TEXTS`: Document types to scrape (default: ["HTML Packet", "HTML Agenda"])

### Output

- **`notebooklm_source.txt`**: Combined text file ready for NotebookLM upload
- **`scraped_content/`**: Directory with individual text files for each document

## License

See `LICENSE` for license details.

## Contributing

Pull requests, feature suggestions, and bug reports are welcome!
