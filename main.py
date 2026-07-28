import os
import re
import json
import requests
import shutil
import whisper
import logging
import inspect
import warnings
from datetime import datetime

# --- Diagnostic Block ---
# This block will help identify if the wrong "whisper" library is being used.
# The official 'openai-whisper' has the 'load_model' function, while an imposter
# package on PyPI also named 'whisper' does not.
try:
    print("--- WHISPER LIBRARY DIAGNOSTICS ---")
    print(f"Attempting to load the 'whisper' library...")
    if hasattr(whisper, 'load_model'):
        print("SUCCESS: The correct 'openai-whisper' library appears to be loaded.")
        print(f"Library location: {inspect.getfile(whisper)}")
    else:
        print("\n!!! ERROR: The INCORRECT 'whisper' library is installed. !!!")
        print("This is the likely cause of the 'has no attribute load_model' error.")
        print(f"The problematic library is located at: {inspect.getfile(whisper)}")
        print("\nTO FIX THIS, PLEASE RUN THE FOLLOWING COMMANDS IN YOUR TERMINAL:")
        print("1. pip uninstall whisper")
        print("2. pip install openai-whisper\n")
    print("-------------------------------------\n")
except Exception as e:
    print(f"An error occurred during the diagnostic check: {e}")


# --- Configuration ---
# Configure logging to provide timestamped, leveled output to see script progress.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Suppress specific warnings from underlying libraries that can be noisy.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# --- Constants ---
# Archive embed URL that contains the JSON playlist of all meeting recordings.
# This is loaded inside an iframe on https://www.youngsville.us/livestream/
from moviepy import VideoFileClip
ARCHIVE_EMBED_URL = "https://cache.stl.sheenomo.live/eo8nUQfCKXC8M0scH2zp0pmIzMdzmzDg/channels/1/embeds/players/vUzCgGBxuMEjQUfW/render"

# --- Folder Setup ---
# Create necessary folders if they don't exist
download_folder = 'mp4_downloads'
audio_folder = 'audio_extracts'
transcription_folder = 'transcriptions'
os.makedirs(download_folder, exist_ok=True)
os.makedirs(audio_folder, exist_ok=True)
os.makedirs(transcription_folder, exist_ok=True)

def convert_to_iso8601_datetime(meeting_info):
    """
    Convert meeting info to ISO 8601 Extended Format.
    Example: "November 13, 2025 City Council Regular Meeting at 6:00 PM"
    Returns: "2025-11-13T18:00 City Council Regular Meeting" (date and time in ISO 8601 format)
    """
    # Pattern to match: "Month Day, Year ... at H:MM AM/PM"
    # Groups: (1)month_name (2)day (3)year (4)meeting_description (5)hour (6)minute (7)AM/PM
    pattern = r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\s+(.*?)\s+at\s+(\d{1,2}):(\d{2})\s+(AM|PM)'
    match = re.match(pattern, meeting_info)
    
    if not match:
        # If pattern doesn't match, return original
        return meeting_info
    
    month_name, day, year, meeting_desc, hour, minute, am_pm = match.groups()
    
    # Convert month name to number
    try:
        month_num = datetime.strptime(month_name, '%B').month
    except ValueError:
        # If full month name doesn't work, try abbreviated
        try:
            month_num = datetime.strptime(month_name, '%b').month
        except ValueError:
            # If still doesn't work, return original
            return meeting_info
    
    # Convert 12-hour time to 24-hour time
    hour_int = int(hour)
    if am_pm == 'PM' and hour_int != 12:
        hour_int += 12
    elif am_pm == 'AM' and hour_int == 12:
        hour_int = 0
    
    # Format in ISO 8601 Extended Format
    iso_date = f"{year}-{month_num:02d}-{int(day):02d}"
    iso_time = f"{hour_int:02d}:{minute}"
    iso_datetime = f"{iso_date}T{iso_time}"
    
    # Return formatted string with meeting description
    return f"{iso_datetime} {meeting_desc.strip()}"

