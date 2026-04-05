import csv
import logging
import os
import sys

# Ensure we can import from src
sys.path.append(os.getcwd())

from src.core.anki_client import _invoke, find_notes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CSV_FILES = [
    "Anki追加登録 - 英作文_CV.csv",
    "Anki追加登録 - 英作文_キャリア (1).csv"
]
DECK_NAME = "2_EnglishComposition"
TAG = "interview1"

def add_tag_to_notes(note_ids, tag):
    """Add a tag to a list of note IDs via AnkiConnect."""
    if not note_ids:
        return
    try:
        # addTags action adds tags to the specified notes
        _invoke("addTags", {"notes": note_ids, "tags": tag})
        logger.debug(f"Added tag '{tag}' to note IDs: {note_ids}")
    except Exception as e:
        logger.error(f"Failed to add tags: {e}")

def main():
    total_processed = 0
    total_found = 0
    total_not_found = 0

    logger.info(f"Starting to tag notes in deck '{DECK_NAME}' with tag '{TAG}'")

    for csv_file in CSV_FILES:
        path = os.path.join(os.getcwd(), csv_file)
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            continue

        logger.info(f"--- Processing {csv_file} ---")

        try:
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 1:
                        continue

                    # Column 1: Japanese sentence
                    # Column 2: English sentence
                    japanese_text = row[0].strip()
                    english_text = row[1].strip() if len(row) > 1 else ""

                    if not japanese_text:
                        continue

                    total_processed += 1

                    # 1. Search by Japanese text in the '表' field
                    search_text_jp = japanese_text.replace('"', '\\"')
                    query = f'deck:"{DECK_NAME}" "表:{search_text_jp}"'
                    note_ids = find_notes(query)

                    # 2. Fallback: Search by Japanese text anywhere in the note
                    if not note_ids:
                        query = f'deck:"{DECK_NAME}" "{search_text_jp}"'
                        note_ids = find_notes(query)

                    # 3. Fallback: Search by English text in the '裏' field
                    if not note_ids and english_text:
                        search_text_en = english_text.replace('"', '\\"')
                        query = f'deck:"{DECK_NAME}" "裏:{search_text_en}"'
                        note_ids = find_notes(query)

                    # 4. Fallback: Search by English text anywhere in the note
                    if not note_ids and english_text:
                        query = f'deck:"{DECK_NAME}" "{search_text_en}"'
                        note_ids = find_notes(query)

                    if note_ids:
                        add_tag_to_notes(note_ids, TAG)
                        total_found += 1
                        logger.info(f"Found and tagged: {japanese_text[:40]}...")
                    else:
                        logger.warning(f"Note NOT found: {japanese_text[:40]}...")
                        total_not_found += 1

        except Exception as e:
            logger.error(f"Error processing file {csv_file}: {e}")

    logger.info("=" * 50)
    logger.info(f"Process Completed")
    logger.info(f"  Total sentences in CSV: {total_processed}")
    logger.info(f"  Successfully found & tagged: {total_found}")
    logger.info(f"  Not found: {total_not_found}")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
