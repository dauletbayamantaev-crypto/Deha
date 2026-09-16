@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ──────────────────────────────────────
echo   TZ bot
echo ──────────────────────────────────────

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python topilmadi.
    echo     python.org/downloads saytidan o'rnating.
    echo     O'rnatishda "Add Python to PATH" katagini belgilang.
    pause
    exit /b 1
)

if not exist .venv (
    echo - Birinchi ishga tushirish: muhit tayyorlanmoqda...
    python -m venv .venv
)

echo - Kutubxonalar tekshirilmoqda...
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt

if not exist .env (
    echo.
    set /p BOT_TOKEN_INPUT=BotFather bergan tokenni kiriting: 
    if "%BOT_TOKEN_INPUT%"=="" (
        echo [X] Token kiritilmadi.
        pause
        exit /b 1
    )
    .venv\Scripts\python -c "import os,pathlib;t=os.environ['BOT_TOKEN_INPUT'].strip();lines=pathlib.Path('.env.example').read_text(encoding='utf-8').splitlines();pathlib.Path('.env').write_text('\n'.join(('BOT_TOKEN='+t) if l.startswith('BOT_TOKEN=') else l for l in lines)+'\n',encoding='utf-8');print('[OK] Token .env fayliga saqlandi.')"
)

echo.
echo - Bot ishga tushmoqda. To'xtatish: Ctrl+C
echo.
.venv\Scripts\python main.py
pause
