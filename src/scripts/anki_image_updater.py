import argparse
import base64
import logging
import urllib
import sys
import time
from typing import List, Dict, Any, Optional

import requests

from ..utils import config
from ..core.anki_client import find_notes, notes_info, update_note_fields, store_media_file, check_connection
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
            logger.info("No results found for '%s' in Langeek API.", word)
            return None

        # The API returns a list of matches. Usually the first one is the best match.
        # Structure: [{ ..., translation: { ..., wordPhoto: { photo: "URL" } } }]

        first_match = data[0]
        translation = first_match.get('translation')
        if not translation:
             logger.debug("No translation object for '%s'.", word)
             return None

        word_photo = translation.get('wordPhoto')
        if not word_photo:
            logger.debug("No wordPhoto object for '%s'.", word)
            return None

        image_url = word_photo.get('photo')
        if image_url:
            logger.info("Found image URL for '%s': %s", word, image_url)
            return image_url

        return None

    except Exception as e:
        logger.error("Error searching Langeek API for '%s': %s", word, e)
        return None

def download_image_as_base64(url: str) -> Optional[str]:
    """Download image and return base64 encoded string."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.error("Failed to download image from %s: %s", url, e)
        return None

def update_cards_with_images(deck_name: str, ease_limit: Optional[float] = None):
    """Find cards with low ease and update them with images."""
    query = f'deck:"{deck_name}"'
    if ease_limit is not None:
        query += f' prop:ease<{ease_limit}'

    logger.info("Searching for cards with query: %s", query)

    note_ids = find_notes(query)
    if not note_ids:
        logger.info("No cards matching the criteria found.")
        return

    logger.info("Found %d notes to process.", len(note_ids))
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

        # Determine which field to update
        target_field = None
        if 'フレーズ' in fields:
            target_field = 'フレーズ'
        elif 'Front' in fields:
            target_field = 'Front'

        if not target_field:
            logger.warning("Could not determine target field for note %s. Fields: %s", note_id, fields.keys())
            continue

        if "<img" in fields.get(target_field, {}).get('value', ""):
            logger.debug("Note %s already has an image in '%s'. Skipping.", note_id, target_field)
            continue

        if not word:
            logger.warning("Could not determine word for note %s.", note_id)
            continue

        logger.info("⭐️Processing note %d/%d (ID: %s, Word: %s)", i+1, len(notes_data), note_id, word)

        # Add a small delay to be nice to the API
        time.sleep(0.5)

        img_b64 = download_image_as_base64(image_url)
        if not img_b64:
            logger.info("Failed to download image for word: %s", word)
            continue

        current_phrase = fields.get(target_field, {}).get('value', "")
        try:
            # Store image in Anki media folder for robustness
            image_filename = f"langeek_{word}_{note_id}.jpg"
            store_media_file(image_filename, img_b64)

            # Update note with local image reference
            updated_phrase = f'{current_phrase}<br><img src="{image_filename}" width="400">'

            update_fields = {target_field: updated_phrase}
            update_note_fields(note_id, update_fields)
            logger.info("Updated note %s with local image '%s' in '%s' field.", note_id, image_filename, target_field)

        except Exception as e:
            logger.error("Failed to update note %s: %s", note_id, e)

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Add images to difficult Anki cards using Langeek API")
    parser.add_argument("--deck", default="1_Vocabulary_今日の復習", help="Deck name")
    parser.add_argument("--ease", type=float, default=None, help="Ease threshold (prop:ease<X)")

    args = parser.parse_args()

    if not check_connection():
        logger.error("Cannot connect to AnkiConnect. Is Anki running?")
        sys.exit(1)

    update_cards_with_images(args.deck, args.ease)

if __name__ == "__main__":
    main()

# python -m src.scripts.anki_image_updater --deck "1_Vocabulary" --ease 2
