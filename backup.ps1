param(
    [string]$SourceDir = "",
    [string]$BackupDir = "backup"
)

# 備份原始碼（附日期時間）
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"

# 建立備份目錄
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }

# ZIP 路徑
$zipPath = Join-Path $BackupDir "$timestamp.zip"

# 排除路徑（相對於 SourceDir）
$excludeDirs = @(
    '__pycache__', '.git', 'venv', '.venv', 'data\cache', 
    'backup', '.mypy_cache', '.pytest_cache', 'node_modules'
)

$excludeExts = @('.zip', '.pyc', '.pyo', '.parquet', '.db')

# 設定來源目錄
if ([string]::IsNullOrEmpty($SourceDir)) { $SourceDir = Get-Location }
$SourceDir = $SourceDir.TrimEnd('\')

# 改用 Shell.Application COM 物件壓縮（相容性最佳，不需 .NET assembly）
$shell = New-Object -ComObject Shell.Application

try {
    # 收集要壓縮的檔案清單
    $items = @()
    Get-ChildItem $SourceDir -Recurse -File | Where-Object {
        $relPath = $_.FullName.Substring($SourceDir.Length + 1)
        
        # 檢查是否在排除目錄中
        foreach ($excl in $excludeDirs) {
            if ($relPath -match [regex]::Escape($excl)) { return $false }
        }
        
        # 檢查副檔名排除
        foreach ($ext in $excludeExts) {
            if ($_.Extension -eq $ext) { return $false }
        }
        
        # 排除 backup.ps1 和 .gitignore
        if ($_.Name -eq '.gitignore' -or $_.Name -eq 'backup.ps1') { return $false }
        
        return $true
    } | ForEach-Object { $items += $_.FullName }
    
    if ($items.Count -gt 0) {
        # 將所有檔案複製到一個暫存目錄，保留相對路徑
        $tmpDir = Join-Path $env:TEMP "backup_$([System.IO.Path]::GetRandomFileName())"
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        
        foreach ($filePath in $items) {
            $relPath = $filePath.Substring($SourceDir.Length + 1)
            $destFile = Join-Path $tmpDir $relPath
            $destDir = Split-Path $destFile -Parent
            if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item $filePath $destFile
        }
        
        # 壓縮暫存目錄
        $zipObj = $shell.NameSpace($zipPath)
        $tmpShell = $shell.NameSpace($tmpDir)
        $zipObj.CopyHere($tmpShell.Items(), 20)
        
        # 等待壓縮完成
        Start-Sleep -Seconds 2
        
        # 清理暫存目錄
        Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    if (Test-Path $zipPath) {
        $fileSize = (Get-Item $zipPath).Length
        Write-Host "  ✅ 備份完成：$timestamp.zip （大小：$fileSize 位元組）"
    } else {
        Write-Host "  ⚠️  備份失敗"
    }
}
catch {
    Write-Host "  ⚠️  備份失敗：$_"
}