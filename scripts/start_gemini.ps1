# Start only the local SearchRank-AI stack. No key is written to disk or printed.
[CmdletBinding()]
param(
    [switch]$FreeTierConfirmed,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
if (-not $FreeTierConfirmed) {
    throw 'First verify Free tier in AI Studio and no paid billing. Then pass -FreeTierConfirmed.'
}
$taskKey = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($taskKey)) {
    $taskKey = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User')
}
if ([string]::IsNullOrWhiteSpace($taskKey)) {
    throw 'Save GEMINI_API_KEY in your private Windows user environment first.'
}
$taskSettings = @{
    GEMINI_API_KEY = $taskKey.Trim()
    SEARCHRANK_LLM_PROVIDER = 'gemini'
    SEARCHRANK_LLM_MODEL = 'gemini-3.1-flash-lite'
    SEARCHRANK_GEMINI_FREE_TIER_CONFIRMED = '1'
}
$taskPrevious = @{}
foreach ($taskName in $taskSettings.Keys) {
    $taskPrevious[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
}
Push-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
try {
    foreach ($taskName in $taskSettings.Keys) {
        [Environment]::SetEnvironmentVariable($taskName, $taskSettings[$taskName], 'Process')
    }
    $taskArgs = @('compose', 'up', '-d')
    if ($Build) { $taskArgs += '--build' }
    $taskArgs += @('api', 'ui')
    & docker @taskArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker startup failed. Check Docker Desktop; do not print resolved Compose secrets.'
    }
    Write-Output 'SearchRank-AI started with Gemini. Open http://127.0.0.1:8501/.'
    Write-Output 'Free-tier confirmation is not a billing API check. Do not enable paid billing.'
}
finally {
    foreach ($taskName in $taskPrevious.Keys) {
        [Environment]::SetEnvironmentVariable($taskName, $taskPrevious[$taskName], 'Process')
    }
    $taskKey = $null
    $taskSettings.Clear()
    $taskPrevious.Clear()
    Pop-Location
}
