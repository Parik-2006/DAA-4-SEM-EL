# Download ML Models for Smart Attendance System

$WeightsDir = "p:\DAA LAB EL\attendance_backend\weights"
New-Item -ItemType Directory -Path $WeightsDir -Force | Out-Null

Write-Host "Downloading YOLOv8 Face Detection Model..." -ForegroundColor Cyan

# Method 1: Direct from Ultralytics (Most Reliable)
$yoloUrl = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
$yoloPath = "$WeightsDir\yolov8n-face.pt"

try {
    Write-Host "Downloading from: $yoloUrl"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $yoloUrl -OutFile $yoloPath -UseBasicParsing
    Write-Host "✓ YOLOv8 model downloaded: $yoloPath" -ForegroundColor Green
} catch {
    Write-Host "✗ Download failed. Please download manually from:" -ForegroundColor Red
    Write-Host "  https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Alternative Downloads (if above fails):" -ForegroundColor Yellow
Write-Host "  YOLOv8n: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt"
Write-Host "  YOLOv8n-Face: https://github.com/akanametov/yolov8-face/releases"
Write-Host ""
Write-Host "Checking what's in weights directory..." -ForegroundColor Cyan
Get-ChildItem -Path $WeightsDir
