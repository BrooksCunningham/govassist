import os
import requests
from bs4 import BeautifulSoup
import shutil
import whisper

import warnings

# Suppress the torch FutureWarning and UserWarning for FP16
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Base URL for the website and the mp4 storage domain
BASE_URL = "https://meetings.municode.com/PublishPage?cid=YOUNGSVILA&ppid=5d44059a-1e19-4452-a226-babc4b369c18&p={}"
VIDEO_DOMAIN = "https://storage.sheenomo.live"

# Step 4: Create the download folder if it doesn't exist
download_folder = 'mp4_downloads'
audio_folder = 'audio_extracts'
transcription_folder = 'transcriptions'
os.makedirs(download_folder, exist_ok=True)
os.makedirs(audio_folder, exist_ok=True)
os.makedirs(transcription_folder, exist_ok=True)

def download_file(url, filename):
    """Downloads a file from the given URL and saves it with the specified filename."""
    response = requests.get(url, stream=True)
    with open(filename, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
    del response

def extract_audio_func(video_file, audio_file):
    """Extracts audio from the given video file and saves it as an audio file using ffmpeg."""
    if os.path.exists(audio_file):
        print(f"Audio file {audio_file} already exists. Skipping extraction.")
        return
    print(f"Extracting audio from {video_file}...")
    try:
        from audio_extract import extract_audio
        extract_audio(input_path=video_file, output_path=audio_file)
        print(f"Audio saved as {audio_file}")
    except Exception as e:
        print(f"Error extracting audio: {e}")

def save_chunks(transcription_file, chunks):
    """Saves each chunk to a separate text file."""
    base_filename = os.path.splitext(transcription_file)[0]
    for i, chunk in enumerate(chunks):
        chunk_filename = f"{base_filename}_chunk_{i+1}.txt"
        with open(chunk_filename, 'w') as f:
            f.write(chunk)
        print(f"Chunk {i+1} saved as {chunk_filename}")

def chunks_exist(transcription_file):
    """Check if chunk files for the given transcription already exist."""
    base_filename = os.path.splitext(transcription_file)[0]
    # We assume that chunk files are named as <base_filename>_chunk_X.txt
    i = 1
    while True:
        chunk_filename = f"{base_filename}_chunk_{i}.txt"
        if os.path.exists(chunk_filename):
            i += 1
        else:
            break
    return i > 1  # Returns True if any chunk files exist

def transcribe_audio(audio_file, transcription_file):
    """Transcribes the audio file using Whisper, chunks the transcription, and saves each chunk."""
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} does not exist. Cannot transcribe.")
        return None
    
    # If the transcription file already exists, load and return its content
    if os.path.exists(transcription_file):
        print(f"Transcription file already exists. {transcription_file}")

        # Read the full transcription text
        with open(transcription_file, 'r') as f:
            full_text = f.read()

        # Check if chunking has already been performed
        if chunks_exist(transcription_file):
            print(f"Chunks already exist for {transcription_file}. Skipping chunking.")
            return full_text
        else:
            print(f"No chunks found for {transcription_file}. Proceeding with chunking.")
            chunks = chunk_text(full_text, chunk_size=500)
            save_chunks(transcription_file, chunks)
            print(f"Chunks created and saved for {transcription_file}.")
            return full_text
    
    print(f"Transcribing audio file {audio_file}...")
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
        full_text = result["text"]

        # Save the full transcription text
        with open(transcription_file, 'w') as f:
            f.write(full_text)

        # Proceed with chunking
        chunks = chunk_text(full_text, chunk_size=500)
        save_chunks(transcription_file, chunks)
        print(f"Transcription and chunking completed for {transcription_file}.")
        return full_text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None


