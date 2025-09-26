import pytest
from unittest.mock import MagicMock
import requests

# src ディレクトリをパスに追加
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import anki_client
from src import config
from src.gemini_client import ProcessedWord, ProcessedSentence

@pytest.fixture
def mock_requests(mocker):
    """Fixture to mock requests.post."""
    return mocker.patch("requests.post")

def test_format_word_note():
    """
    Test the format_word_note function to ensure it creates the correct
    Anki note structure from a ProcessedWord object.
    """
    word_data = ProcessedWord(
        english_word="Test",
        example_sentence="This is a test.",
        japanese_meaning="テスト",
        example_translation="これはテストです。"
    )

    note = anki_client.format_word_note(word_data)

    assert note["deckName"] == config.ANKI_WORD_DECK_NAME
    assert note["modelName"] == config.ANKI_WORD_NOTE_TYPE
    assert note["fields"]["単語"] == "Test"
    assert note["fields"]["フレーズ"] == "This is a test."
    assert note["fields"]["意味"] == "テスト"
    assert note["fields"]["フレーズの意味"] == "これはテストです。"
    assert "allowDuplicate" in note["options"]

def test_format_sentence_note():
    """
    Test the format_sentence_note function to ensure it creates the correct
    Anki note structure from a ProcessedSentence object.
    """
    sentence_data = ProcessedSentence(
        japanese_sentence="こんにちは",
        english_sentence="Hello"
    )

    note = anki_client.format_sentence_note(sentence_data)

    assert note["deckName"] == config.ANKI_SENTENCE_DECK_NAME
    assert note["modelName"] == config.ANKI_SENTENCE_NOTE_TYPE
    assert note["fields"]["Front"] == "こんにちは"
    assert note["fields"]["Back"] == "Hello"
    assert "allowDuplicate" in note["options"]

def test_add_note_success(mock_requests):
    """
    Test add_note for a successful API call.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": 123, "error": None}
    mock_response.raise_for_status.return_value = None
    mock_requests.return_value = mock_response

    note = {"deckName": "Test Deck", "modelName": "Test Model", "fields": {}}
    result = anki_client.add_note(note)

    mock_requests.assert_called_once_with(
        config.ANKICONNECT_URL,
        json={"action": "addNote", "version": 6, "params": {"note": note}},
        timeout=30
    )
    assert result == 123

def test_add_note_api_error(mock_requests):
    """
    Test add_note when AnkiConnect returns an error.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": None, "error": "Deck not found"}
    mock_response.raise_for_status.return_value = None
    mock_requests.return_value = mock_response

    note = {"deckName": "Non-existent Deck", "modelName": "Test Model", "fields": {}}

    with pytest.raises(RuntimeError, match="AnkiConnect error: Deck not found"):
        anki_client._invoke("addNote", {"note": note})

def test_add_note_request_exception(mock_requests):
    """
    Test add_note when a requests exception occurs.
    """
    mock_requests.side_effect = requests.exceptions.Timeout("Connection timed out")

    note = {"fields": {}}
    result = anki_client.add_note(note)

    assert result is None

def test_ensure_deck_and_model(mock_requests):
    """
    Test that ensure_deck_and_model calls the 'createDeck' action.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": None, "error": None}
    mock_response.raise_for_status.return_value = None
    mock_requests.return_value = mock_response

    anki_client.ensure_deck_and_model("New Deck", "Some Model")

    mock_requests.assert_called_with(
        config.ANKICONNECT_URL,
        json={"action": "createDeck", "version": 6, "params": {"deck": "New Deck"}},
        timeout=30
    )
