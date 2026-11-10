@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.13 -m venv .venv
  if errorlevel 1 goto fail
)
if not exist ".venv\.dependencies-ready" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
  type nul > ".venv\.dependencies-ready"
)
".venv\Scripts\python.exe" -X utf8 setup_workbench.py
if errorlevel 1 goto fail
start "" ".venv\Scripts\pythonw.exe" app.py
popd
exit /b 0
:fail
echo Setup failed. See README.md for Python 3.13 and Save Editor 4.2.1 requirements.
pause
popd
exit /b 1
