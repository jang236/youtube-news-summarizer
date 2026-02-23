@echo off
echo 필수 패키지 설치 중...
echo.

echo [1/4] OpenAI Whisper 설치...
pip install openai-whisper

echo [2/4] yt-dlp 설치...
pip install yt-dlp

echo [3/4] YouTube Transcript API 설치...
pip install youtube-transcript-api

echo [4/4] BeautifulSoup4 설치...
pip install beautifulsoup4

echo.
echo ✅ 모든 패키지 설치 완료!
echo.
echo 📝 추가 요구사항:
echo - FFmpeg가 시스템에 설치되어 있어야 합니다
echo - GPU 사용을 위해서는 PyTorch GPU 버전이 필요합니다
echo.
pause