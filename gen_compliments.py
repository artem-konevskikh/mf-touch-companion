import argparse
import json
import os
import requests
from pathlib import Path
from tqdm import tqdm 

API_URL = 'https://art.ycloud.eazify.net:8443/comp'

COMPLIMENTS_FILE_PATH = Path(__file__).parent / 'src' / 'compliments.json'

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}

def load_compliments(file_path):
    """Loads compliments from the JSON file."""
    if not file_path.exists():
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('compliments', [])
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading compliments from {file_path}: {e}")
        return []

def save_compliments(file_path, compliments):
    """Saves compliments to the JSON file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({'compliments': compliments}, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Error saving compliments to {file_path}: {e}")

def process_image(image_path):
    """Sends an image to the API and returns the compliment text."""
    try:
        with open(image_path, 'rb') as f:
            binary_jpeg_data = f.read()
        
        res = requests.post(API_URL, data=binary_jpeg_data, timeout=10) # Added timeout
        res.raise_for_status() # Raise an exception for bad status codes
        
        response_data = res.json()
        compliment_text = response_data.get('text')
        if compliment_text:
            return compliment_text
        else:
            print(f"  -> No 'text' field found in response for {image_path.name}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending {image_path.name} to API: {e}")
        return None
    except Exception as e:
        print(f"Error processing {image_path.name}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Generate compliments from images in a folder.')
    parser.add_argument('-i', '--input_folder', required=True, type=str,
                        help='Path to the folder containing images.')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_folder)
    if not input_path.is_dir():
        print(f"Error: Input path '{input_path}' is not a valid directory.")
        return

    print(f"Loading existing compliments from {COMPLIMENTS_FILE_PATH}...")
    existing_compliments = load_compliments(COMPLIMENTS_FILE_PATH)
    print(f"Loaded {len(existing_compliments)} existing compliments.")
    
    new_compliments_added = 0
    
    image_files = [item for item in input_path.iterdir() if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS]
    total_images = len(image_files)
    print(f"Found {total_images} images to process in {input_path}.") # Inform user about total images

    for item in tqdm(image_files, desc="Processing images", unit="image"):
        compliment = process_image(item)
        if compliment and compliment not in existing_compliments:
            existing_compliments.append(compliment)
            new_compliments_added += 1

    if new_compliments_added > 0:
        print(f"Added {new_compliments_added} new unique compliments.")
        save_compliments(COMPLIMENTS_FILE_PATH, existing_compliments)
        print(f"Successfully saved {len(existing_compliments)} compliments to {COMPLIMENTS_FILE_PATH}") # Moved save confirmation here
    else:
        print("No new unique compliments were added.")

if __name__ == '__main__':
    main()