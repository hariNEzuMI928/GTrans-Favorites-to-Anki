"""
anki_mature_to_sheets.py

AnkiデータベースからMature（ivl >= 21）カードを抽出し、
Google Sheetsへ全入れ替えで同期するスクリプト。

対象デッキ:
  - 1_Vocabulary       → index 0 (表面) → "words" タブ
  - 2_EnglishComposition → index 1 (裏面) → "sentence" タブ

Usage:
  python -m src.anki_mature_to_sheets
"""

import argparse
import logging
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================================================
# ⚙️  Config
# ============================================================
SERVICE_ACCOUNT_FILE: str = "data/service_account.json"
SPREADSHEET_ID: str = "1cWV8jg6Obh93NV7OWwJ03MU_N3mu1IAZUa82_Zpmqp8"
ANKI_COLLECTION_PATH: str = str(
    Path.home() / "Library/Application Support/Anki2/ユーザー 1/collection.anki2"
)

# Mature カードの最小間隔日数
MATURE_THRESHOLD: int = 21

# デッキごとの設定: (検索用デッキ名, flds の index, Sheets タブ名)
# startswith で検索するため、前方一致する全てのデッキが対象となります。
DECK_CONFIGS: List[Tuple[str, int, str]] = [
    ("1_Vocabulary",           0, "words"),     # 表面
    ("2_EnglishComposition",   1, "sentence"),  # 裏面
]

# Google Sheets API スコープ
SCOPES: List[str] = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# スプレッドシートのヘッダー行
HEADER: List[str] = ["Content"]
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("anki_mature_to_sheets")


def strip_html(text: str) -> str:
    """HTMLタグとエンティティを除去してプレーンテキストを返す。"""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def fetch_mature_cards(
    db_path: str,
    deck_name_prefix: str,
    field_index: int,
    mature_threshold: int = MATURE_THRESHOLD,
) -> List[str]:
    """指定デッキ（前方一致）から Mature カードの内容を抽出する。"""
    results: List[str] = []
    db_uri = f"file:{db_path}?mode=ro"

    try:
        con = sqlite3.connect(db_uri, uri=True)
        # Anki 独自の unicase コリレーションを登録
        con.create_collation("unicase", lambda a, b: (a.lower() > b.lower()) - (a.lower() < b.lower()))
    except sqlite3.OperationalError as e:
        logger.error(f"DB 接続失敗: {e}")
        raise

    with con:
        cur = con.cursor()

        # デッキ ID を収集 (前方一致)
        cur.execute("SELECT id, name FROM decks WHERE name LIKE ?", (deck_name_prefix + "%",))
        target_dids = []
        for did, name in cur.fetchall():
            target_dids.append(did)
            logger.info(f"  対象デッキ検出: '{name}' (did={did})")

        if not target_dids:
            logger.warning(f"デッキ '{deck_name_prefix}' に一致するものがありません。")
            return results

        placeholders = ",".join("?" * len(target_dids))
        query = f"""
            SELECT n.flds
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.did IN ({placeholders})
              AND c.ivl >= ?
              AND c.queue >= 0
            ORDER BY c.ivl DESC
        """
        cur.execute(query, target_dids + [mature_threshold])
        rows = cur.fetchall()

    logger.info(f"  '{deck_name_prefix}' (前方一致) から {len(rows)} 件の Mature カードを取得")

    for (flds_raw,) in rows:
        fields = flds_raw.split("\x1f")
        if field_index < len(fields):
            content = strip_html(fields[field_index])
            if content:
                results.append(content)

    return results


def sync_to_sheet(
    client: gspread.Client,
    spreadsheet_id: str,
    tab_name: str,
    data: List[str],
    dry_run: bool = False,
) -> None:
    """指定タブを全削除してからデータを書き込む。"""
    if dry_run:
        logger.info(f"[DRY-RUN] '{tab_name}' タブへ {len(data)} 行を書き込む予定")
        return

    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1, cols=1)

    worksheet.clear()
    rows = [[HEADER[0]]] + [[item] for item in data]
    worksheet.update(rows, value_input_option="RAW")
    logger.info(f"  '{tab_name}' タブへ {len(data)} 行を書き込みました。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anki Mature カードを Google Sheets へ同期します。")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES))

    for deck_name, field_index, tab_name in DECK_CONFIGS:
        logger.info("-" * 60)
        logger.info(f"処理中: '{deck_name}' → '{tab_name}'")
        
        cards = fetch_mature_cards(ANKI_COLLECTION_PATH, deck_name, field_index)
        if cards:
            sync_to_sheet(client, SPREADSHEET_ID, tab_name, cards, args.dry_run)
        else:
            logger.info("  対象カードなし。")

    logger.info("✅ 同期完了。")


if __name__ == "__main__":
    main()
