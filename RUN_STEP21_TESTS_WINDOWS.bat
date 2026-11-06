@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo  CHEMI Step 21 - Local regression tests
 echo =============================================
where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON=py -3"
) else (
  set "PYTHON=python"
)
%PYTHON% -m unittest discover -p "test_*.py" -v
if errorlevel 1 goto fail
echo.
where node >nul 2>&1
if errorlevel 1 (
  echo Node.js is not installed. JavaScript checks skipped.
  goto done
)
node test_step14_interaction.js
if errorlevel 1 goto fail
node test_step16_requests_ui.js
if errorlevel 1 goto fail
node test_step19_invite.js
if errorlevel 1 goto fail
node test_step22_demo_request.js
if errorlevel 1 goto fail
:done
echo.
echo All available local checks completed.
pause
exit /b 0
:fail
echo.
echo FAILED. Please send the last error line, without credentials.
pause
exit /b 1
