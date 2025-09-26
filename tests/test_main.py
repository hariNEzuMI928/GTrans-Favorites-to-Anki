import pytest
from unittest.mock import MagicMock, patch, call

# src ディレクトリをパスに追加
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import run_once
from src.scraper import FavoriteItem
from src.gemini_client import ProcessedItem, ProcessedWord

@pytest.fixture
def mock_dependencies(mocker):
    """Fixture to mock all external dependencies for main.py."""
    mocks = {
        'load_ids': mocker.patch('src.main.load_ids'),
        'save_ids': mocker.patch('src.main.save_ids'),
        'fetch_favorites': mocker.patch('src.main.fetch_favorites'),
        'delete_favorite_item': mocker.patch('src.main.delete_favorite_item'),
        'GeminiProcessor': mocker.patch('src.main.GeminiProcessor'),
        'add_note': mocker.patch('src.main.add_note'),
        'ensure_deck_and_model': mocker.patch('src.main.ensure_deck_and_model'),
        'format_word_note': mocker.patch('src.main.format_word_note'),
    }

    # Mock the return value for the GeminiProcessor instance's method
    mock_gemini_instance = mocks['GeminiProcessor'].return_value
    mock_gemini_instance.process_item = MagicMock()
    mocks['process_item'] = mock_gemini_instance.process_item

    return mocks

def test_run_once_happy_path(mock_dependencies, mocker): # Added mocker fixture
    """Test a standard run where new items are found, processed, and saved."""
    # Arrange
    mock_dependencies['load_ids'].return_value = set()
    new_items = [FavoriteItem(text='new', translation='新しい', item_id='1')]
    mock_dependencies['fetch_favorites'].return_value = new_items

    processed_item = ProcessedItem(item_id='1', type='word', data=ProcessedWord('new', 'ex', '新しい', 'ex_trans'))
    mock_dependencies['process_item'].return_value = processed_item

    mock_dependencies['format_word_note'].return_value = {"fields": {}}
    mock_dependencies['add_note'].return_value = 12345 # Success
    mock_dependencies['delete_favorite_item'].return_value = True

    # Act
    run_once(limit=10, dry_run=False, skip_browser=False)

    # Assert
    mock_dependencies['load_ids'].assert_called_once()
    mock_dependencies['fetch_favorites'].assert_called_once()
    mock_dependencies['process_item'].assert_called_once_with(new_items[0])
    mock_dependencies['add_note'].assert_called_once()
    mock_dependencies['save_ids'].assert_called_once_with(mocker.ANY, {'1'})
    mock_dependencies['delete_favorite_item'].assert_called_once_with(new_items[0])

def test_run_once_dry_run(mock_dependencies):
    """Test that a dry run fetches and processes but does not save or delete."""
    # Arrange
    mock_dependencies['load_ids'].return_value = set()
    new_items = [FavoriteItem(text='new', translation='新しい', item_id='1')]
    mock_dependencies['fetch_favorites'].return_value = new_items

    processed_item = ProcessedItem(item_id='1', type='word', data=ProcessedWord('new', 'ex', '新しい', 'ex_trans'))
    mock_dependencies['process_item'].return_value = processed_item
    mock_dependencies['format_word_note'].return_value = {"fields": {}}

    # Act
    run_once(limit=10, dry_run=True, skip_browser=False)

    # Assert
    mock_dependencies['load_ids'].assert_called_once()
    mock_dependencies['fetch_favorites'].assert_called_once()
    mock_dependencies['process_item'].assert_called_once()

    # These should NOT be called in a dry run
    mock_dependencies['add_note'].assert_not_called()
    mock_dependencies['save_ids'].assert_not_called()
    mock_dependencies['delete_favorite_item'].assert_not_called()

def test_run_once_cleans_up_stale_items(mock_dependencies):
    """Test that stale items (processed but not deleted) are cleaned up."""
    # Arrange
    mock_dependencies['load_ids'].return_value = {'1'}
    stale_item = FavoriteItem(text='stale', translation='古い', item_id='1')

    # fetch_favorites is called, finds a stale item, then is called again after cleanup.
    mock_dependencies['fetch_favorites'].side_effect = [
        [stale_item],  # First call returns the stale item
        []             # Second call returns an empty list
    ]
    mock_dependencies['delete_favorite_item'].return_value = True

    # Act
    run_once(limit=10, dry_run=False, skip_browser=False)

    # Assert
    mock_dependencies['load_ids'].assert_called_once()

    # It should fetch, find stale item, delete it, then fetch again
    expected_fetch_calls = [call(limit=10), call(limit=10)]
    mock_dependencies['fetch_favorites'].assert_has_calls(expected_fetch_calls)
    assert mock_dependencies['fetch_favorites'].call_count == 2

    mock_dependencies['delete_favorite_item'].assert_called_once_with(stale_item)

    # Since there are no new items after cleanup, processing should not occur
    mock_dependencies['process_item'].assert_not_called()
    mock_dependencies['add_note'].assert_not_called()
    # save_ids is only called when new items are successfully added to Anki
    mock_dependencies['save_ids'].assert_not_called()

def test_run_once_skip_browser(mock_dependencies):
    """Test that browser operations are skipped with the --skip-browser flag."""
    # Arrange
    mock_dependencies['load_ids'].return_value = set()

    # Act
    run_once(limit=10, dry_run=False, skip_browser=True)

    # Assert
    mock_dependencies['load_ids'].assert_called_once()

    # Browser operations should be skipped
    mock_dependencies['fetch_favorites'].assert_not_called()
    mock_dependencies['delete_favorite_item'].assert_not_called()

    # Since no items are fetched, nothing else should happen
    mock_dependencies['process_item'].assert_not_called()
    mock_dependencies['add_note'].assert_not_called()
    mock_dependencies['save_ids'].assert_not_called()
