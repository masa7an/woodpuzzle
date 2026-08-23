@echo off
cd /d "%~dp0"

rem Use the venv python directly. Do not use activate.bat: it only checks
rem that the folder exists, so it reports success even when the base
rem interpreter is gone.
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Create it first:
    echo     py -3.12 -m venv venv
    echo     venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo ========================================
echo  Building Web Version with Pygbag
echo ========================================
echo.

rem NOTE: keep this file ASCII-only. cmd.exe reads .bat as CP932 on JP Windows,
rem so UTF-8 Japanese comments corrupt the parser and break the script.

rem Clean previous build.
rem The mkdir is required: pygbag opens build\web\<app>.apk with mode="x" and
rem does not create the folder itself, so it crashes if build\web is missing.
if exist "build\web" (
    echo Cleaning previous build...
    rmdir /s /q "build\web"
)
if not exist "build\web" mkdir "build\web"

rem --- IMPORTANT ---
rem Stash the root woodpazzule.apk (the artifact GitHub Pages serves) before building.
rem pygbag packs the whole project folder and does NOT skip .apk
rem (see pygbag/filtering.py SKIP_EXT). Leaving it in place nests the old apk
rem inside the new one and roughly doubles its size (3.6MB -> 7.1MB).
rem .bak IS in SKIP_EXT, so renaming keeps it out of the bundle.
if exist "woodpazzule.apk" (
    echo Stashing root woodpazzule.apk so it is not packed into itself...
    move /y "woodpazzule.apk" "woodpazzule.apk.bak" >nul
)

"venv\Scripts\python.exe" -m pygbag --build .
set BUILD_RC=%ERRORLEVEL%

rem Always restore the stashed apk, even if the build failed
if exist "woodpazzule.apk.bak" (
    move /y "woodpazzule.apk.bak" "woodpazzule.apk" >nul
)

if not "%BUILD_RC%"=="0" (
    echo.
    echo *** Build FAILED ***
    pause
    exit /b %BUILD_RC%
)

echo.
echo Injecting GA4 tag...
"venv\Scripts\python.exe" assets\scripts\inject_ga4.py

echo.
echo ========================================
echo  Build Complete: build\web\
echo ========================================
echo.
echo  Test locally : run.bat  (pygbag dev server, http://localhost:8000/)
echo  Deploy       : copy build\web\* to the repo root, then git push
echo.
pause
