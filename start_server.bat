@echo off
title AI Parametric CAD & CNC CAM Studio - Port 9000
echo =================================================================
echo   AI Parametric CAD & CNC CAM Studio (FreeCAD 1.1 + OpenCV)
echo   Repository Commit: b1e8e7d
echo   Starting Dedicated Local Hosting on http://localhost:9000 ...
echo =================================================================

cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" http://localhost:9000
python server.py
pause
