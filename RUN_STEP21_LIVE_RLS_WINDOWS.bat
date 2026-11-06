@echo off
setlocal
cd /d "%~dp0"
echo CHEMI - Read-only Supabase RLS check with 2 real test accounts
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 LIVE_RLS_CHECK.py
) else (
  python LIVE_RLS_CHECK.py
)
echo.
pause
