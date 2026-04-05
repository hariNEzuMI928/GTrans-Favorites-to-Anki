import argparse
import base64
import logging
import urllib
import sys
import time
from typing import List, Dict, Any, Optional

import requests

from ..utils import config
from ..core.anki_client import find_notes, notes_info, update_note_fields, store_media_file, _invoke
from ..utils.logging_setup import setup_logging

logger = logging.getLogger("anki_image_updater")

def get_langeek_image_url(word: str) -> Optional[str]:
    """
    Search Langeek API for the word and return the primary image URL.
    Uses the internal API endpoint: https://api.langeek.co/v1/cs/en/word/?term={word}
    """
    quoted_word = urllib.parse.quote(word)
    url = f"https://api.langeek.co/v1/cs/en/word/?term={quoted_word}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, list):
            logger.info(f"No results found for '{word}' in Langeek API.")
            return None

        # The API returns a list of matches. Usually the first one is the best match.
        # Structure: [{ ..., translation: { ..., wordPhoto: { photo: "URL" } } }]

        first_match = data[0]
        translation = first_match.get('translation')
        if not translation:
             logger.debug(f"No translation object for '{word}'.")
             return None

        word_photo = translation.get('wordPhoto')
        if not word_photo:
            logger.debug(f"No wordPhoto object for '{word}'.")
            return None

        image_url = word_photo.get('photo')
        if image_url:
            logger.info(f"Found image URL for '{word}': {image_url}")
            return image_url

        return None

    except Exception as e:
        logger.error(f"Error searching Langeek API for '{word}': {e}")
        return None

def download_image_as_base64(url: str) -> Optional[str]:
    """Download image and return base64 encoded string."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None

def update_cards_with_images(deck_name: str, ease_limit: Optional[float] = None):
    """Find cards with low ease and update them with images."""
    query = f'deck:"{deck_name}"'
    if ease_limit is not None:
        query += f' prop:ease<{ease_limit}'

    logger.info(f"Searching for cards with query: {query}")

    note_ids = find_notes(query)
    if not note_ids:
        logger.info("No cards matching the criteria found.")
        return

    logger.info(f"Found {len(note_ids)} notes to process.")
    notes_data = notes_info(note_ids)

    for i, note in enumerate(notes_data):
        note_id = note['noteId']
        fields = note['fields']


        # Determine the word to search for.
        word = None
        if '単語' in fields:
            word = fields['単語']['value']
        elif 'Front' in fields:
            word = fields['Front']['value']

        if 'フレーズ' in fields:
          target_field = 'フレーズ'
        elif 'Front' in fields:
          target_field = 'Front'

        if "<img" in fields.get(target_field, {}).get('value', ""):
            logger.debug(f"Note {note_id} already has an image in '{target_field}'. Skipping.")
            continue

        if not word:
            logger.warning(f"Could not determine word for note {note_id}. Fields: {fields.keys()}")
            continue

        logger.info(f"⭐️Processing note {i+1}/{len(notes_data)} (ID: {note_id}, Word: {word})")

        # Add a small delay to be nice to the API
        time.sleep(0.5)

        image_url = get_langeek_image_url(word)
        if not image_url:
            logger.info(f"No image found for word: {word}")
            continue

        img_b64 = download_image_as_base64(image_url)
        if not img_b64:
            logger.info(f"Failed to download image for word: {word}")
            continue

        current_phrase = fields.get(target_field, {}).get('value', "")
        try:
            # 既存のフレーズを残しつつ、指定のHTMLを追加
            updated_phrase = f'{current_phrase}<br><img src="{image_url}" width="400">'

            update_fields = {target_field: updated_phrase}
            update_note_fields(note_id, update_fields)
            logger.info(f"Updated note {note_id} with image URL in '{target_field}' field.")

        except Exception as e:
            logger.error(f"Failed to update note {note_id}: {e}")

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Add images to difficult Anki cards using Langeek API")
    parser.add_argument("--deck", default="1_Vocabulary_今日の復習", help="Deck name")
    parser.add_argument("--ease", type=float, default=None, help="Ease threshold (prop:ease<X)")

    args = parser.parse_args()

    try:
        _invoke("version")
    except Exception as e:
        logger.error(f"Cannot connect to AnkiConnect. Is Anki running? Error: {e}")
        sys.exit(1)

    update_cards_with_images(args.deck, args.ease)

if __name__ == "__main__":
    main()

# python -m src.scripts.anki_image_updater --deck "1_Vocabulary" --ease 2
