import json
import logging
from pathlib import Path
from typing import Iterable, Set, List, Any

logger = logging.getLogger(__name__)


def load_ids(path: Path) -> Set[str]:
    """Loads a set of IDs from a JSON file."""
    if not path.exists():
        logger.info("ID file not found at %s. Returning empty set.", path)
        return set()
    try:
        with path.open("r", encoding="utf-8") as f:
            data: Any = json.load(f)
            if isinstance(data, list):
                return set(str(x) for x in data)
            logger.warning("Content of %s is not a list. Returning empty set.", path)
            return set()
    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON from %s: %s", path, e)
        return set()
    except IOError as e:
        logger.error("IO error while reading %s: %s", path, e)
        return set()
    except Exception as e:
        logger.error("Unexpected error while loading IDs from %s: %s", path, e)
        return set()


def save_ids(path: Path, ids: Iterable[str]) -> None:
    """Saves a set of IDs to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            # Ensure the IDs are sorted for consistent file content
            sorted_ids: List[str] = sorted(list(set(ids)))
            json.dump(sorted_ids, f, ensure_ascii=False, indent=2)
        logger.info("Successfully saved %d IDs to %s.", len(sorted_ids), path)
    except IOError as e:
        logger.error("IO error while writing to %s: %s", path, e)
    except Exception as e:
        logger.error("Unexpected error while saving IDs to %s: %s", path, e)


