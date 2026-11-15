@echo off
REM ============================================================
REM  Сборка установщика SupportBotPanel_Setup.exe
REM  1. Сначала запустите build_exe.bat
REM  2. Затем этот скрипт
REM  Требуется: Inno Setup 6 (https://jrsoftware.org/isinfo.php)
REM ============================================================

cd /d "%~dp0.."

echo [1/2] Проверяю dist\SupportBotPanel.exe...
if not exist "dist\SupportBotPanel.exe" (
    echo   ОШИБКА: .exe не найден. Сначала запустите build_exe.bat
    pause
    exit /b 1
)

echo [2/2] Сборка установщика...
"Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  УСТАНОВЩИК ГОТОВ: installer\SupportBotPanel_Setup.exe
echo ============================================================
echo.
echo Его можно отправить на хостинг или раздать пользователям.
echo.
pause
exit /b 0

:error
echo.
echo ОШИБКА сборки установщика.
echo Убедитесь, что Inno Setup 6 установлен.
pause
exit /b 1
