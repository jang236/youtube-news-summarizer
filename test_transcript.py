from youtube_transcript_extractor import YouTubeTranscriptExtractor
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

extractor = YouTubeTranscriptExtractor()

test_urls = [
    "https://www.youtube.com/watch?v=RqlZ1fIVKgE",
]

for url in test_urls:
    print(f"\n{'='*60}")
    print(f"테스트: {url}")
    print(f"{'='*60}")

    result = extractor.extract(url)

    if result['success']:
        print(f"\n✅ 성공!")
        print(f"   방법: {result['method']}")
        print(f"   언어: {result['language']}")
        print(f"   글자수: {result['char_count']:,}자")
        print(f"\n--- 미리보기 (처음 500자) ---")
        print(result['transcript'][:500])
    else:
        print(f"\n❌ 실패: {result['error']}")
