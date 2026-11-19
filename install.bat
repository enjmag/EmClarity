@echo off
REM EmClarity one-click installer. Add  -WithResemble  to also install the optional Resemble Enhance engine.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
