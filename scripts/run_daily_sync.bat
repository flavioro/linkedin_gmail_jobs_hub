@echo off
setlocal

set "PROJECT_ROOT=D:\Python\projetos\gmail_linkedin\linkedin_gmail_jobs_hub"
set "CONDA_BAT=D:\Python\anaconda3\Scripts\activate.bat"
set "CONDA_ENV=linkedin_gmail_jobs_hub"
set "LOG_DIR=%PROJECT_ROOT%\logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call "%CONDA_BAT%"
call conda activate "%CONDA_ENV%"
cd /d "%PROJECT_ROOT%"

python "%PROJECT_ROOT%\run_daily_sync.py" >> "%LOG_DIR%\run_daily_sync.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [%date% %time%] Erro na sincronizacao. Codigo=%EXIT_CODE% >> "%LOG_DIR%\run_daily_sync.log"
)

endlocal & exit /b %EXIT_CODE%
