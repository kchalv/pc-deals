@echo off
rem Manual run: scans all Greek stores and opens the deals page.
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
cd /d "%~dp0"
python "%~dp0pc_deals.py" %*
start "" http://127.0.0.1:8765/
