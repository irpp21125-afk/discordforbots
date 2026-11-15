@echo off
REM ============================================================
REM  Сборка SupportBotPanel.exe из desktop\app.py
REM  Требуется: Python 3.10+ и pip
REM ============================================================

cd /d "%~dp0.."

echo [1/3] Установка PyInstaller...
python -m pip install --upgrade pip
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo [2/3] Сборка .exe (это займёт 1-3 минуты)...
pyinstaller --clean --noconfirm desktop\app.spec
if errorlevel 1 goto :error

echo [3/3] Готово!
echo.
echo   Экзешник: dist\SupportBotPanel.exe
echo   Далее запустите installer\build_installer.bat для установщика.
echo.
pause
exit /b 0

:error
echo.
echo ОШИБКА сборки. См. сообщения выше.
pause
exit /b 1
