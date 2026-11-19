@echo off
setlocal
REM EmClarity - drag audio/video files or folders onto this file.
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo EmClarity is not installed yet. Run install.bat first.
  pause & exit /b 1
)
if "%~1"=="" (
  echo Drag audio or video files ^(or a folder^) onto Enhance.bat.
  echo.
  "%PY%" -m emclarity --list
  pause & exit /b 0
)

echo.
echo  EmClarity - choose a preset (auto-picks 1 in 15s):
echo    1  VO Clean         gentle denoise, voice untouched (default)
echo    2  Strong Denoise   removes all steady noise, voice untouched
echo    3  Noisy Room       music/TV/crowd behind the voice (+ saves background)
echo    4  Rescue           rebuilds the voice - ONLY for bad recordings
echo    5  Rescue Resemble  alternative rebuild for A/B (optional engine)
echo    6  Compare          run 1, 2 and 4 for side-by-side listening
echo.
choice /c 123456 /n /t 15 /d 1 /m "Preset [1-6]: "
set "SEL=%errorlevel%"

set "HF_HUB_OFFLINE=1"
pushd "%ROOT%"
if "%SEL%"=="1" "%PY%" -m emclarity -p vo_clean %*
if "%SEL%"=="2" "%PY%" -m emclarity -p strong_denoise %*
if "%SEL%"=="3" "%PY%" -m emclarity -p noisy_room %*
if "%SEL%"=="4" "%PY%" -m emclarity -p rescue %*
if "%SEL%"=="5" "%PY%" -m emclarity -p rescue_resemble %*
if "%SEL%"=="6" (
  "%PY%" -m emclarity -p vo_clean %*
  "%PY%" -m emclarity -p strong_denoise %*
  "%PY%" -m emclarity -p rescue %*
)
popd
echo.
pause
