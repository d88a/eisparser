param(
  [string]$Server = "root@213.189.219.55",
  [string]$ProjectRoot = "D:\Anna\eisparser"
)

$ErrorActionPreference = "Stop"
$parent = Split-Path $ProjectRoot -Parent
$tmpTar = Join-Path $parent "eisparser_sync.tar.gz"
$tmpDir = Join-Path $parent "_sync_eisparser"

Write-Host "[1/5] Creating server snapshot..."
ssh $Server "cd /opt && tar --exclude='eisparser/.venv' --exclude='eisparser/results' --exclude='eisparser/zakupki' --exclude='eisparser/__pycache__' --exclude='eisparser/.pytest_cache' --exclude='eisparser/*.sql' --exclude='eisparser/*.sql.gz' --exclude='eisparser/*.tar.gz' --exclude='eisparser/*.zip' -czf /tmp/eisparser_sync.tar.gz eisparser"

Write-Host "[2/5] Downloading snapshot..."
scp "$Server`:/tmp/eisparser_sync.tar.gz" "$tmpTar"

Write-Host "[3/5] Extracting snapshot..."
if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
New-Item -ItemType Directory $tmpDir | Out-Null
tar -xzf $tmpTar -C $tmpDir

Write-Host "[4/5] Mirroring to local project..."
robocopy (Join-Path $tmpDir "eisparser") $ProjectRoot /MIR /R:2 /W:2 /XD .git .venv results zakupki __pycache__ .pytest_cache /XF *.sql *.sql.gz *.tar.gz *.zip | Out-Null

Write-Host "[5/5] Cleaning temp files..."
Remove-Item -Recurse -Force $tmpDir
Remove-Item -Force $tmpTar

Write-Host "Done. Local project synchronized with server snapshot."
