# Ultra Pro Studio - winGet kullanmadan temel Python/Tkinter kurulumu.
# Python indirmesi yalnizca python.org adresinden, Windows imzasi kontrol edilerek gerceklesir.
$ErrorActionPreference = 'Stop'
$script:APP = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..'
$script:APP = [IO.Path]::GetFullPath($script:APP)
$script:PY = $null
$script:PYA = @()
function TestPython([string]$cmd, [string[]]$a) {
  try {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {return $false}
    & $cmd @a -c 'import tkinter; import sys; print(sys.version_info[0])' 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {return $false}
}
function FindPython {
  if (TestPython 'py' @('-3')) {$script:PY='py';$script:PYA=@('-3');return $true}
  $possible = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
    (Join-Path $env:ProgramFiles 'Python312\python.exe'),
    'python'
  )
  foreach ($p in $possible) {
    if (TestPython $p @()) {$script:PY=$p;$script:PYA=@();return $true}
  }
  return $false
}
Write-Host '=== ULTRA PRO STUDIO V5 ===' -ForegroundColor Cyan
if (-not (FindPython)) {
  Write-Host 'Tkinter destekli Python bulunamadi. Windows/winget durumu engel degil.' -ForegroundColor Yellow
  Write-Host 'Resmi python.org adresinden Python 3.12.10 x64 kurulum dosyasi indirilecek.'
  $ans=Read-Host 'Indirme ve sadece bu kullaniciya kurulum icin EVET yazin (iptal: HAYIR)'
  if ($ans -ne 'EVET') {Write-Host 'Kurulum iptal edildi.';exit 1}
  if ([Environment]::Is64BitOperatingSystem -eq $false) {Write-Host 'Bu kurulum sadece 64-bit Windows icindir.';exit 1}
  $url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
  $dst=Join-Path $env:TEMP 'ultra-pro-python-3.12.10-amd64.exe'
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
    $sig=Get-AuthenticodeSignature -FilePath $dst
    if ($sig.Status -ne 'Valid') {throw 'Indirilen Python dosyasinin Windows imzasi gecerli degil. Kurulum durduruldu.'}
    Write-Host 'Python dogrulandi, kullanici profiline kuruluyor...'
    $process=Start-Process -FilePath $dst -ArgumentList @('/quiet','InstallAllUsers=0','Include_launcher=1','Include_tcltk=1','Include_pip=1','PrependPath=0','Include_test=0') -Wait -PassThru
    if ($process.ExitCode -ne 0) {throw "Python installer hata kodu: $($process.ExitCode)"}
    if (-not (FindPython)) {throw 'Python kuruldu fakat calistirilamiyor. Bilgisayari yeniden baslatip tekrar dene.'}
  } catch {
    Write-Host ("Otomatik Python kurulumu basarisiz: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Manuel resmi adres: https://www.python.org/downloads/windows/' -ForegroundColor Yellow
    exit 1
  }
}
$scriptFile=Join-Path $script:APP 'app\gui.py'
Write-Host 'Ultra Pro Studio arayuzu aciliyor...'
try {
  $command = $script:PY
  $arg = @($script:PYA) + @($scriptFile)
  & $command @arg
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
} catch {
  Write-Host ("Arayuz acilamadi: " + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
