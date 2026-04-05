"""
anki_mature_to_sheets.py

AnkiデータベースからMature（ivl >= 21）カードを抽出し、
Google Sheetsへ全入れ替えで同期するスクリプト。

対象デッキ:
  - 1_Vocabulary       → index 0 (表面) → "words" タブ
  - 2_EnglishComposition → index 1 (裏面) → "sentence" タブ

Usage:
  python -m src.scripts.anki_mature_to_sheets
"""

import argparse
import logging
import re
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


from ..core.anki_client import find_cards, cards_info

def fetch_mature_cards(
    deck_name_prefix: str,
    field_index: int,
    mature_threshold: int = MATURE_THRESHOLD,
) -> List[str]:
    """指定デッキ（前方一致）から Mature カードの内容を抽出する (AnkiConnect経由)。"""
    results: List[str] = []
    
    # AnkiConnect 用のクエリを作成 (前方一致デッキ名 & 間隔条件)
    # queue >= 0 (通常キュー) も含めるなら prop:queue>=0 も追加可能ですが、
    # ivl >= X であれば通常はアクティブです。
    query = f'deck:"{deck_name_prefix}*" prop:ivl>={mature_threshold}'
    
    try:
        card_ids = find_cards(query)
        if not card_ids:
            logger.info(f"  対象カードなし: '{deck_name_prefix}*'")
            return results

        logger.info(f"  '{deck_name_prefix}*' から {len(card_ids)} 件の Mature カードを取得中...")
        
        # 情報を一括取得
        cards_data = cards_info(card_ids)
        
        for card in cards_data:
            model_name = card.get("modelName", "")
            fields = card.get("fields", {})
            # フィールドを order の順に並べる
            sorted_fields = sorted(fields.items(), key=lambda x: x[1]["order"])
            
            # デッキとノートタイプに応じたフィールド index の調整
            # (英作文デッキで「基本_単語」を使っている場合のみ、index 1 ではなく 2 (意味) を見る)
            actual_index = field_index
            if "EnglishComposition" in deck_name_prefix and model_name == "基本_単語":
                actual_index = 2 # 「意味」フィールド
                
            if actual_index < len(sorted_fields):
                raw_value = sorted_fields[actual_index][1]["value"]
                content = strip_html(raw_value)
                if content:
                    results.append(content)
                    
        # 重複排除 (順序を維持)
        results = list(dict.fromkeys(results))
        logger.info(f"  結果: {len(results)} 件のユニークなアイテムを抽出")

    except Exception as e:
        logger.error(f"AnkiConnect からのデータ取得失敗: {e}")
        # スケジューラ実行中など、Anki未起動の場合はエラーを上げる
        raise

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
        
        cards = fetch_mature_cards(deck_name, field_index)
        if cards:
            sync_to_sheet(client, SPREADSHEET_ID, tab_name, cards, args.dry_run)
        else:
            logger.info("  対象カードなし。")

    logger.info("✅ 同期完了。")


if __name__ == "__main__":
    main()
