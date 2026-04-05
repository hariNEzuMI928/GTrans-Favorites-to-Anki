#!/bin/bash

log() {
    # $1 = level, $2 = message, $3 = module(optional)
    local level=$1
    local msg=$2
    local module=${3:-anki_scheduler}  # デフォルトは "anki_scheduler"
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "$ts | $level | $module | $msg"
}

# スクリプトのあるディレクトリに移動
cd "$(dirname "$0")" || exit

# 週次同期（日曜日に実行）
if [ "$(date +%u)" -eq 7 ]; then
    log INFO "週次の Google Sheets 同期を開始します (Mature カード)..."
    .venv/bin/python3 -m src.scripts.anki_mature_to_sheets
fi

# Ankiアプリケーションを起動
log INFO "Ankiを起動します..."

open -a Anki
sleep 10

# Pythonスクリプトを実行
log INFO "Pythonスクリプトを実行中..."
.venv/bin/python3 -m src.main --once

# スクリプトの完了後、Ankiを終了
log INFO "Ankiを終了します..."
# osascript -e 'quit app "Anki"' || log ERROR "Anki終了に失敗しました"
# osascript -e 'tell application "Anki" to quit' || log ERROR "Anki終了に失敗しました"
osascript -e 'tell application "Anki" to quit saving no' || log ERROR "Anki終了に失敗しました"

log INFO "処理が完了しました。"
