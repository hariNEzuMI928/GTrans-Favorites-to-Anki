from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import List, Dict, Any, Set, Tuple, Optional

from . import config
from .logging_setup import setup_logging
from .scraper import ensure_logged_in, fetch_favorites, delete_favorite_item, FavoriteItem
from .gemini_client import GeminiProcessor, ProcessedItem, ProcessedWord, ProcessedSentence
from .anki_client import ensure_deck_and_model, format_word_note, format_sentence_note, add_note
from .storage import load_ids, save_ids
from .anki_client import AnkiNote # Import AnkiNote TypedDict


logger = logging.getLogger("main")

def _load_and_filter_favorites(
    limit: int, processed_item_ids: Set[str], skip_browser: bool
) -> List[FavoriteItem]:
    """Loads favorites, cleans up stale items, and filters out already processed ones."""
    all_favorites: List[FavoriteItem] = []
    if not skip_browser:
        logger.info("Fetching favorite items from Google Translate...")
        all_favorites = fetch_favorites(limit=limit)
        logger.info("Found %d favorite items in Google Translate.", len(all_favorites))

        stale_favorites = [item for item in all_favorites if item.item_id in processed_item_ids]
        if stale_favorites:
            logger.info(
                "Found %d stale items in Google Translate favorites that were already processed. Cleaning up...",
                len(stale_favorites),
            )
            deleted_count = 0
            for item in stale_favorites:
                if delete_favorite_item(item):
                    deleted_count += 1
                else:
                    logger.warning(
                        "Failed to delete stale item %s from Google Translate favorites.",
                        item.text,
                    )
            logger.info("Successfully deleted %d stale items.", deleted_count)
            logger.info("Refetching favorites from Google Translate after cleanup...")
            all_favorites = fetch_favorites(limit=limit)
            logger.info("Found %d favorite items after cleanup.", len(all_favorites))
    else:
        logger.info("Skipping browser operation as --skip-browser is enabled.")

    new_favorites = [item for item in all_favorites if item.item_id not in processed_item_ids]
    logger.info("Found %d new items to process.", len(new_favorites))
    return new_favorites


def _process_new_favorites(
    new_favorites: List[FavoriteItem], limit: int, dry_run: bool
) -> Tuple[List[AnkiNote], Set[str]]:
    """Processes new favorite items using Gemini AI and prepares Anki notes."""
    gemini_processor = GeminiProcessor()
    notes_to_add: List[AnkiNote] = []
    newly_processed_ids: Set[str] = set()

    logger.info("Processing %d new items with Gemini AI...", len(new_favorites))
    for i, item in enumerate(new_favorites):
        if dry_run and i >= limit:
            logger.info(
                "Dry run limit of %d reached for Gemini processing. Skipping remaining items.",
                limit,
            )
            break

        logger.info(
            "Processing item %d/%d: %s - %s", i + 1, len(new_favorites), item.text, item.translation
        )
        processed_item: Optional[ProcessedItem] = gemini_processor.process_item(item)

        if processed_item:
            if processed_item.type == "word":
                notes_to_add.append(format_word_note(processed_item.data))
            elif processed_item.type == "sentence":
                notes_to_add.append(format_sentence_note(processed_item.data))
            newly_processed_ids.add(item.item_id)
        else:
            logger.warning("Failed to process item: %s. Skipping.", item.text)

    logger.info("Prepared %d notes for Anki.", len(notes_to_add))
    return notes_to_add, newly_processed_ids


