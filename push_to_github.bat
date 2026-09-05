@echo off
title Push to GitHub
echo ============================================================
echo   Pushing ApexQuant to GitHub:
echo   https://github.com/softsideof/Automatic-trading-bot
echo ============================================================
echo.
set "GIT_EXE=C:\Users\Legion\AppData\Local\GitHubDesktop\app-3.6.5\resources\app\git\cmd\git.exe"

"%GIT_EXE%" push -u origin main

echo.
echo If a GitHub authentication popup appeared, please complete sign-in.
pause
