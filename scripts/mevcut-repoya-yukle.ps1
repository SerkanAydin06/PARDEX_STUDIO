$ErrorActionPreference='Stop'
$root = Split-Path -Parent $PSScriptRoot
$repo = 'SerkanAydin06/PARDEX_STUDIO'
Write-Host "PARDEX_STUDIO: HERKESE ACIK depoya guncelleme" -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue) -or -not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Git ve GitHub CLI kurulu olmali.' }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'GitHub oturumunu `gh auth login` ile ac.' }
$confirm = Read-Host "Kisisel dosya ve sifreleri kontrol ettim. $repo icine kaynaklari yuklemek icin YUKLE yazin"
if ($confirm -cne 'YUKLE') {Write-Host 'Iptal'; exit 0}
$temp = Join-Path $env:TEMP ('pardex-studio-sync-' + [guid]::NewGuid().ToString('N'))
& gh repo clone $repo $temp
if ($LASTEXITCODE -ne 0) {throw 'Repo klonlanamadi.'}
try {
  $folders = @('app','tests','scripts','templates','.github','docs')
  foreach($folder in $folders){
    $src=Join-Path $root $folder; $dest=Join-Path $temp $folder
    if(Test-Path $src){
      New-Item -ItemType Directory -Force -Path $dest | Out-Null
      Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force
    }
  }
  $files=@('README.md','AGENTS.md','CLAUDE.md','GEMINI.md','CONTRIBUTING.md','SECURITY.md','KURULUM_VE_KULLANIM.md','TEST_RAPORU.md','.gitignore','01_ULTRA_PRO_STUDIO_AC.cmd','02_AI_CLI_KUR.cmd','03_CEKIRDEGI_GITHUBA_YUKLE.cmd','GITHUBA_YUKLE_BASIT.cmd')
  foreach($f in $files){$s=Join-Path $root $f;if(Test-Path $s){Copy-Item $s (Join-Path $temp $f) -Force}}
  Push-Location $temp
  try {
    & git add -A
    & git status --short
    $ok = Read-Host 'Yukaridaki degisiklikleri herkese acik GitHub reposuna gondermek icin ONAY yazin'
    if ($ok -cne 'ONAY') { Write-Host 'Iptal'; exit 0 }
    & git diff --cached --check
    if ($LASTEXITCODE -ne 0) {throw 'Degisiklik bicim kontrolu hatasi'}
    & git commit -m 'Update PARDEX_STUDIO source and AI guidance'
    if ($LASTEXITCODE -ne 0) {Write-Host 'Commit yok veya git kullanici ayarlarini kontrol et';exit 1}
    & git push origin HEAD:main
    if ($LASTEXITCODE -ne 0) {throw 'Push basarisiz; remote degisikliklerini kontrol et'}
    Write-Host "Guncellendi: https://github.com/$repo" -ForegroundColor Green
  } finally {Pop-Location}
} finally {Write-Host "Gecici kopya: $temp"}
