#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube 자막 추출기 - 하이브리드 방식
1차: youtube-transcript-api (빠르고 안정적)
2차: yt-dlp (강력한 백업, 자동생성 자막 포함)
"""

import re
import logging
import json
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class YouTubeTranscriptExtractor:
    """하이브리드 YouTube 자막 추출기"""

    def __init__(self):
        self.supported_languages = ['ko', 'en', 'ja', 'zh-Hans', 'zh-Hant']

    def extract_video_id(self, url: str) -> str:
        """YouTube URL에서 video_id 추출"""
        patterns = [
            r'(?:v=)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be/)([0-9A-Za-z_-]{11})',
            r'(?:embed/)([0-9A-Za-z_-]{11})',
            r'(?:shorts/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract(self, video_url: str) -> dict:
        """
        자막 추출 메인 함수 (하이브리드 방식)

        Returns:
            dict: {
                'success': bool,
                'transcript': str,        # 전체 자막 텍스트
                'language': str,           # 추출된 언어
                'method': str,             # 사용된 방법
                'char_count': int,         # 글자 수
                'error': str or None       # 에러 메시지
            }
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return {
                'success': False,
                'transcript': '',
                'language': '',
                'method': 'none',
                'char_count': 0,
                'error': '유효하지 않은 YouTube URL입니다.'
            }

        logger.info(f"📺 자막 추출 시작: {video_id}")

        # === 1차: youtube-transcript-api ===
        result = self._method_transcript_api(video_id)
        if result['success']:
            return result

        # === 2차: yt-dlp ===
        result = self._method_ytdlp(video_id)
        if result['success']:
            return result

        # === 모두 실패 ===
        logger.error(f"❌ 모든 방법 실패: {video_id}")
        return {
            'success': False,
            'transcript': '',
            'language': '',
            'method': 'none',
            'char_count': 0,
            'error': '자막을 추출할 수 없습니다. 자막이 없는 영상이거나 접근이 제한된 영상입니다.'
        }

    # =========================================================
    # 방법 1: youtube-transcript-api (빠르고 안정적)
    # =========================================================
    def _method_transcript_api(self, video_id: str) -> dict:
        """youtube-transcript-api를 사용한 자막 추출 (최신 API 대응)"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            logger.info("[방법 1] youtube-transcript-api 시도...")

            # 최신 버전: 인스턴스 생성 필요
            api = YouTubeTranscriptApi()

            # === 방법 1-A: 직접 fetch (가장 간단) ===
            lang_used = ''
            fetched = None

            for lang in self.supported_languages:
                try:
                    fetched = api.fetch(video_id, languages=[lang])
                    lang_used = lang
                    logger.info(f"[방법 1] ✅ 자막 fetch 성공: {lang}")
                    break
                except Exception:
                    continue

            # 못 찾으면 list로 시도
            if fetched is None:
                try:
                    transcript_list = api.list(video_id)

                    # 수동 자막 우선
                    for lang in self.supported_languages:
                        try:
                            transcript = transcript_list.find_transcript(
                                [lang])
                            fetched = transcript.fetch()
                            lang_used = lang
                            logger.info(f"[방법 1] ✅ 수동 자막 발견: {lang}")
                            break
                        except Exception:
                            continue

                    # 자동 생성 자막 시도
                    if fetched is None:
                        for lang in self.supported_languages:
                            try:
                                transcript = transcript_list.find_generated_transcript(
                                    [lang])
                                fetched = transcript.fetch()
                                lang_used = f"{lang} (자동생성)"
                                logger.info(f"[방법 1] ✅ 자동생성 자막 발견: {lang}")
                                break
                            except Exception:
                                continue

                    # 아무 자막이나
                    if fetched is None:
                        for t in transcript_list:
                            fetched = t.fetch()
                            lang_used = getattr(t, 'language_code', 'unknown')
                            logger.info(f"[방법 1] ✅ 기타 자막 발견: {lang_used}")
                            break

                except Exception as e:
                    logger.warning(f"[방법 1] list 시도 실패: {e}")

            if fetched is None:
                logger.warning("[방법 1] ❌ 사용 가능한 자막 없음")
                return {
                    'success': False,
                    'transcript': '',
                    'language': '',
                    'method': 'transcript_api',
                    'char_count': 0,
                    'error': '자막을 찾을 수 없습니다.'
                }

            # FetchedTranscript → 텍스트 추출
            # (snippet.text / dict['text'] / to_raw_data() 모두 대응)
            texts = []
            try:
                for item in fetched:
                    if isinstance(item, dict):
                        text = item.get('text', '')
                    elif hasattr(item, 'text'):
                        text = item.text
                    else:
                        text = str(item)
                    if text and text.strip():
                        texts.append(text.strip())
            except TypeError:
                # iterable이 아닌 경우 to_raw_data() 시도
                try:
                    raw = fetched.to_raw_data()
                    for item in raw:
                        text = item.get('text', '') if isinstance(
                            item, dict) else str(item)
                        if text and text.strip():
                            texts.append(text.strip())
                except Exception:
                    pass

            full_text = ' '.join(texts)

            if not full_text.strip():
                logger.warning("[방법 1] ❌ 자막 텍스트가 비어있음")
                return {
                    'success': False,
                    'transcript': '',
                    'language': lang_used,
                    'method': 'transcript_api',
                    'char_count': 0,
                    'error': '자막 텍스트가 비어있습니다.'
                }

            full_text = self._clean_text(full_text)
            char_count = len(full_text)

            logger.info(f"[방법 1] ✅ 추출 성공: {char_count:,}자 ({lang_used})")
            return {
                'success': True,
                'transcript': full_text,
                'language': lang_used,
                'method': 'youtube-transcript-api',
                'char_count': char_count,
                'error': None
            }

        except ImportError:
            logger.warning("[방법 1] ⚠️ youtube-transcript-api 미설치")
            return {
                'success': False,
                'transcript': '',
                'language': '',
                'method': 'transcript_api',
                'char_count': 0,
                'error': 'youtube-transcript-api가 설치되지 않았습니다.'
            }
        except Exception as e:
            logger.warning(f"[방법 1] ❌ 실패: {e}")
            return {
                'success': False,
                'transcript': '',
                'language': '',
                'method': 'transcript_api',
                'char_count': 0,
                'error': str(e)
            }

    # =========================================================
    # 방법 2: yt-dlp (강력한 백업)
    # =========================================================
    def _method_ytdlp(self, video_id: str) -> dict:
        """yt-dlp를 사용한 자막 추출"""
        try:
            import yt_dlp
            logger.info("[방법 2] yt-dlp 시도...")

            url = f"https://www.youtube.com/watch?v={video_id}"

            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': self.supported_languages,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                subtitles = info.get('subtitles', {})
                auto_captions = info.get('automatic_captions', {})

                # 자막 선택 (수동 > 자동)
                selected_subs = None
                lang_used = ''
                is_auto = False

                # 수동 자막 먼저
                for lang in self.supported_languages:
                    if lang in subtitles:
                        selected_subs = subtitles[lang]
                        lang_used = lang
                        logger.info(f"[방법 2] ✅ 수동 자막 발견: {lang}")
                        break

                # 자동 자막 시도
                if not selected_subs:
                    for lang in self.supported_languages:
                        if lang in auto_captions:
                            selected_subs = auto_captions[lang]
                            lang_used = f"{lang} (자동생성)"
                            is_auto = True
                            logger.info(f"[방법 2] ✅ 자동생성 자막 발견: {lang}")
                            break

                if not selected_subs:
                    logger.warning("[방법 2] ❌ 사용 가능한 자막 없음")
                    return {
                        'success': False,
                        'transcript': '',
                        'language': '',
                        'method': 'yt-dlp',
                        'char_count': 0,
                        'error': 'yt-dlp로도 자막을 찾을 수 없습니다.'
                    }

                # 자막 포맷 선택 (json3 > vtt > srv1 > ttml)
                format_priority = [
                    'json3', 'vtt', 'srv1', 'srv2', 'srv3', 'ttml'
                ]
                selected_format = None
                sub_url = None

                for fmt in format_priority:
                    for sub in selected_subs:
                        if sub.get('ext') == fmt:
                            selected_format = fmt
                            sub_url = sub.get('url')
                            break
                    if sub_url:
                        break

                # 포맷을 못 찾으면 첫 번째 사용
                if not sub_url and selected_subs:
                    sub_url = selected_subs[0].get('url')
                    selected_format = selected_subs[0].get('ext', 'unknown')

                if not sub_url:
                    return {
                        'success': False,
                        'transcript': '',
                        'language': lang_used,
                        'method': 'yt-dlp',
                        'char_count': 0,
                        'error': '자막 URL을 가져올 수 없습니다.'
                    }

                # 자막 다운로드
                import requests
                headers = {
                    'User-Agent':
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                }
                response = requests.get(sub_url, headers=headers, timeout=30)
                response.raise_for_status()
                raw_content = response.text

                if not raw_content.strip():
                    return {
                        'success': False,
                        'transcript': '',
                        'language': lang_used,
                        'method': 'yt-dlp',
                        'char_count': 0,
                        'error': '자막 데이터가 비어있습니다.'
                    }

                # 포맷별 파싱
                full_text = self._parse_subtitle(raw_content, selected_format)

                if not full_text.strip():
                    return {
                        'success': False,
                        'transcript': '',
                        'language': lang_used,
                        'method': 'yt-dlp',
                        'char_count': 0,
                        'error': '자막 파싱에 실패했습니다.'
                    }

                full_text = self._clean_text(full_text)
                char_count = len(full_text)

                logger.info(
                    f"[방법 2] ✅ 추출 성공: {char_count:,}자 ({lang_used}, {selected_format})"
                )
                return {
                    'success': True,
                    'transcript': full_text,
                    'language': lang_used,
                    'method': f'yt-dlp ({selected_format})',
                    'char_count': char_count,
                    'error': None
                }

        except ImportError:
            logger.warning("[방법 2] ⚠️ yt-dlp 미설치")
            return {
                'success': False,
                'transcript': '',
                'language': '',
                'method': 'yt-dlp',
                'char_count': 0,
                'error': 'yt-dlp가 설치되지 않았습니다.'
            }
        except Exception as e:
            logger.warning(f"[방법 2] ❌ 실패: {e}")
            return {
                'success': False,
                'transcript': '',
                'language': '',
                'method': 'yt-dlp',
                'char_count': 0,
                'error': str(e)
            }

    # =========================================================
    # 자막 파싱 유틸리티
    # =========================================================
    def _parse_subtitle(self, content: str, fmt: str) -> str:
        """포맷별 자막 파싱"""
        try:
            if fmt == 'json3':
                return self._parse_json3(content)
            elif fmt == 'vtt':
                return self._parse_vtt(content)
            elif fmt in ('srv1', 'srv2', 'srv3', 'ttml'):
                return self._parse_xml(content)
            else:
                # 알 수 없는 포맷 - 태그 제거 후 반환
                return re.sub(r'<[^>]+>', '', content)
        except Exception as e:
            logger.warning(f"파싱 실패 ({fmt}): {e}, 태그 제거로 폴백")
            return re.sub(r'<[^>]+>', '', content)

    def _parse_json3(self, content: str) -> str:
        """JSON3 포맷 파싱"""
        data = json.loads(content)
        texts = []

        events = data.get('events', [])
        for event in events:
            segs = event.get('segs', [])
            for seg in segs:
                text = seg.get('utf8', '').strip()
                if text and text != '\n':
                    texts.append(text)

        return ' '.join(texts)

    def _parse_vtt(self, content: str) -> str:
        """VTT (WebVTT) 포맷 파싱"""
        lines = content.split('\n')
        texts = []
        skip_header = True

        for line in lines:
            line = line.strip()

            # 헤더 건너뛰기
            if skip_header:
                if line == '' or line.startswith('WEBVTT') or line.startswith(
                        'Kind:') or line.startswith('Language:'):
                    continue
                if '-->' in line:
                    skip_header = False
                    continue
                continue

            # 타임스탬프 라인 건너뛰기
            if '-->' in line:
                continue

            # 빈 줄 건너뛰기
            if not line:
                continue

            # 숫자만 있는 줄 건너뛰기 (큐 번호)
            if line.isdigit():
                continue

            # HTML 태그 제거
            clean = re.sub(r'<[^>]+>', '', line)
            if clean.strip():
                texts.append(clean.strip())

        return ' '.join(texts)

    def _parse_xml(self, content: str) -> str:
        """XML 기반 자막 파싱 (srv1, srv2, srv3, ttml)"""
        try:
            root = ET.fromstring(content)
            texts = []

            # 모든 텍스트 노드 추출
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    text = re.sub(r'<[^>]+>', '', elem.text).strip()
                    if text:
                        texts.append(text)

            return ' '.join(texts)
        except ET.ParseError:
            # XML 파싱 실패 시 정규식으로 텍스트 추출
            texts = re.findall(r'>([^<]+)<', content)
            return ' '.join(t.strip() for t in texts if t.strip())

    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        # HTML 엔티티 변환
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('\xa0', ' ')

        # 연속 공백 정리
        text = re.sub(r'\s+', ' ', text)

        # 중복 문장 제거 (자동생성 자막에서 흔함)
        sentences = text.split('. ')
        seen = set()
        unique = []
        for s in sentences:
            s_clean = s.strip().lower()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                unique.append(s.strip())
        text = '. '.join(unique)

        return text.strip()


# =========================================================
# 편의 함수 (기존 코드 호환용)
# =========================================================
_extractor = YouTubeTranscriptExtractor()


def extract_transcript(video_url: str) -> dict:
    """간편 호출 함수"""
    return _extractor.extract(video_url)


def get_transcript(video_id: str, language_codes=None) -> dict:
    """기존 코드 호환용 함수"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    result = _extractor.extract(url)
    # 기존 인터페이스에 맞게 변환
    return {
        'success': result['success'],
        'transcript': result['transcript'],
        'title': '',
        'language': result['language'],
        'error': result.get('error')
    }


# =========================================================
# 테스트
# =========================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    test_urls = [
        "https://www.youtube.com/watch?v=RqlZ1fIVKgE",  # 테스트 영상
    ]

    extractor = YouTubeTranscriptExtractor()

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"테스트: {url}")
        print(f"{'='*60}")

        result = extractor.extract(url)

        if result['success']:
            print(f"✅ 성공!")
            print(f"   방법: {result['method']}")
            print(f"   언어: {result['language']}")
            print(f"   글자수: {result['char_count']:,}자")
            print(f"   미리보기: {result['transcript'][:200]}...")
        else:
            print(f"❌ 실패: {result['error']}")
