param(
  [string]$ZipPath = "C:\Users\david someone\Downloads\magenta-main.zip",
  [string]$Destination = "external"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if ([System.IO.Path]::IsPathRooted($Destination)) {
  $resolvedDestination = $Destination
} else {
  $resolvedDestination = Join-Path $repoRoot $Destination
}
$resolvedZip = Resolve-Path -LiteralPath $ZipPath

New-Item -ItemType Directory -Force -Path $resolvedDestination | Out-Null
tar -xf $resolvedZip -C $resolvedDestination

$magentaPath = Join-Path $resolvedDestination "magenta-main"
Write-Output "Magenta source extracted to: $magentaPath"
Write-Output "Keep this sandbox isolated from backend/app and the production FastAPI runtime."
