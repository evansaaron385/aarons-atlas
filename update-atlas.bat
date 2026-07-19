@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: creating the Atlas photo environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

echo Checking photo importer requirements...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

echo.
".venv\Scripts\python.exe" python\build_atlas.py
if errorlevel 1 goto :error

echo.
echo Update complete. Refresh Aaron's Atlas in your browser.
pause
exit /b 0

:error
echo.
echo The Atlas update did not finish. Review the error above.
pause
exit /b 1
