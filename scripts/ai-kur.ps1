$ErrorActionPreference='Stop'
Write-Host '=== Ultra Pro - AI CLI Araclari ===' -ForegroundColor Cyan
Write-Host 'Claude Code, Codex, Gemini ve istege bagli Copilot CLI - resmi npm paketleri.'
Write-Host 'Bu islem mevcut Node.js surumune ve internete ihtiyac duyar.'
Write-Host 'Hicbir API anahtari kaydedilmez. Abonelik hesabiniza daha sonra kendiniz girersiniz.'
$npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if (-not $npm) {Write-Host 'Node.js/npm bulunamadi. Resmi: https://nodejs.org/en/download' -ForegroundColor Yellow;exit 1}
$ans=Read-Host 'Uc resmi AI CLI paketini yuklemek veya guncellemek icin EVET yaz'
if ($ans -eq 'EVET') {
  foreach ($pkg in @('@openai/codex','@google/gemini-cli','@anthropic-ai/claude-code')) {
    Write-Host "Yukleniyor: $pkg" -ForegroundColor Cyan
    & $npm.Source install -g "$pkg@latest"
    if ($LASTEXITCODE -ne 0) {Write-Host "UYARI: $pkg kurulumu basarisiz. Digerlerine geciliyor." -ForegroundColor Yellow}
  }
}
$copilot = Read-Host 'Copilot Pro CLI kurmak/guncellemek icin EVET yaz (istege bagli)'
if ($copilot -eq 'EVET') {
  $nodeVersion = & node --version
  if ($LASTEXITCODE -ne 0 -or -not $nodeVersion -or [int]($nodeVersion.TrimStart('v').Split('.')[0]) -lt 22) {
    Write-Host 'Copilot CLI icin Node.js 22+ gerekir: https://nodejs.org/en/download' -ForegroundColor Yellow
  } else {
    & $npm.Source install -g '@github/copilot@latest'
    if ($LASTEXITCODE -ne 0) {Write-Host 'Copilot CLI kurulumu basarisiz.' -ForegroundColor Yellow}
    else {Write-Host 'PowerShell 6+ ile copilot login calistirip Copilot Pro hesabina gir.' -ForegroundColor Green}
  }
}
Write-Host 'Bitti. PARDEX Sirket Merkezi Model yonlendirme ekraninda CLI durumunu kontrol et.' -ForegroundColor Green
