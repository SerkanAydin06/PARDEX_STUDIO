$ErrorActionPreference='Stop'
Write-Host '=== Ultra Pro - AI CLI Araclari ===' -ForegroundColor Cyan
Write-Host 'Claude Code, Codex ve Gemini CLI - npm orijinal paketleri ile.'
Write-Host 'Bu islem mevcut Node.js surumune ve internete ihtiyac duyar.'
Write-Host 'Hicbir API anahtari kaydedilmez. Abonelik hesabiniza daha sonra kendiniz girersiniz.'
$npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if (-not $npm) {Write-Host 'Node.js/npm bulunamadi. Resmi: https://nodejs.org/en/download' -ForegroundColor Yellow;exit 1}
$ans=Read-Host 'Uc resmi AI CLI paketini yuklemek veya guncellemek icin EVET yaz'
if ($ans -ne 'EVET') {Write-Host 'Iptal edildi';exit 0}
foreach ($pkg in @('@openai/codex','@google/gemini-cli','@anthropic-ai/claude-code')) {
  Write-Host "Yukleniyor: $pkg" -ForegroundColor Cyan
  & $npm.Source install -g "$pkg@latest"
  if ($LASTEXITCODE -ne 0) {Write-Host "UYARI: $pkg kurulumu basarisiz. Digerlerine geciliyor." -ForegroundColor Yellow}
}
Write-Host 'Bitti. Studio Sistem bolumunden kurulum durumunu kontrol et.' -ForegroundColor Green
