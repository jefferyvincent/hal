$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Gamer\hal-voice'
$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"`n=== HAL starting $ts ===" | Add-Content -Path 'hal.log' -Encoding utf8
& '.\.venv\Scripts\python.exe' -u 'server.py' *>> 'hal.log'
