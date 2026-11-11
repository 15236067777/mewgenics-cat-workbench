@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo 请先运行 Start.cmd 完成初始化，再运行这个助手。
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -X utf8 f3_start.py
popd