def _add_notes_to_anki(
    notes_to_add: List[AnkiNote],
    new_favorites: List[FavoriteItem],
    processed_item_ids: Set[str],
) -> List[FavoriteItem]:
    """Adds notes to Anki and updates processed IDs."""
    ensure_deck_and_model(config.ANKI_WORD_DECK_NAME, config.ANKI_WORD_NOTE_TYPE)
    ensure_deck_and_model(config.ANKI_SENTENCE_DECK_NAME, config.ANKI_SENTENCE_NOTE_TYPE)

    logger.info("Adding %d notes to Anki one by one...", len(notes_to_add))
    successfully_added_items: List[FavoriteItem] = []

    for i, note in enumerate(notes_to_add):
        original_favorite_item = new_favorites[i]
        note_id = add_note(note)

        if note_id is not None:
            successfully_added_items.append(original_favorite_item)
            logger.info(
                "Successfully added note for item '%s' (ID: %s).",
                original_favorite_item.text,
                note_id,
            )
        else:
            logger.warning("Failed to add note for item '%s'.", original_favorite_item.text)

    logger.info(
        "Successfully added %d notes to Anki out of %d attempted.",
        len(successfully_added_items),
        len(notes_to_add),
    )

    for item in successfully_added_items:
        processed_item_ids.add(item.item_id)
    save_ids(config.PROCESSED_IDS_PATH, processed_item_ids)
    logger.info("Updated processed_ids.json with %d items.", len(processed_item_ids))
    return successfully_added_items


def _delete_processed_favorites(
    successfully_added_items: List[FavoriteItem], skip_browser: bool
) -> None:
    """Deletes successfully added items from Google Translate favorites."""
    if not skip_browser:
        logger.info(
            "Deleting %d successfully added items from Google Translate favorites...",
            len(successfully_added_items),
        )
        deleted_count = 0
        for item in successfully_added_items:
            if delete_favorite_item(item):
                deleted_count += 1
            else:
                logger.warning(
                    "Failed to delete item %s from Google Translate favorites.", item.text
                )
        logger.info(
            "Successfully deleted %d items from Google Translate favorites.", deleted_count
        )
    else:
        logger.info("Skipping deletion from Google Translate favorites as --skip-browser is enabled.")


def run_once(limit: int, dry_run: bool, skip_browser: bool) -> None:
    logger.info("Starting a single run...")

    processed_item_ids: Set[str] = load_ids(config.PROCESSED_IDS_PATH)
    logger.info("Loaded %d already processed items.", len(processed_item_ids))

    new_favorites = _load_and_filter_favorites(limit, processed_item_ids, skip_browser)

    if not new_favorites:
        logger.info("No new items to process. Exiting run.")
        return

    notes_to_add, newly_processed_ids = _process_new_favorites(new_favorites, limit, dry_run)

    if not notes_to_add:
        logger.info("No notes were successfully processed for Anki. Exiting.")
        return

    if dry_run:
        logger.info("Dry run enabled. Skipping Anki card creation and deletion from Google Favorites.")
        for note in notes_to_add:
            logger.info(
                "DRY RUN - Anki Note (Deck: %s, Model: %s): %s",
                note.get("deckName"),
                note.get("modelName"),
                note.get("fields"),
            )
        logger.info(
            "DRY RUN - Would mark %d items as processed: %s",
            len(newly_processed_ids),
            list(newly_processed_ids)[:5],
        )
        return

    successfully_added_items = _add_notes_to_anki(notes_to_add, new_favorites, processed_item_ids)
    _delete_processed_favorites(successfully_added_items, skip_browser)


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Anki Vocab Bot")
    parser.add_argument("--manual-login", action="store_true", help="Perform manual login and save auth state.")
    parser.add_argument("--once", action="store_true", help="Run once and exit.")
    parser.add_argument("--limit", type=int, default=config.DEFAULT_BATCH_LIMIT, help="Limit the number of items to process.")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without sending to AnkiConnect.")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser operations (for testing non-browser logic).")
    args = parser.parse_args()

    if args.manual_login:
        ensure_logged_in(manual_login=True)
        return 0

    if args.once:
        run_once(limit=args.limit, dry_run=args.dry_run, skip_browser=args.skip_browser)
    else:
        logger.info("Running in continuous mode. This feature is not yet fully implemented.")
        run_once(limit=args.limit, dry_run=args.dry_run, skip_browser=args.skip_browser)

    return 0

if __name__ == "__main__":
    sys.exit(main())
