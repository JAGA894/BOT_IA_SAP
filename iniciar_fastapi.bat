@echo off
title [1] FastAPI - Bot CxC
color 0B
echo ============================================
echo   BOT CxC - FASTAPI WEBHOOK (Puerto 8000)
echo ============================================
cd /d c:\Users\Sistemas\Desktop\BOT_IA_HANA
call venv\Scripts\activate.bat
python bot_app.py
echo.
echo *** El proceso termino. Revisa el error arriba ***
pause
