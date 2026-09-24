[CmdletBinding()]
param(
    [ValidateSet('Shared', 'OpenCode', 'Both')]
    [string]$Target = 'Both'
)

$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) {
    throw "Skill source is incomplete: $source"
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'scripts\extract_opencode_session.py') -PathType Leaf)) {
    throw "Extractor source is missing: $source"
}

$targets = switch ($Target) {
    'Shared' { Join-Path $env:USERPROFILE '.agents\skills\opencode-session-extract' }
    'OpenCode' { Join-Path $env:USERPROFILE '.config\opencode\skills\opencode-session-extract' }
    'Both' {
        Join-Path $env:USERPROFILE '.agents\skills\opencode-session-extract'
        Join-Path $env:USERPROFILE '.config\opencode\skills\opencode-session-extract'
    }
}

$results = foreach ($destination in $targets) {
    $skillParent = Split-Path -Parent $destination
    $backup = $null
    if (Test-Path -LiteralPath $destination -PathType Container) {
        $backupParent = Join-Path $skillParent '.backups'
        $backup = Join-Path $backupParent "opencode-session-extract-$timestamp"
        New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    }

    New-Item -ItemType Directory -Path (Join-Path $destination 'scripts') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'SKILL.md') -Destination (Join-Path $destination 'SKILL.md') -Force
    Copy-Item -LiteralPath (Join-Path $source 'scripts\extract_opencode_session.py') `
        -Destination (Join-Path $destination 'scripts\extract_opencode_session.py') -Force

    [ordered]@{
        installed = $destination
        backup = $backup
        hashes_match = @('SKILL.md', 'scripts\extract_opencode_session.py') | ForEach-Object {
            (Get-FileHash -LiteralPath (Join-Path $source $_) -Algorithm SHA256).Hash -eq
                (Get-FileHash -LiteralPath (Join-Path $destination $_) -Algorithm SHA256).Hash
        } | Where-Object { -not $_ } | Measure-Object | Select-Object -ExpandProperty Count | ForEach-Object { $_ -eq 0 }
    }
}

$results | ConvertTo-Json -Depth 4
