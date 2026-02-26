# 기존 빌드 파일 삭제 후 재생성
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
pyinstaller CMEMO.spec

# 단일 EXE 빌드 (원파일)
pyinstaller CMEMO.onefile.spec

# 압축
& "C:\Program Files\Bandizip\Bandizip.exe" a "C:\Users\이창민\클라우드\google\vsc\python\cmemo\dist\CMEMO.zip" "C:\Users\이창민\클라우드\google\vsc\python\cmemo\dist\CMEMO"

# 단일 EXE 압축 예시
# & "C:\Program Files\Bandizip\Bandizip.exe" a "C:\Users\이창민\클라우드\google\vsc\python\cmemo\dist\CMEMO.zip" "C:\Users\이창민\클라우드\google\vsc\python\cmemo\dist\CMEMO.exe"

# 압축파일 구글드라이브에 백업
## 1. 기존 파일 삭제 (파일이 있을 경우에만 삭제)
$oldFile = "C:\Users\이창민\클라우드\google\유틸리티\CMEMO.zip"
if (Test-Path $oldFile) {
    Remove-Item -Path $oldFile -Force
    Write-Host "기존 파일을 삭제했습니다." -ForegroundColor Yellow
}

## 2. 새 파일 경로 설정
$sourceFile = "C:\Users\이창민\클라우드\google\vsc\python\cmemo\dist\CMEMO.zip"
$destFolder = "C:\Users\이창민\클라우드\google\유틸리티\"

## 3. 파일 복사
Copy-Item -Path $sourceFile -Destination $destFolder -Force
Write-Host "새로운 파일을 성공적으로 복사했습니다." -ForegroundColor Green
