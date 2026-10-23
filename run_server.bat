@echo off
setlocal
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================================
echo  Supplier Document Workbench
echo  http://127.0.0.1:8000
echo ============================================================
start "" "http://127.0.0.1:8000"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
