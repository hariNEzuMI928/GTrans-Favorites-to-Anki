import json
from unittest.mock import MagicMock, patch
import pytest
from src.core.gemini_client import GeminiProcessor, ProcessedWord, ProcessedSentence, FavoriteItem

@pytest.fixture
def mock_genai():
    with patch("google.generativeai.configure"):
        with patch("google.generativeai.GenerativeModel") as mock_model:
            yield mock_model

@pytest.fixture
def processor(mock_genai):
    with patch("src.utils.config.GEMINI_API_KEY", "test_key"):
        return GeminiProcessor()

def test_process_item_word(processor, mock_genai):
    # Mock response for a word
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "type": "word",
        "data": {
            "english_word": "test",
            "example_sentence": "This is a test.",
            "japanese_meaning": "テスト",
            "example_translation": "これはテストです。"
        }
    })
    processor.model.generate_content.return_value = mock_response
    
    item = FavoriteItem(text="test", translation="テスト", item_id="123")
    result = processor.process_item(item)
    
    assert result.type == "word"
    assert isinstance(result.data, ProcessedWord)
    assert result.data.english_word == "test"
    assert result.data.japanese_meaning == "テスト"

def test_process_item_sentence(processor, mock_genai):
    # Mock response for a sentence
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "type": "sentence",
        "data": {
            "english_sentence": "I go to school.",
            "japanese_sentence": "学校へ行きます。"
        }
    })
    processor.model.generate_content.return_value = mock_response
    
    item = FavoriteItem(text="I go to school.", translation="学校へ行きます。", item_id="456")
    result = processor.process_item(item)
    
    assert result.type == "sentence"
    assert isinstance(result.data, ProcessedSentence)
    assert result.data.english_sentence == "I go to school."
    assert result.data.japanese_sentence == "学校へ行きます。"

def test_process_item_malformed_json(processor, mock_genai):
    mock_response = MagicMock()
    mock_response.text = "this is not json"
    processor.model.generate_content.return_value = mock_response
    
    item = FavoriteItem(text="test", translation="テスト", item_id="123")
    result = processor.process_item(item)
    
    assert result is None

def test_process_item_boundary_extraction(processor, mock_genai):
    # Gemini sometimes adds extra text or markdown
    mock_response = MagicMock()
    mock_response.text = """Markdown prefix
```json
{
  "type": "word",
  "data": {
    "english_word": "test",
    "example_sentence": "test",
    "japanese_meaning": "test",
    "example_translation": "test"
  }
}
```
Markdown suffix"""
    processor.model.generate_content.return_value = mock_response
    
    item = FavoriteItem(text="test", translation="test", item_id="123")
    result = processor.process_item(item)
    
    assert result is not None
    assert result.type == "word"
