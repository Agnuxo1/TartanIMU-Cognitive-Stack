param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "JEV runtime missing: $Python"
    exit 2
}
$env:JEV_ORCHESTRATOR_ROOT = $Root
$env:JEV_CALLER_CWD = (Get-Location).Path
$ExitCode = 0
Push-Location -LiteralPath $Root
try {
    & $Python -m jev_orchestrator.connection @Arguments
    $ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $ExitCode
