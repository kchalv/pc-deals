@echo off
rem Starts the local deals page (http://127.0.0.1:8765/) hidden. Run at logon by "PC Deals Server".
cd /d "%~dp0"
start "" /b "C:\Python310\pythonw.exe" "%~dp0server.py"
