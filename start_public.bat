@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "Supplier Workbench" cmd /c run_server.bat
timeout /t 4 >nul
echo.
echo 正在建立公网隧道（bore.pub）...
echo 终端会打印 listening at bore.pub:PORT，浏览器打开 http://bore.pub:PORT
echo 保持此窗口不要关闭。
echo.
set "BORE=%~dp0tools\bore\bore.exe"
if not exist "%BORE%" set "BORE=%~dp0bore\bore.exe"
if not exist "%BORE%" (
  echo 未找到 bore.exe。请把 bore.exe 放到 tools\bore\ 或根目录，或从 https://github.com/ekzhang/bore/releases 下载。
  pause
  exit /b 1
)
"%BORE%" local 8000 --to bore.pub
