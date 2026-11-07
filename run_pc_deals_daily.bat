@echo off
rem Obsolete: replaced by the hourly task "PC Deals Hourly" (pythonw pc_deals.py --log logs\hourly_YYYY-MM-DD.log).
rem Kept so an old shortcut still works.
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python "%~dp0pc_deals.py" --log "%~dp0logs\manual.log"
