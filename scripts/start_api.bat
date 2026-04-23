@echo off
setlocal

set "PROJECT_ROOT=D:\Python\projetos\gmail_linkedin\linkedin_gmail_jobs_hub"
set "CONDA_BAT=D:\Python\anaconda3\Scripts\activate.bat"
set "CONDA_ENV=linkedin_gmail_jobs_hub"

call "%CONDA_BAT%"
call conda activate "%CONDA_ENV%"
cd /d "%PROJECT_ROOT%"

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
