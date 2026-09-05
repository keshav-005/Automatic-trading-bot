@echo off
title ApexQuant - Unit Tests
echo ============================================================
echo   ApexQuant: Running Automated Unit Test Suite
echo ============================================================
echo.
python -m unittest discover -s tests -p "test_*.py" -v
pause