def process_page(page_number):
    """Processes each page of the meeting, extracts MP4 URLs, handles downloading, audio extraction, and transcription."""
    print(f"Processing page {page_number}...")
    
    # Get the page's HTML content
    url = BASE_URL.format(page_number)
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Find all the rows with multimedia links (mp4 files)
    mp4_links = soup.find_all('a', href=lambda href: href and 'storage.sheenomo.live' in href)
    
    for link in mp4_links:
        video_url = link['href']  # The MP4 file URL
        img_tag = link.find('img')  # Find the associated <img> tag inside the <a>

        # Generate the file name based on the alt attribute or use a default
        if img_tag and 'alt' in img_tag.attrs:
            base_filename = img_tag['alt'].replace(' ', '_').replace(':', '').replace(',','') + '.mp4'  # Use the alt attribute for naming
        else:
            base_filename = 'unnamed_video.mp4'  # Default name if no alt attribute is found

        # Generate the audio and transcription file names
        audio_file_name = base_filename.replace('.mp4', '.mp3')
        transcription_file_name = base_filename.replace('.mp4', '.txt')
        audio_file_path = os.path.join(audio_folder, audio_file_name)
        transcription_file_path = os.path.join(transcription_folder, transcription_file_name)

        video_filename = os.path.join(download_folder, f"{base_filename}.mp4")

        # Check if transcription already exists. Do not download the video if the link exists
        if os.path.exists(transcription_file_path):
            print(f"Transcription file already exists. Skipping download and processing. {transcription_file_path}")
            continue

        if os.path.exists(audio_file_path):
            print(f"Audio file {audio_file_path} already exists. Skipping download and processing.")
            continue

        # Download the MP4 file
        if not os.path.exists(video_filename) and not os.path.exists(audio_file_path):
            print(f"Downloading video {video_filename} from {video_url}...")
            download_file(video_url, video_filename)

        # Extract audio
        if not os.path.exists(audio_file_path):
            print(f"Extracting audio file {audio_file_path}")
            extract_audio_func(video_filename, audio_file_path)
                        
        
        # Transcribe audio
        transcribe_audio(audio_file_path, transcription_file_path)
        
        # Remove video file after extraction
        if os.path.exists(video_filename):
            print(f"Removing video file {video_filename}...")
            os.remove(video_filename)

def chunks_exist(transcription_file):
    """Check if chunk files for the given transcription already exist."""
    base_filename = os.path.splitext(transcription_file)[0]
    # We assume that chunk files are named as <base_filename>_chunk_X.txt
    i = 1
    while True:
        chunk_filename = f"{base_filename}_chunk_{i}.txt"
        if os.path.exists(chunk_filename):
            i += 1
        else:
            break
    return i > 1  # Returns True if any chunk files exist

def chunk_text(text, chunk_size=500):
    """Splits the text into chunks of a given size (default: 500 words)."""
    words = text.split()
    # Create chunks of up to `chunk_size` words
    for i in range(0, len(words), chunk_size):
        yield ' '.join(words[i:i + chunk_size])

def process_transcribed_files_in_directory(directory_path, directory_path_chunks):
    """Prints the full text of all .txt files in the given directory."""
    # Check if the directory exists
    if not os.path.exists(directory_path):
        print(f"Error: Directory {directory_path} does not exist.")
        return

    # List all files in the directory
    for filename in os.listdir(directory_path, directory_path_chunks):
        # Avoid trying to rechunk data
        if chunks_exist(filename):
            print(f"Chunks already exist for {filename}. Skipping chunking.")
            continue

        # Filter only .txt files
        if filename.endswith(".txt"):
            file_path = os.path.join(directory_path, filename)
            print(f"Reading file: {file_path}")
            
            # Open and read the full text of the file
            try:
                with open(file_path, 'r') as file:
                    full_text = file.read()

                    # Chunk the transcription text
                    chunks = chunk_text(full_text, chunk_size=500)

                    # Save chunks as separate text files
                    save_chunks(directory_path_chunks, chunks)

                    
            except Exception as e:
                print(f"Error reading {filename}: {e}")

def main():
    # Get total number of pages from the dropdown (example has 5 pages, update dynamically if needed)
    total_pages = 5  # Based on the HTML provided, there are 5 pages
    
    # Process each page
    for page_number in range(1, total_pages + 1):
        process_page(page_number)
    
    # process each recording
    process_transcribed_files_in_directory("transcriptions", "transcriptions_chunks")


if __name__ == "__main__":
    main()
