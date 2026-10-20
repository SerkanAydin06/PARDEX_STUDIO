$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host '=== ULTRA PRO v5 / OZEL GITHUB CEKIRDEK DEPOSU ===' -ForegroundColor Cyan
if (-not (Get-Command gh -ErrorAction SilentlyContinue) -or -not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host 'Git veya GitHub CLI eksik. Sistem sekmesinden resmi kurulum adreslerini inceleyin.' -ForegroundColor Yellow
  exit 1
}
& gh auth status
if ($LASTEXITCODE -ne 0) {Write-Host 'Once GitHub CLI ile oturum ac: gh auth login';exit 1}
if (Test-Path (Join-Path $root '.git')) {Write-Host 'Bu cekirdek klasorunde zaten bir git deposu var. Islem korunmak icin durduruldu.';exit 1}
$name=Read-Host 'OZEL cekirdek depo adi (bos=Ultra-Pro-Studio-Core)'
if ([string]::IsNullOrWhiteSpace($name)) {$name='Ultra-Pro-Studio-Core'}
if ($name -notmatch '^[A-Za-z0-9._-]{2,65}$') {Write-Host 'Depo adi gecersiz';exit 1}
Write-Host 'UYARI: Bu komut .gitignore disindaki bu klasor dosyalarini gercek GitHub hesabina gonderecektir.' -ForegroundColor Yellow
$confirm=Read-Host "GitHub'da $name adinda OZEL depo olusturup yuklemek icin YAYINLA yazin"
if ($confirm -ne 'YAYINLA') {Write-Host 'Iptal edildi.';exit 0}
& git init -b main
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
& git add .
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
& git commit -m 'Initial Ultra Pro Studio Core v5'
if ($LASTEXITCODE -ne 0) {Write-Host 'Git kullanici adin/e-posta ayarin eksik olabilir.';exit $LASTEXITCODE}
& gh repo create $name --private --source . --remote origin --push
if ($LASTEXITCODE -ne 0) {Write-Host 'GitHub depo olusturma basarisiz. Kayitlari kontrol et.';exit $LASTEXITCODE}
Write-Host 'Cekirdek artik GitHub uzerinde ozel depoda. Actions test ve radar islerini kontrol edebilirsiniz.' -ForegroundColor Green