def make_filename_from_playlist_entry(entry):
    """
    Build a base filename from a playlist entry returned by the sheenomo.live archive embed.
    Each entry contains:
      - title:             e.g. "Council Meeting 7.9.26"
      - pubdate_formatted: e.g. "Thursday, July 9, 2026"
      - pubtime_formatted: e.g. "5:56 PM CDT"
    Returns a sanitized string suitable for use as a filename.
    """
    title = entry.get("title", "")
    pubdate = entry.get("pubdate_formatted", "")
    pubtime = entry.get("pubtime_formatted", "")

    # Parse the date: "Thursday, July 9, 2026" → datetime
    iso_date = ""
    for fmt in ("%A, %B %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(pubdate, fmt)
            iso_date = dt.strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    # Strip timezone abbreviation from time string (e.g. "5:56 PM CDT" → "5:56 PM")
    time_clean = re.sub(r'\s+[A-Z]{2,4}$', '', pubtime).strip()

    # Compose a human-readable string and sanitize it
    if iso_date:
        composed = f"{iso_date}T{time_clean} {title}"
    else:
        composed = title

    return sanitize_filename(composed)

def sanitize_filename(text, max_length=100):
    """
    Sanitize text for use as a filename.
    Removes/replaces characters that are not safe for filenames.
    """
    # Replace common problematic characters
    sanitized = text.replace(':', '').replace(',', '').replace('/', '-')
    sanitized = sanitized.replace('\\', '-').replace('?', '').replace('*', '')
    sanitized = sanitized.replace('"', '').replace('<', '').replace('>', '')
    sanitized = sanitized.replace('|', '-')
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Remove any remaining non-alphanumeric characters except underscore, dash, and period
    sanitized = re.sub(r'[^\w\-.]', '', sanitized)
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized

def download_file(url, filename):
    """Downloads a file from a URL using a streaming request for efficiency."""
    logging.info(f"Downloading video to {filename} from {url}...")
    try:
        # Use a context manager for the request to ensure the connection is closed.
        with requests.get(url, stream=True, timeout=300) as response:
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            with open(filename, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
        logging.info(f"Successfully downloaded {filename}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading {url}: {e}")

def extract_audio_func(video_file, audio_file):
    """
    Extracts audio from a video file using moviepy.
    ENHANCED: Uses a context manager (`with` statement) for robust resource handling,
    ensuring files are closed properly even if errors occur.
    """
    if os.path.exists(audio_file):
        logging.info(f"Audio file {audio_file} already exists. Skipping extraction.")
        return

    logging.info(f"Extracting audio from {video_file}...")
    try:
        # Using a context manager ensures that video file handles are closed automatically.
        with VideoFileClip(video_file) as video_clip:
            audio_clip = video_clip.audio
            if audio_clip:
                # Specify codec and bitrate for consistent, high-quality MP3 output.
                audio_clip.write_audiofile(audio_file, codec='libmp3lame', bitrate='192k')
                logging.info(f"Audio successfully saved as {audio_file}")
            else:
                logging.warning(f"Video file {video_file} appears to have no audio track.")
    except Exception as e:
        # Catching broad exceptions to handle potential moviepy/ffmpeg errors.
        logging.error(f"Error extracting audio with moviepy from {video_file}: {e}")
        logging.error("This might be due to a missing or misconfigured FFmpeg installation.")

def transcribe_audio(audio_file, transcription_file):
    """Transcribes the given audio file using OpenAI's Whisper model."""
    if not os.path.exists(audio_file):
        logging.error(f"Audio file {audio_file} does not exist. Cannot transcribe.")
        return

    if os.path.exists(transcription_file):
        logging.info(f"Transcription {transcription_file} already exists. Skipping.")
        return

    logging.info(f"Transcribing audio file {audio_file} with 'base' model...")
    try:
        # Load the Whisper model. For higher accuracy, consider "small" or "medium".
        model = whisper.load_model("base")
        result = model.transcribe(audio_file, fp16=False) # fp16=False can improve compatibility
        full_text = result["text"]

        # Save the full transcription text to a file.
        with open(transcription_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        logging.info(f"Transcription saved to {transcription_file}")
    except Exception as e:
        logging.error(f"Error during transcription of {audio_file}: {e}")

def fetch_playlist():
    """
    Fetch the sheenomo.live archive embed page and extract the meeting playlist.

    The embed page embeds all meeting metadata in a JavaScript variable:
        _SCIO.config.playerSetup.originalPlaylist = [ ... ];
    Each entry contains title, pubdate_formatted, pubtime_formatted,
    videoDownloadURL, audioDownloadURL, and HLS sources.

    Returns a list of dicts (one per meeting), or an empty list on failure.
    """
    logging.info(f"Fetching archive playlist from {ARCHIVE_EMBED_URL}...")
    try:
        response = requests.get(ARCHIVE_EMBED_URL, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not retrieve archive embed. Error: {e}")
        return []

    html = response.text

    # Extract the JSON array assigned to originalPlaylist
    match = re.search(
        r'_SCIO\.config\.playerSetup\.originalPlaylist\s*=\s*(\[.*?\]);',
        html,
        re.DOTALL,
    )
    if not match:
        logging.error("Could not find originalPlaylist in archive embed page.")
        return []

    try:
        playlist = json.loads(match.group(1))
        logging.info(f"Found {len(playlist)} meeting(s) in playlist.")
        return playlist
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse playlist JSON: {e}")
        return []


def process_meetings():
    """
    Fetch all archived meeting recordings and orchestrate the
    download-transcribe workflow for each entry.

    The sheenomo.live embed exposes a direct audioDownloadURL for every
    meeting, so we download the audio file directly and skip the
    video-download + audio-extraction steps entirely.
    """
    playlist = fetch_playlist()
    if not playlist:
        logging.info("No meetings found in playlist.")
        return

    for entry in playlist:
        base_filename = make_filename_from_playlist_entry(entry)
        if not base_filename:
            logging.warning(f"Could not build filename for entry: {entry.get('title')}")
            continue

        audio_url = entry.get("audioDownloadURL", "")
        video_url = entry.get("videoDownloadURL", "")

        audio_file_path = os.path.join(audio_folder, f"{base_filename}.mp3")
        transcription_file_path = os.path.join(transcription_folder, f"{base_filename}.txt")

        # 1. Skip all steps if the final output (transcription) already exists.
        if os.path.exists(transcription_file_path):
            logging.info(f"Final transcription exists for {base_filename}. Skipping all steps.")
            continue

        # 2. Download audio directly if available, otherwise fall back to video.
        if not os.path.exists(audio_file_path):
            if audio_url:
                logging.info(f"Downloading audio directly for {base_filename}...")
                download_file(audio_url, audio_file_path)
            elif video_url:
                video_filename = os.path.join(download_folder, f"{base_filename}.mp4")
                if not os.path.exists(video_filename):
                    download_file(video_url, video_filename)
                if os.path.exists(video_filename):
                    extract_audio_func(video_filename, audio_file_path)
                    if os.path.exists(video_filename):
                        logging.info(f"Removing video file {video_filename} to save space...")
                        os.remove(video_filename)
            else:
                logging.warning(f"No download URL found for {base_filename}. Skipping.")
                continue

        # 3. Transcribe the audio file if it exists.
        transcribe_audio(audio_file_path, transcription_file_path)

        logging.info("-" * 20)

def main():
    """Main function to run the scraper and transcription process."""
    process_meetings()
    logging.info("\nProcessing complete.")


if __name__ == "__main__":
    main()
