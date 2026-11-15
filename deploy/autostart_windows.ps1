# Регистрация задач в планировщике Windows: бот, notify и API стартуют
# при загрузке системы (даже без входа в Windows) и перезапускаются,
# если процесс был убит.
#
# Запуск от администратора:
#   powershell -ExecutionPolicy Bypass -File deploy\autostart_windows.ps1
#
# Удалить задачи:
#   powershell -ExecutionPolicy Bypass -File deploy\autostart_windows.ps1 -Remove

param([switch]$Remove)

$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source

$tasks = @(
    @{ Name = "SupportBot-Discord"; Args = "run_forever.py discord_bot/bot.py" },
    @{ Name = "SupportBot-Notify";  Args = "run_forever.py notify.py" },
    @{ Name = "SupportBot-API";     Args = "run_forever.py flask_api.py" }
)

if ($Remove) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Удалена задача: $($t.Name)"
    }
    return
}

foreach ($t in $tasks) {
    $action = New-ScheduledTaskAction -Execute $Python `
        -Argument $t.Args -WorkingDirectory $Root

    $trigger = New-ScheduledTaskTrigger -AtStartup

    # Перезапуск, если процесс всё-таки убили (watchdog делает основную работу)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

    Register-ScheduledTask -TaskName $t.Name -Action $action `
        -Trigger $trigger -Settings $settings -User "SYSTEM" `
        -RunLevel Highest -Force | Out-Null

    Write-Host "Зарегистрирована задача: $($t.Name)"
}

Write-Host ""
Write-Host "Готово. Проверка: taskschd.msc"
Write-Host "Запустить прямо сейчас: Start-ScheduledTask -TaskName 'SupportBot-Discord'"
