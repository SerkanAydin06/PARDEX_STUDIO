$ErrorActionPreference = 'Continue'
Write-Host '=== PARDEX Studio - Tek tik kurulum ===' -ForegroundColor Cyan
Write-Host 'Eksik programlari bulur, senin onayinla resmi kaynaklardan kurar ve sirket panelini acar.'
Write-Host 'Hicbir hesap bilgisi veya API anahtari istenmez/kaydedilmez.'
Write-Host ''

function Update-SessionPath {
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Test-Cmd([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Test-Python {
  if (Test-Cmd 'py') { return $true }
  $c = Get-Command 'python' -ErrorAction SilentlyContinue
  if (-not $c) { return $false }
  if ($c.Source -like '*WindowsApps*') { return $false }   # Microsoft Store kisayolu, gercek Python degil
  return $true
}
function Get-NodeMajor {
  if (-not (Test-Cmd 'node')) { return 0 }
  $v = (& node --version) 2>$null
  if ($v -match 'v(\d+)\.') { return [int]$Matches[1] }
  return 0
}
function Confirm-Evet([string]$Question) {
  $a = Read-Host ($Question + ' Onayliyorsan EVET yaz')
  return ($a -eq 'EVET')
}

# ---- 1) Temel programlar ----
$base = @()
if (-not (Test-Python)) { $base += [pscustomobject]@{ Name = 'Python 3.12'; Id = 'Python.Python.3.12'; Url = 'https://www.python.org/downloads/windows/' } }
if (-not (Test-Cmd 'git')) { $base += [pscustomobject]@{ Name = 'Git'; Id = 'Git.Git'; Url = 'https://git-scm.com/downloads/win' } }
if ((Get-NodeMajor) -lt 20) { $base += [pscustomobject]@{ Name = 'Node.js LTS'; Id = 'OpenJS.NodeJS.LTS'; Url = 'https://nodejs.org/en/download' } }

if ($base.Count -gt 0) {
  Write-Host ('Eksik: ' + (($base | ForEach-Object { $_.Name }) -join ', ')) -ForegroundColor Yellow
  if (Test-Cmd 'winget') {
    if (Confirm-Evet 'Bunlar winget ile kurulacak (Windows onay penceresi cikabilir).') {
      foreach ($b in $base) {
        Write-Host ('Kuruluyor: ' + $b.Name) -ForegroundColor Cyan
        & winget install --id $b.Id -e --source winget --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Write-Host ('UYARI: ' + $b.Name + ' kurulamadi. Elle kur: ' + $b.Url) -ForegroundColor Yellow }
      }
      Update-SessionPath
    } else { Write-Host 'Iptal edildi.'; exit 1 }
  } else {
    Write-Host 'winget bulunamadi. Indirme sayfalari aciliyor; kurduktan sonra bu dosyayi yeniden calistir.' -ForegroundColor Yellow
    foreach ($b in $base) { Start-Process $b.Url }
    exit 1
  }
}
if (-not (Test-Python) -or -not (Test-Cmd 'git') -or ((Get-NodeMajor) -lt 20)) {
  Write-Host 'Bazi programlar hala gorunmuyor. Bu pencereyi kapatip 00_KUR.cmd dosyasini yeniden calistir.' -ForegroundColor Yellow
  exit 1
}

# ---- 2) AI programlari (aboneliklerin) ----
$clis = @(
  [pscustomobject]@{ Cmd = 'claude'; Pkg = '@anthropic-ai/claude-code'; Name = 'Claude Code (Claude Pro)' },
  [pscustomobject]@{ Cmd = 'codex';  Pkg = '@openai/codex';             Name = 'Codex CLI (ChatGPT Pro)' },
  [pscustomobject]@{ Cmd = 'gemini'; Pkg = '@google/gemini-cli';        Name = 'Gemini CLI (Google AI Pro)' }
)
$missing = @($clis | Where-Object { -not (Test-Cmd $_.Cmd) })
if ($missing.Count -gt 0) {
  Write-Host ('Eksik AI programlari: ' + (($missing | ForEach-Object { $_.Name }) -join ', ')) -ForegroundColor Yellow
  if (Confirm-Evet 'Resmi npm paketleri kurulacak.') {
    $npm = (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue).Source
    foreach ($c in $missing) {
      Write-Host ('Kuruluyor: ' + $c.Name) -ForegroundColor Cyan
      & $npm install -g ($c.Pkg + '@latest')
      if ($LASTEXITCODE -ne 0) { Write-Host ('UYARI: ' + $c.Name + ' kurulamadi; paneldeki Kurulum ekranindan tekrar dene.') -ForegroundColor Yellow }
    }
    Update-SessionPath
  }
}

# ---- 3) Paneli ac ----
Write-Host ''
Write-Host 'Sirket paneli aciliyor. Hesap girislerini panelin Kurulum ekranindan yapabilirsin.' -ForegroundColor Green
Write-Host 'Paneli kapatmak icin bu pencereyi kapat.'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Cmd 'py') { & py -3 app\hq_server.py } else { & python app\hq_server.py }
