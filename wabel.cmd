@echo off
REM lecture-scribe driver. Keep this file ASCII only (cmd.exe reads .cmd as ANSI).
REM Point PY at the python of the venv you installed requirements.txt into.
set PY=python
"%PY%" "%~dp0tools\pipeline.py" %*
