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

# Ankiアプリケーションを起動
log INFO "Ankiを起動します..."

open -a Anki
sleep 10

# Pythonスクリプトを実行
log INFO "Pythonスクリプトを実行中..."
/usr/bin/python3 -m src.main --once

# スクリプトの完了後、Ankiを終了
log INFO "Ankiを終了します..."
# osascript -e 'quit app "Anki"' || log ERROR "Anki終了に失敗しました"
# osascript -e 'tell application "Anki" to quit' || log ERROR "Anki終了に失敗しました"
osascript -e 'tell application "Anki" to quit saving no' || log ERROR "Anki終了に失敗しました"

log INFO "処理が完了しました。"
