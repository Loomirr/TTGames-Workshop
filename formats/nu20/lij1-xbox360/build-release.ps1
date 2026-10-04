$ErrorActionPreference = 'Stop'
$toolRoot = $PSScriptRoot
$projectPath = Join-Path $toolRoot 'Source\LIJ1TextureExtractor.csproj'
$publishPath = Join-Path $toolRoot 'dist'
dotnet publish $projectPath -c Release -o $publishPath --ignore-failed-sources
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }

$releaseRoot = Join-Path $toolRoot 'Release'
$projectXml = [xml](Get-Content -LiteralPath $projectPath -Raw)
$toolVersion = $projectXml.Project.PropertyGroup.Version
$packageName = "LIJ1_360_Texture_Extractor_v${toolVersion}_win64"
$packagePath = Join-Path $releaseRoot $packageName
if (Test-Path -LiteralPath $packagePath) { throw "Package folder already exists: $packagePath. Use a new package/version or move the existing package first." }
New-Item -ItemType Directory -Path $packagePath -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $publishPath 'LIJ1_360_Texture_Extractor.exe') -Destination $packagePath
foreach ($name in @('README.md', 'FORMAT.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.txt', 'build-release.ps1')) {
    Copy-Item -LiteralPath (Join-Path $toolRoot $name) -Destination $packagePath
}
$sourceDestination = Join-Path $packagePath 'Source'
New-Item -ItemType Directory -Path $sourceDestination | Out-Null
Get-ChildItem -LiteralPath (Join-Path $toolRoot 'Source') -File | Where-Object { $_.Extension -in @('.cs', '.csproj') } | Copy-Item -Destination $sourceDestination
$testsDestination = Join-Path $packagePath 'Tests'
New-Item -ItemType Directory -Path $testsDestination | Out-Null
Copy-Item -LiteralPath (Join-Path $toolRoot 'Tests\verify_samples.py') -Destination $testsDestination
Copy-Item -LiteralPath (Join-Path $toolRoot 'Tests\verify_variants.py') -Destination $testsDestination
$parserTestsDestination = Join-Path $testsDestination 'ParserChecks'
New-Item -ItemType Directory -Path $parserTestsDestination | Out-Null
foreach ($name in @('ParserChecks.csproj', 'Program.cs')) {
    Copy-Item -LiteralPath (Join-Path $toolRoot "Tests\ParserChecks\$name") -Destination $parserTestsDestination
}
$researchDestination = Join-Path $packagePath 'Research'
New-Item -ItemType Directory -Path $researchDestination | Out-Null
Copy-Item -LiteralPath (Join-Path $toolRoot 'Research\probe.py') -Destination $researchDestination
# Local sample manifests are deliberately not included in the source package.
$dotnetRoot = Split-Path -Parent (Get-Command dotnet).Source
Copy-Item -LiteralPath (Join-Path $dotnetRoot 'LICENSE.txt') -Destination (Join-Path $packagePath 'Runtime_LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $dotnetRoot 'ThirdPartyNotices.txt') -Destination (Join-Path $packagePath 'Runtime_ThirdPartyNotices.txt')

Compress-Archive -LiteralPath $packagePath -DestinationPath (Join-Path $releaseRoot ($packageName + '.zip')) -CompressionLevel Optimal
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $packagePath 'LIJ1_360_Texture_Extractor.exe'), (Join-Path $releaseRoot ($packageName + '.zip')) | Format-Table -AutoSize
