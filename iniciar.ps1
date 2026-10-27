$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Primero crear el entorno e instalar dependencias siguiendo README.md.'
}
& '.\.venv\Scripts\python.exe' manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron aplicar las migraciones.' }
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
