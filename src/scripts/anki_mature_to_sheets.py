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
import gspread
import logging
import re
import sys
from typing import List, Tuple

from ..utils import config
from ..utils.logging_setup import setup_logging
from ..core.anki_client import find_cards, cards_info

# ============================================================
# ⚙️  Config
# ============================================================
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

logger = logging.getLogger("anki_mature_to_sheets")


def strip_html(text: str) -> str:
    """HTMLタグとエンティティを除去してプレーンテキストを返す。"""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean




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
    logger.info("  '%s' タブへ %d 行を書き込みました。", tab_name, len(data))


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Anki Mature カードを Google Sheets へ同期します。")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        if not config.SERVICE_ACCOUNT_PATH.exists():
             logger.error("Service account file not found at %s", config.SERVICE_ACCOUNT_PATH)
             sys.exit(1)
        client = gspread.service_account(filename=str(config.SERVICE_ACCOUNT_PATH))

    for deck_name, field_index, tab_name in DECK_CONFIGS:
        logger.info("-" * 60)
        logger.info("処理中: '%s' → '%s'", deck_name, tab_name)
        
        cards = fetch_mature_cards(deck_name, field_index)
        if cards:
            sync_to_sheet(client, config.SPREADSHEET_ID, tab_name, cards, args.dry_run)
        else:
            logger.info("  対象カードなし。")

    logger.info("✅ 同期完了。")


if __name__ == "__main__":
    main()
