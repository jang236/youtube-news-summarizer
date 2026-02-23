        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        """
        자막 추출 테스트 스크립트
        Replit Shell에서 실행: python test_transcript.py
        """

        from youtube_transcript_extractor import YouTubeTranscriptExtractor
        import logging

        logging.basicConfig(level=logging.INFO, format='%(message)s')

        extractor = YouTubeTranscriptExtractor()

        # 테스트 영상 목록 (원하는 URL로 변경 가능)
        test_urls = [
            "https://www.youtube.com/watch?v=RqlZ1fIVKgE",   # 테스트 1
            # "https://www.youtube.com/watch?v=영상ID",       # 추가 테스트
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
                print(f"\n--- 끝부분 (마지막 200자) ---")
                print(result['transcript'][-200:])
            else:
                print(f"\n❌ 실패: {result['error']}")

        print(f"\n{'='*60}")
        print("테스트 완료")