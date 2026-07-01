@echo off
title OEM Price Lookup
echo.
echo ============================================
echo  OEM Price Lookup — oempartsonline.com
echo ============================================
echo.
echo IMPORTANT: Close cotizacion_bulk.xlsm before running.
echo.

python "%~dp0oem_lookup.py"

echo.
echo ============================================
echo  Done! Open cotizacion_bulk.xlsm to review
echo  columns Z-AC (OEM_MSRP, OEM_PRECIO, etc.)
echo ============================================
echo.
pause
