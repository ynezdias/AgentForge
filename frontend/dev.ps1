$ErrorActionPreference = 'Stop'
$portableNodePath = Join-Path $PSScriptRoot '..\.tools\node-v24.22.3-win-x64'
if (Test-Path (Join-Path $portableNodePath 'node.exe')) {
    $env:PATH = "$portableNodePath;$env:PATH"
}
Push-Location $PSScriptRoot
try {
    & npm.cmd run dev
} finally {
    Pop-Location
}
