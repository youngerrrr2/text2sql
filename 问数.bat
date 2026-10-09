@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting text2sql UI (Streamlit)...
.venv\Scripts\python.exe -m streamlit run app.py
echo.
echo UI stopped.
pause
