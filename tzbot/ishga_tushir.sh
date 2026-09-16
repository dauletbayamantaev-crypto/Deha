#!/usr/bin/env bash
# TZ botini ishga tushiradi. Mac va Linux uchun.
# Terminalda: bash ishga_tushir.sh
set -e
cd "$(dirname "$0")"

echo "──────────────────────────────────────"
echo "  TZ bot"
echo "──────────────────────────────────────"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python topilmadi."
    echo "   python.org/downloads saytidan o'rnating va shu faylni qayta ishga tushiring."
    exit 1
fi

if [ ! -d .venv ]; then
    echo "→ Birinchi ishga tushirish: muhit tayyorlanmoqda..."
    python3 -m venv .venv
fi

echo "→ Kutubxonalar tekshirilmoqda..."
./.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt

if [ ! -f .env ]; then
    echo
    echo "BotFather bergan tokenni kiriting."
    echo "(Yozganingiz ko'rinmaydi — bu normal, yozib Enter bosing)"
    printf "Token: "
    read -r -s BOT_TOKEN_INPUT
    echo
    if [ -z "$BOT_TOKEN_INPUT" ]; then
        echo "❌ Token kiritilmadi."
        exit 1
    fi
    BOT_TOKEN_INPUT="$BOT_TOKEN_INPUT" ./.venv/bin/python - <<'PY'
import os
import pathlib

token = os.environ["BOT_TOKEN_INPUT"].strip()
lines = pathlib.Path(".env.example").read_text().splitlines()
updated = [f"BOT_TOKEN={token}" if line.startswith("BOT_TOKEN=") else line for line in lines]
pathlib.Path(".env").write_text("\n".join(updated) + "\n")
print("✅ Token .env fayliga saqlandi.")
PY
fi

echo
echo "→ Bot ishga tushmoqda. To'xtatish: Ctrl+C"
echo
exec ./.venv/bin/python main.py
