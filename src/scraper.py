from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright, Browser, TimeoutError
import hashlib

from . import config

logger = logging.getLogger(__name__)


@dataclass
class FavoriteItem:
    text: str
    translation: str
    item_id: str # A unique ID for the item (e.g., hash of text + translation)


class Scraper:
    def __init__(self) -> None:
        self.selectors: Dict[str, str] = self._load_selectors(config.BASE_DIR / "src" / "selectors.json")

    def _load_selectors(self, file_path: Path) -> Dict[str, str]:
        """Loads CSS selectors from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _new_context(self, pw: Playwright, manual_login: bool) -> Tuple[BrowserContext, Browser]:
        """Creates a new Playwright browser context with common options."""
        user_agent: str = config.PLAYWRIGHT_USER_AGENT
        headless: bool = not manual_login if manual_login else config.PLAYWRIGHT_HEADLESS

        browser: Browser = pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context_options: Dict[str, Any] = {
            "user_agent": user_agent,
            "ignore_https_errors": True,
        }

        config.DATA_DIR.mkdir(parents=True, exist_ok=True)

        if config.AUTH_STATE_PATH.exists():
            logger.info("Loading existing auth state from %s", config.AUTH_STATE_PATH)
            context_options["storage_state"] = str(config.AUTH_STATE_PATH)

        context: BrowserContext = browser.new_context(**context_options)
        return context, browser

    def ensure_logged_in(self, manual_login: bool = False, timeout_sec: int = 300) -> None:
        """Ensures the user is logged into Google Translate favorites."""
        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login=manual_login)
            page: Page = context.new_page()
            try:
                logger.info("Opening favorites page for login check...")
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)
                logger.info("Current URL after navigation: %s", page.url)

                if manual_login:
                    logger.info("Manual login mode: please authenticate in the opened browser.")
                    input("Press Enter when you have finished logging in and the favorites page is loaded...")

                ready_selector: str = f"{self.selectors['favorites_container']}, {self.selectors['empty_state_indicator']}"
                logger.info("Waiting for page to be ready (either list or empty state)...")
                page.locator(ready_selector).first.wait_for(timeout=timeout_sec * 1000)
                logger.info("Page is ready. Saving auth state.")

                context.storage_state(path=str(config.AUTH_STATE_PATH))
                logger.info("Saved auth state to %s", config.AUTH_STATE_PATH)

            except TimeoutError as e:
                logger.error("Timeout during login check/setup: %s", e)
                screenshot_path = config.DATA_DIR / "error_ensure_logged_in_timeout.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                raise
            except Exception as e:
                logger.error("Error during login check/setup: %s", e, exc_info=True)
                screenshot_path = config.DATA_DIR / "error_ensure_logged_in.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                raise
            finally:
                page.close()
                context.close()
                browser.close()

    def fetch_favorites(self, limit: Optional[int] = None) -> List[FavoriteItem]:
        """Fetches favorite items from Google Translate."""
        items: List[FavoriteItem] = []

        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login=False)
            page: Page = context.new_page()

            try:
                logger.info("Navigating to favorites page...")
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)
                logger.info("Current URL after navigation: %s", page.url)

                ready_selector: str = f"{self.selectors['favorites_container']}, {self.selectors['empty_state_indicator']}"
                logger.info("Waiting for page content (either list or empty state)...")
                page.locator(ready_selector).first.wait_for(timeout=30000)
                logger.info("Page content is ready.")

                empty_state_locator = page.locator(self.selectors["empty_state_indicator"])
                if empty_state_locator.count() > 0:
                    logger.info("Empty state indicator found. No favorite items to process.")
                    return []

                logger.info("Extracting favorite items...")
                favorite_elements = page.locator(self.selectors["favorite_item"]).all()
                logger.info("Found %d favorite items.", len(favorite_elements))

                for i, element in enumerate(favorite_elements):
                    if limit and i >= limit:
                        logger.info("Reached limit of %d items. Stopping scraping.", limit)
                        break

                    try:
                        text_element = element.locator(self.selectors["favorite_item_text"]).first
                        translation_element = element.locator(self.selectors["favorite_item_translation"]).first

                        text = text_element.inner_text().strip() if text_element else ""
                        translation = translation_element.inner_text().strip() if translation_element else ""

                        if text and translation:
                            item_id = hashlib.sha256(f"{text}-{translation}".encode()).hexdigest()
                            items.append(FavoriteItem(text=text, translation=translation, item_id=item_id))
                        else:
                            logger.warning(
                                "Skipping item due to missing text or translation: Text='%s', Translation='%s'",
                                text,
                                translation,
                            )

                    except Exception as e:
                        logger.error("Error extracting data from favorite item %d: %s", i, e)
                        continue

            except TimeoutError as e:
                logger.error("Timeout during fetching favorites: %s", e)
                screenshot_path = config.DATA_DIR / "error_fetch_favorites_timeout.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                return []
            except Exception as e:
                logger.error("Error during fetching favorites: %s", e, exc_info=True)
                screenshot_path = config.DATA_DIR / "error_fetch_favorites.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                return []
            finally:
                page.close()
                context.close()
                browser.close()

            return items

    def delete_favorite_item(self, item: FavoriteItem) -> bool:
        """Deletes a specific item from Google Translate favorites."""
        with sync_playwright() as pw:
            context, browser = self._new_context(pw, manual_login=False)
            page: Page = context.new_page()

            try:
                logger.info("Navigating to favorites page to delete item: %s", item.text)
                page.goto(config.GOOGLE_TRANSLATE_FAVORITES_URL, wait_until="domcontentloaded", timeout=60000)

                # Use a more robust selector for the item, escaping quotes in item.text
                escaped_item_text = item.text.replace('"', '\\"')
                item_selector: str = f"{self.selectors['favorite_item']}:has-text(\"{escaped_item_text}\")"
                logger.info("Attempting to find item with selector: %s", item_selector)

                target_item_locator = page.locator(item_selector).first
                target_item_locator.wait_for(state="visible", timeout=30000)

                if target_item_locator.count() == 0:
                    logger.warning("Item to delete not found: %s", item.text)
                    return False

                delete_button = target_item_locator.locator(self.selectors['favorite_item_delete_button']).first
                delete_button.wait_for(state="visible", timeout=10000)
                delete_button.click()

                logger.info("Successfully clicked delete button for item: %s", item.text)

                target_item_locator.wait_for(state="hidden", timeout=10000)
                logger.info("Item %s successfully deleted and removed from DOM.", item.text)
                return True

            except TimeoutError as e:
                logger.error("Timeout during deleting item %s: %s", item.text, e)
                screenshot_path = config.DATA_DIR / f"error_delete_item_timeout_{item.item_id[:8]}.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                return False
            except Exception as e:
                logger.error("Error deleting item %s: %s", item.text, e, exc_info=True)
                screenshot_path = config.DATA_DIR / f"error_delete_item_{item.item_id[:8]}.png"
                page.screenshot(path=str(screenshot_path))
                logger.error("Screenshot saved to %s", screenshot_path)
                return False
            finally:
                page.close()
                context.close()
                browser.close()

# Global scraper instance for backward compatibility with existing calls
_global_scraper = Scraper()
ensure_logged_in = _global_scraper.ensure_logged_in
fetch_favorites = _global_scraper.fetch_favorites
delete_favorite_item = _global_scraper.delete_favorite_item
