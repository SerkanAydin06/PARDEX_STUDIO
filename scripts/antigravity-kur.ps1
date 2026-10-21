$ErrorActionPreference = 'Stop'
# Official Google installer; invoked only after the owner's install action.
$installer = Join-Path ([IO.Path]::GetTempPath()) ('pardex-agy-' + [guid]::NewGuid().ToString() + '.ps1')
try {
  Invoke-WebRequest -Uri 'https://antigravity.google/cli/install.ps1' -OutFile $installer -UseBasicParsing
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
  if ($LASTEXITCODE -ne 0) { throw 'Antigravity CLI kurulumu basarisiz.' }
} finally {
  Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
}
