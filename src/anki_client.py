from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict # TypedDictを追加

import requests

from . import config
from .gemini_client import ProcessedItem, ProcessedWord, ProcessedSentence # Import ProcessedItem and its sub-types


logger = logging.getLogger(__name__)

# TypedDict for Anki Note Fields
class AnkiFields(TypedDict):
    単語: str
    フレーズ: str
    意味: str
    フレーズの意味: str
    単語音声: str
    フレーズ音声: str

class AnkiSentenceFields(TypedDict):
    Front: str
    Back: str

# TypedDict for Anki Note Structure
class AnkiNote(TypedDict):
    deckName: str
    modelName: str
    fields: AnkiFields | AnkiSentenceFields
    options: Dict[str, Any]


def _invoke(action: str, params: Optional[Dict[str, Any]] = None) -> Any:
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    resp = requests.post(config.ANKICONNECT_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        # エラーメッセージをより詳細にする
        error_message = data["error"]
        logger.error("AnkiConnect error for action '%s': %s", action, error_message)
        raise RuntimeError(f"AnkiConnect error: {error_message}")
    return data.get("result")


def ensure_deck_and_model(deck_name: str, model_name: str) -> None:
    _invoke("createDeck", {"deck": deck_name})
    # Model creation is not attempted here; assume existing model


def format_word_note(word_data: ProcessedWord) -> AnkiNote: # 型ヒントを更新
    """
    Formats a ProcessedWord into an Anki note structure.
    Assumes a note type with 'Front', 'Back', 'ExampleSentence', 'ExampleSentenceTranslation' fields.
    """
    return {
        "deckName": config.ANKI_WORD_DECK_NAME,
        "modelName": config.ANKI_WORD_NOTE_TYPE,
        "fields": {
            "単語": word_data.english_word,
            "フレーズ": word_data.example_sentence,
            "意味": word_data.japanese_meaning,
            "フレーズの意味": word_data.example_translation,
            "単語音声": "",
            "フレーズ音声": "",
        },
        "options": {"allowDuplicate": True},
    }

def format_sentence_note(sentence_data: ProcessedSentence) -> AnkiNote: # 型ヒントを更新
    """
    Formats a ProcessedSentence into an Anki note structure.
    Assumes a note type with 'Front' and 'Back' fields (e.g., for English sentence on front, Japanese on back).
    """
    return {
        "deckName": config.ANKI_SENTENCE_DECK_NAME,
        "modelName": config.ANKI_SENTENCE_NOTE_TYPE,
        "fields": {
            "Front": sentence_data.japanese_sentence,
            "Back": sentence_data.english_sentence,
        },
        "options": {"allowDuplicate": True},
    }

def add_note(note: AnkiNote) -> Optional[int]: # 型ヒントを更新
    """
    Adds a single Anki note.
    Returns the note ID for the successfully created note, or None for failure.
    """
    logger.info("Attempting to add single note to AnkiConnect: Deck='%s', Model='%s'",
                note.get("deckName"), note.get("modelName"))
    try:
        result = _invoke("addNote", {"note": note})
        if result:
            logger.info("Successfully added note to AnkiConnect. Note ID: %s", result)
        else:
            logger.warning("AnkiConnect returned no ID for the added note. Result: %s", result)
        return result
    except Exception as e:
        logger.error("Failed to add note to AnkiConnect: %s", e)
        return None
