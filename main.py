import os
import requests
from bs4 import BeautifulSoup
import shutil
import whisper
import logging
import inspect
import warnings
import re
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
# Base URL for the website and the mp4 storage domain
from moviepy import VideoFileClip
BASE_URL = "https://meetings.municode.com/PublishPage?cid=YOUNGSVILA&ppid=5d44059a-1e19-4452-a226-babc4b369c18&p={}"
VIDEO_DOMAIN = "https://storage.sheenomo.live"

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
    iso_time = f"{hour_int:02d}{minute}"
    iso_datetime = f"{iso_date}T{iso_time}"
    
    # Return formatted string with meeting description
    return f"{iso_datetime}_{meeting_desc.strip()}"

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

def process_page(page_number):
    """Processes a single page: finds video links and orchestrates the download-extract-transcribe workflow."""
    logging.info(f"Processing page {page_number}...")
    
    url = BASE_URL.format(page_number)
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not retrieve page {page_number}. Error: {e}")
        return

    soup = BeautifulSoup(response.content, "html.parser")
    # Find all anchor tags whose href contains the video storage domain
    mp4_links = soup.find_all('a', href=lambda href: href and VIDEO_DOMAIN in href)
    
    if not mp4_links:
        logging.info(f"No video links found on page {page_number}.")
        return

    for link in mp4_links:
        video_url = link['href']
        img_tag = link.find('img')
        base_filename = ""

        if img_tag and 'alt' in img_tag.attrs:
            # Get alt text (e.g., "Multimedia for November 13, 2025 City Council Regular Meeting at 6:00 PM")
            alt_text = img_tag['alt']
            
            # Extract meeting info after "Multimedia for " or similar prefix
            if 'for ' in alt_text:
                meeting_info = alt_text.split('for ', 1)[1]
                # Convert to ISO 8601 format
                iso_formatted = convert_to_iso8601_datetime(meeting_info)
                # Sanitize for use as filename
                base_filename = sanitize_filename(iso_formatted)
            else:
                # Fallback to basic sanitization if pattern doesn't match
                sanitized_name = img_tag['alt'].replace(' ', '_').replace(':', '').replace(',', '')
                base_filename = f"{sanitized_name}"
        else:
            # Create a fallback name from the URL if no alt text is available.
            base_filename = os.path.splitext(os.path.basename(video_url))[0]

        # Define file paths for each stage of the process.
        video_filename = os.path.join(download_folder, f"{base_filename}.mp4")
        audio_file_path = os.path.join(audio_folder, f"{base_filename}.mp3")
        transcription_file_path = os.path.join(transcription_folder, f"{base_filename}.txt")

        # --- Main Workflow Logic ---
        # 1. Skip all steps if the final output (transcription) already exists.
        if os.path.exists(transcription_file_path):
            logging.info(f"Final transcription exists for {base_filename}. Skipping all steps.")
            continue

        # 2. Download video only if the audio doesn't already exist and the video isn't already there.
        if not os.path.exists(audio_file_path) and not os.path.exists(video_filename):
            download_file(video_url, video_filename)
        
        # 3. Extract audio if the video file is present.
        if os.path.exists(video_filename):
            extract_audio_func(video_filename, audio_file_path)
        
        # 4. Transcribe the audio file if it exists.
        transcribe_audio(audio_file_path, transcription_file_path)
        
        # 5. Clean up by removing the large video file after processing.
        if os.path.exists(video_filename):
            logging.info(f"Removing video file {video_filename} to save space...")
            os.remove(video_filename)
        
        logging.info("-" * 20)

def main():
    """Main function to run the scraper and transcription process."""
    # Assuming there are 5 pages to process based on the website structure.
    total_pages = 5
    
    for page_number in range(1, total_pages + 1):
        process_page(page_number)
    
    logging.info("\nProcessing complete.")


if __name__ == "__main__":
    main()
