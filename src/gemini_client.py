from __future__ import annotations

import logging
import json
import time
from typing import Dict, List, Literal, Any, TypedDict
from dataclasses import dataclass

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

from . import config
from .scraper import FavoriteItem # Import FavoriteItem from scraper

logger = logging.getLogger(__name__)

# TypedDict for the expected JSON output from Gemini
class WordData(TypedDict):
    english_word: str
    example_sentence: str
    japanese_meaning: str
    example_translation: str

class SentenceData(TypedDict):
    japanese_sentence: str
    english_sentence: str

class GeminiOutput(TypedDict):
    type: Literal["word", "sentence"]
    data: WordData | SentenceData

@dataclass
class ProcessedWord:
    english_word: str
    example_sentence: str
    japanese_meaning: str
    example_translation: str

@dataclass
class ProcessedSentence:
    japanese_sentence: str
    english_sentence: str

@dataclass
class ProcessedItem:
    item_id: str
    type: Literal["word", "sentence"]
    data: ProcessedWord | ProcessedSentence

class GeminiProcessor:
    def __init__(self) -> None:
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        genai.configure(api_key=api_key)  # pyright: ignore [reportPrivateImportUsage]
        self.model = genai.GenerativeModel(config.GEMINI_MODEL)  # pyright: ignore [reportPrivateImportUsage]

    def process_item(self, item: FavoriteItem, retry_count: int = 0) -> ProcessedItem | None:
        MAX_RETRIES = 3
        
        prompt = f"""Developer: Given an English/Japanese text and its translation from Google Translate favorites:

- **Text:** {item.text}
- **Translated Text:** {item.translation}

Begin with a concise checklist (3-7 bullets) of what you will do; keep items conceptual, not implementation-level.

Your task:
1. Determine if the text is a 'word/phrase' (not a complete sentence) or a 'sentence' (complete grammatical sentence).
2. If it is a 'word/phrase':
    - Extract the word or phrase.
    - Provide a natural, contextually relevant example sentence using the word or phrase.
    - Give its Japanese meaning.
    - Give the Japanese translation of the example sentence.
3. If it is a 'sentence':
    - Extract the sentence.
    - Provide its Japanese translation (from the item). Do not generate additional examples.

Respond with only a JSON object in this format:

# Output Format
{{
  "type": "word" | "sentence",
  "data": {{ ... }}
}}


Output schema:
- For a 'word/phrase':
  {{
    "type": "word",
    "data": {{
      "english_word": \"<string>\",
      "example_sentence": \"<string>\",
      "japanese_meaning": \"<string>\",
      "example_translation": \"<string>\"
    }}
  }}
- For a 'sentence':
  {{
    "type": "sentence",
    "data": {{
      "english_sentence": \"<string>\",
      "japanese_sentence": \"<string>\"
    }}
  }}

Return only the JSON result. Do not include any additional text.
"""
        response_text = ""
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            json_output = response_text.strip()

            # Clean up potential markdown formatting if Gemini includes it
            if json_output.startswith("```json") and json_output.endswith("```"):
                json_output = json_output[7:-3].strip()

            # Attempt to find the first '{' and the last '}' to extract the raw JSON string.
            try:
                start_index = json_output.index('{')
                end_index = json_output.rindex('}')
                json_output = json_output[start_index:end_index + 1]
            except ValueError:
                logger.error("Could not find a valid JSON object boundary ('{' and '}') in the response for item_id: %s", item.item_id)
                return None

            # Use TypedDict for better type checking
            data: GeminiOutput = json.loads(json_output)

            item_type = data.get("type")
            item_data = data.get("data")

            if not item_type or not item_data:
                logger.warning("Gemini response missing 'type' or 'data' for item_id: %s. Response: %s", item.item_id, json_output)
                return None

            if item_type == "word":
                # Ensure all expected keys are present with default empty strings
                processed_word = ProcessedWord(
                    english_word=item_data.get("english_word", ""),
                    example_sentence=item_data.get("example_sentence", ""),
                    japanese_meaning=item_data.get("japanese_meaning", ""),
                    example_translation=item_data.get("example_translation", "")
                )
                return ProcessedItem(item_id=item.item_id, type="word", data=processed_word)
            elif item_type == "sentence":
                # Ensure all expected keys are present with default empty strings
                processed_sentence = ProcessedSentence(
                    japanese_sentence=item_data.get("japanese_sentence", ""),
                    english_sentence=item_data.get("english_sentence", "")
                )
                return ProcessedItem(item_id=item.item_id, type="sentence", data=processed_sentence)
            else:
                logger.warning("Unknown item type received from Gemini: %s for item_id: %s. Response: %s", item_type, item.item_id, json_output)
                return None

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini JSON response for item_id %s: %s\nResponse text: %s", item.item_id, e, response_text)
            return None
        except GoogleAPIError as e:
            logger.error("Gemini API error for item_id %s: %s", item.item_id, e)
            
            # Check for rate limit error (HTTP 429) and implement retry logic
            if "429" in str(e) and retry_count < MAX_RETRIES:
                import re
                retry_delay = 5.0 # Default fallback delay
                
                # Attempt to extract precise retry delay from the error message
                if hasattr(e, "message"):
                    match = re.search(r"Please retry in (\d+\.\d+)s", str(e))
                    if match:
                        retry_delay = float(match.group(1))

                logger.info("Rate limit exceeded (429). Retrying item_id: %s in %.2f seconds (Attempt %d/%d).", 
                            item.item_id, retry_delay, retry_count + 1, MAX_RETRIES)
                time.sleep(retry_delay + 1) # Add a small buffer
                return self.process_item(item, retry_count + 1) # Recursive retry
            
            return None
        except Exception as e:
            logger.error("Unexpected error during Gemini processing for item_id %s: %s", item.item_id, e)
            return None
