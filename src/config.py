import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Union, Literal


# Load environment variables from .env file if present
load_dotenv()


# Directories
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"

# Ensure DATA_DIR exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_PATH: Path = DATA_DIR / "auth_state.json"
PROCESSED_IDS_PATH: Path = DATA_DIR / "processed_ids.json"
APP_LOG_PATH: Path = DATA_DIR / "app.log"


# External services
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# AnkiConnect
ANKICONNECT_URL: str = os.environ.get("ANKICONNECT_URL", "http://localhost:8765")
ANKI_WORD_DECK_NAME: str = os.environ.get(
    "ANKI_WORD_DECK_NAME", "Default"
)  # デフォルト値を設定
ANKI_SENTENCE_DECK_NAME: str = os.environ.get(
    "ANKI_SENTENCE_DECK_NAME", "Default"
)  # デフォルト値を設定
ANKI_WORD_NOTE_TYPE: str = os.environ.get(
    "ANKI_WORD_NOTE_TYPE", "Basic"
)  # デフォルト値を設定
ANKI_SENTENCE_NOTE_TYPE: str = os.environ.get(
    "ANKI_SENTENCE_NOTE_TYPE", "Basic"
)  # デフォルト値を設定

# Google Translate
GOOGLE_TRANSLATE_FAVORITES_URL: str = os.environ.get(
    "GOOGLE_TRANSLATE_FAVORITES_URL",
    "https://translate.google.com/saved",
)
# 環境変数の値が文字列 "true", "1", "yes" のいずれかであればTrue、それ以外はFalse
PLAYWRIGHT_HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() in (
    "1",
    "true",
    "yes",
)
PLAYWRIGHT_USER_AGENT: str = os.environ.get(
    "PLAYWRIGHT_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
)

# Runtime behavior
DEFAULT_BATCH_LIMIT: int = int(os.environ.get("BATCH_LIMIT", "50"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()  # 新しく追加
