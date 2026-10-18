<#
  build exe + ตัวติดตั้งของ Resume AI ตั้งแต่ต้นจนจบ (รันจากโฟลเดอร์ไหนก็ได้)

    powershell -ExecutionPolicy Bypass -File desktop\build.ps1

  ขั้นตอน:
    1. สร้าง venv ..\.venv-build (ถ้ายังไม่มี) แล้วลงแพ็กเกจตาม requirements-lock.txt (torch แบบ CPU-only)
    2. เตรียม Tesseract (tesseract.exe + DLL ที่ต้องใช้ + tha/eng/osd) ไว้ที่ build_assets\tesseract
    3. PyInstaller (onedir) → desktop\dist\ResumeAI\
    4. Inno Setup → desktop\Output\ResumeAI_Setup_v<เวอร์ชัน>.exe

  ต้องมีในเครื่องที่ build: Python 3.11+ (ใช้ 3.14 ตอนทำ v2.0.0), Tesseract ของ UB-Mannheim, Inno Setup 6
  และโฟลเดอร์โมเดล resume-jd-matcher-model\ + skill-extractor-model\ ที่ root ของโปรเจกต์
#>
param(
    [string]$Python = "py -3.14",
    [string]$TesseractDir = "C:\Program Files\Tesseract-OCR",
    [string]$InnoCompiler = "",
    [switch]$SkipInstall,     # ข้ามขั้นลงแพ็กเกจ (venv พร้อมแล้ว)
    [switch]$SkipInstaller    # build แค่ exe ไม่ทำตัวติดตั้ง
)

$ErrorActionPreference = "Stop"
$Desktop = $PSScriptRoot
$Root = Split-Path $Desktop -Parent
$Venv = Join-Path $Root ".venv-build"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
$Version = (Select-String -Path (Join-Path $Desktop "version.py") -Pattern 'VERSION = "(.+)"').Matches[0].Groups[1].Value
Write-Host "== Resume AI v$Version ==" -ForegroundColor Cyan

foreach ($m in "resume-jd-matcher-model", "skill-extractor-model") {
    if (-not (Test-Path (Join-Path $Root $m))) { throw "ไม่พบโฟลเดอร์โมเดล $m ที่ $Root — ดาวน์โหลดจาก GitHub Releases (v1.0-models) ก่อน" }
}

# ---------- 1. venv ----------
if (-not (Test-Path $VenvPy)) {
    Write-Host "[1/4] สร้าง venv $Venv"
    Invoke-Expression "$Python -m venv `"$Venv`""
}
if (-not $SkipInstall) {
    Write-Host "[1/4] ลงแพ็กเกจจาก requirements-lock.txt (torch CPU-only)"
    & $VenvPy -m pip install --upgrade pip
    & $VenvPy -m pip install -r (Join-Path $Desktop "requirements-lock.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install ล้มเหลว" }
}

# ---------- 2. Tesseract ----------
Write-Host "[2/4] เตรียม Tesseract จาก $TesseractDir"
$TessOut = Join-Path $Desktop "build_assets\tesseract"
if (Test-Path $TessOut) { Remove-Item -Recurse -Force $TessOut }
New-Item -ItemType Directory -Force (Join-Path $TessOut "tessdata") | Out-Null
if (-not (Test-Path (Join-Path $TesseractDir "tesseract.exe"))) {
    throw "ไม่พบ tesseract.exe ที่ $TesseractDir — ติดตั้งจาก https://github.com/UB-Mannheim/tesseract/wiki (เลือก Thai ตอนติดตั้ง) หรือระบุ -TesseractDir"
}
# DLL ที่ tesseract.exe ต้องใช้จริง (ได้จาก ldd tesseract.exe) — ไม่เอา ICU/pango/cairo ที่ใช้แค่ตอน train โมเดล
$Dlls = @(
    "libLerc.dll", "libarchive-13.dll", "libb2-1.dll", "libbrotlicommon.dll", "libbrotlidec.dll", "libbz2-1.dll",
    "libcurl-4.dll", "libdeflate.dll", "libexpat-1.dll", "libgcc_s_seh-1.dll", "libgif-7.dll", "libiconv-2.dll",
    "libidn2-0.dll", "libintl-8.dll", "libjbig-0.dll", "libjpeg-8.dll", "libleptonica-6.dll", "liblz4.dll",
    "liblzma-5.dll", "libopenjp2-7.dll", "libpng16-16.dll", "libpsl-5.dll", "libsharpyuv-0.dll", "libssh2-1.dll",
    "libstdc++-6.dll", "libtesseract-5.dll", "libtiff-6.dll", "libunistring-5.dll", "libwebp-7.dll",
    "libwebpmux-3.dll", "libwinpthread-1.dll", "libzstd.dll", "zlib1.dll"
)
Copy-Item (Join-Path $TesseractDir "tesseract.exe") $TessOut
foreach ($d in $Dlls) {
    $src = Join-Path $TesseractDir $d
    if (Test-Path $src) { Copy-Item $src $TessOut }
    else { Write-Warning "ไม่พบ $d (Tesseract เวอร์ชันอื่นอาจใช้ชื่อต่างกัน) — ตรวจด้วยการทดสอบ OCR หลัง build" }
}
foreach ($lang in "tha", "eng", "osd") {
    Copy-Item (Join-Path $TesseractDir "tessdata\$lang.traineddata") (Join-Path $TessOut "tessdata")
}
Copy-Item (Join-Path $TesseractDir "doc\LICENSE") (Join-Path $TessOut "LICENSE-Tesseract.txt")
Copy-Item (Join-Path $Desktop "THIRD_PARTY_NOTICES.txt") $TessOut

# ทดสอบว่า tesseract ที่แยกออกมารันได้เอง (ไม่พึ่งของในเครื่อง)
$env:TESSDATA_PREFIX = Join-Path $TessOut "tessdata"
$langs = & (Join-Path $TessOut "tesseract.exe") --list-langs 2>&1
Remove-Item Env:\TESSDATA_PREFIX
if (($langs -join " ") -notmatch "tha") { throw "Tesseract ที่เตรียมไว้รันไม่ได้ หรือไม่มีภาษาไทย: $langs" }

# ---------- 3. PyInstaller ----------
Write-Host "[3/4] PyInstaller (onedir)"
Push-Location $Desktop
try {
    & $VenvPy -m PyInstaller --noconfirm --clean ResumeAI_API.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller ล้มเหลว" }
} finally { Pop-Location }
$size = (Get-ChildItem -Recurse (Join-Path $Desktop "dist\ResumeAI") | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("    dist\ResumeAI = {0:N2} GB" -f $size)

# ---------- 4. Inno Setup ----------
if ($SkipInstaller) { Write-Host "ข้ามการทำตัวติดตั้ง (-SkipInstaller)"; exit 0 }
Write-Host "[4/4] Inno Setup"
if (-not $InnoCompiler) {
    $InnoCompiler = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $InnoCompiler) { throw "ไม่พบ Inno Setup 6 (ISCC.exe) — ติดตั้งจาก https://jrsoftware.org/isdl.php หรือระบุ -InnoCompiler" }
& $InnoCompiler "/DMyAppVersion=$Version" (Join-Path $Desktop "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup ล้มเหลว" }
Get-ChildItem (Join-Path $Desktop "Output") -Filter "ResumeAI_Setup_v$Version*" |
    ForEach-Object { Write-Host ("    {0}  {1:N2} GB" -f $_.Name, ($_.Length / 1GB)) }
Write-Host "เสร็จแล้ว" -ForegroundColor Green
