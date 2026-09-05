@echo off
title ApexQuant - Historical Backtest
echo ============================================================
echo   ApexQuant: Executing Quantitative Historical Backtest
echo ============================================================
echo.
python main.py --mode backtest --bars 200
pause
