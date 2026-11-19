param([int]$Port=8765,[string]$DataDir='',[switch]$Desktop)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'Немає .venv. Створіть середовище Python та встановіть пакет: pip install -e ".[web]". Див. https://obscurawriter.com/install.html'
    exit 1
}
if (-not $DataDir) { $DataDir=Join-Path $projectRoot 'data' }
$envFile=Join-Path $projectRoot '.env'
if ($Desktop) {
    # Як застосунок зі Store: окреме вікно й значок у треї, без консолі; порт застосунок вибирає сам.
    if ($PSBoundParameters.ContainsKey('Port')) { Write-Warning '-Port не діє з -Desktop: застосунок сам бере вільний порт (адреса в server.json).' }
    $pythonwPath=Join-Path $projectRoot '.venv/Scripts/pythonw.exe'
    Start-Process -FilePath $pythonwPath -ArgumentList @('-m','storygen.desktop','--data-dir',"`"$DataDir`"",'--env-file',"`"$envFile`"")
    Write-Host "Obscura запускається у власному вікні; значок у треї. Журнал: $(Join-Path $DataDir 'logs\obscura.log')"
    exit 0
}
& $pythonPath -m storygen.server --data-dir $DataDir --env-file $envFile --port $Port --open-browser
exit $LASTEXITCODE
