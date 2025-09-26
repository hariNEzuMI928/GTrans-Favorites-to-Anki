import pytest
import json
from unittest.mock import MagicMock
from google.api_core.exceptions import GoogleAPIError

# src ディレクトリをパスに追加
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gemini_client import GeminiProcessor, ProcessedWord, ProcessedSentence, ProcessedItem
from src.scraper import FavoriteItem

@pytest.fixture
def mock_genai(mocker):
    """Fixture to mock the google.generativeai library."""
    mock_genai_lib = mocker.patch('src.gemini_client.genai')

    # Mock the configure and GenerativeModel parts
    mock_genai_lib.configure = MagicMock()
    mock_model = MagicMock()
    mock_genai_lib.GenerativeModel.return_value = mock_model

    return mock_genai_lib, mock_model

@pytest.fixture
def gemini_processor(mocker, mock_genai):
    """Fixture to provide an instance of GeminiProcessor with a mocked API key."""
    mocker.patch('src.config.GEMINI_API_KEY', 'fake-api-key')
    return GeminiProcessor()

def test_init_raises_error_if_no_api_key(mocker):
    """Test that GeminiProcessor raises a RuntimeError if the API key is missing."""
    mocker.patch('src.config.GEMINI_API_KEY', '')
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set in .env"):
        GeminiProcessor()

def test_process_item_word_success(gemini_processor, mock_genai):
    """Test successful processing of a 'word' item."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="Ephemeral", translation="はかない", item_id="123")

    response_data = {
        "type": "word",
        "data": {
            "english_word": "Ephemeral",
            "example_sentence": "The beauty of cherry blossoms is ephemeral.",
            "japanese_meaning": "はかない、つかの間の",
            "example_translation": "桜の美しさははかない。"
        }
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_data)
    mock_model.generate_content.return_value = mock_response

    result = gemini_processor.process_item(favorite_item)

    assert isinstance(result, ProcessedItem)
    assert result.type == "word"
    assert isinstance(result.data, ProcessedWord)
    assert result.data.english_word == "Ephemeral"
    mock_model.generate_content.assert_called_once()

def test_process_item_sentence_success(gemini_processor, mock_genai):
    """Test successful processing of a 'sentence' item."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="How are you?", translation="お元気ですか？", item_id="456")

    response_data = {
        "type": "sentence",
        "data": {
            "japanese_sentence": "お元気ですか？",
            "english_sentence": "How are you?"
        }
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_data)
    mock_model.generate_content.return_value = mock_response

    result = gemini_processor.process_item(favorite_item)

    assert isinstance(result, ProcessedItem)
    assert result.type == "sentence"
    assert isinstance(result.data, ProcessedSentence)
    assert result.data.english_sentence == "How are you?"

def test_process_item_json_decode_error(gemini_processor, mock_genai):
    """Test that None is returned if the API response is not valid JSON."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="Test", translation="テスト", item_id="789")

    mock_response = MagicMock()
    mock_response.text = "This is not JSON"
    mock_model.generate_content.return_value = mock_response

    result = gemini_processor.process_item(favorite_item)
    assert result is None

def test_process_item_google_api_error(gemini_processor, mock_genai):
    """Test that None is returned if a GoogleAPIError occurs."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="Test", translation="テスト", item_id="abc")

    mock_model.generate_content.side_effect = GoogleAPIError("API limit reached")

    result = gemini_processor.process_item(favorite_item)
    assert result is None

def test_process_item_missing_keys_in_response(gemini_processor, mock_genai):
    """Test that None is returned if the JSON response is missing required keys."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="Test", translation="テスト", item_id="def")

    # Missing 'data' key
    response_data = {"type": "word"}
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_data)
    mock_model.generate_content.return_value = mock_response

    result = gemini_processor.process_item(favorite_item)
    assert result is None

def test_process_item_with_markdown_cleanup(gemini_processor, mock_genai):
    """Test if the client correctly handles JSON wrapped in markdown code blocks."""
    _, mock_model = mock_genai
    favorite_item = FavoriteItem(text="Test", translation="テスト", item_id="123")

    response_data = {
        "type": "word",
        "data": {"english_word": "Cleaned", "example_sentence": "", "japanese_meaning": "", "example_translation": ""}
    }
    json_string = json.dumps(response_data)
    markdown_response = f"```json\n{json_string}\n```"

    mock_response = MagicMock()
    mock_response.text = markdown_response
    mock_model.generate_content.return_value = mock_response

    result = gemini_processor.process_item(favorite_item)
    assert result is not None
    assert result.type == "word"
    assert result.data.english_word == "Cleaned"
