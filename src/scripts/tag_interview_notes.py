import csv
import logging
import os
import sys

from ..core.anki_client import _invoke, find_notes
from ..utils.logging_setup import setup_logging

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
        logger.debug("Added tag '%s' to note IDs: %s", tag, note_ids)
    except Exception as e:
        logger.error(f"Failed to add tags: {e}")

def main():
    setup_logging()
    total_processed = 0
    total_found = 0
    total_not_found = 0

    logger.info("Starting to tag notes in deck '%s' with tag '%s'", DECK_NAME, TAG)

    for csv_file in CSV_FILES:
        path = os.path.join(os.getcwd(), csv_file)
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            continue

        logger.info("--- Processing %s ---", csv_file)

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
                        logger.info("Found and tagged: %s...", japanese_text[:40])
                    else:
                        logger.warning("Note NOT found: %s...", japanese_text[:40])
                        total_not_found += 1

        except Exception as e:
            logger.error("Error processing file %s: %s", csv_file, e)

    logger.info("=" * 50)
    logger.info("Process Completed")
    logger.info("  Total sentences in CSV: %d", total_processed)
    logger.info("  Successfully found & tagged: %d", total_found)
    logger.info("  Not found: %d", total_not_found)
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
