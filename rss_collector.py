#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube RSS 수집기
==================
채널 URL → RSS 피드 파싱 → 최근 영상 수집
"""

import re
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger(__name__)

# YouTube RSS 네임스페이스
NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
    'media': 'http://search.yahoo.com/mrss/',
}


class RSSCollector:
    """YouTube 채널 RSS 수집기"""

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    # =========================================================
    # 채널 URL → channel_id 추출
    # =========================================================
    def extract_channel_id(self, channel_url: str) -> Optional[str]:
        """
        YouTube 채널 URL에서 channel_id 추출

        지원 형식:
        - https://www.youtube.com/@handle
        - https://www.youtube.com/channel/UCxxxx
        - https://www.youtube.com/c/ChannelName
        """
        channel_url = channel_url.strip().rstrip('/')
        # /featured 등 하위 경로 제거
        channel_url = re.sub(r'/(featured|videos|shorts|streams|playlists|community|about)$', '', channel_url)

        # 이미 channel ID 형식인 경우
        match = re.search(r'/channel/(UC[a-zA-Z0-9_-]{22})', channel_url)
        if match:
            return match.group(1)

        # @ 핸들이나 /c/ 형식인 경우 → 페이지 스크래핑
        try:
            req = Request(channel_url, headers={
                'User-Agent': self.user_agent,
                'Accept-Language': 'ko-KR,ko;q=0.9',
            })
            response = urlopen(req, timeout=15)
            html = response.read().decode('utf-8', errors='ignore')

            # channel_id 패턴 찾기
            patterns = [
                r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
                r'channel_id=(UC[a-zA-Z0-9_-]{22})',
                r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
            ]
            for pattern in patterns:
                m = re.search(pattern, html)
                if m:
                    logger.info(f"✅ 채널 ID 추출: {m.group(1)}")
                    return m.group(1)

            logger.warning(f"❌ 채널 ID를 찾을 수 없음: {channel_url}")
            return None

        except Exception as e:
            logger.error(f"❌ 채널 페이지 접근 실패: {e}")
            return None

    # =========================================================
    # 채널 이름 추출
    # =========================================================
    def extract_channel_name(self, channel_url: str) -> str:
        """채널 URL에서 채널 이름 추출 시도"""
        try:
            req = Request(channel_url, headers={
                'User-Agent': self.user_agent,
                'Accept-Language': 'ko-KR,ko;q=0.9',
            })
            response = urlopen(req, timeout=15)
            html = response.read().decode('utf-8', errors='ignore')

            # <title> 태그에서 채널명 추출
            m = re.search(r'<title>(.+?)\s*-\s*YouTube</title>', html)
            if m:
                return m.group(1).strip()

            # og:title 메타 태그
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
            if m:
                return m.group(1).strip()

        except Exception:
            pass

        # URL에서 핸들 추출
        m = re.search(r'@([^/]+)', channel_url)
        if m:
            return f'@{m.group(1)}'
        return channel_url

    # =========================================================
    # RSS 피드 가져오기
    # =========================================================
    def fetch_rss(self, channel_id: str) -> List[Dict]:
        """
        채널의 RSS 피드를 가져와서 영상 목록 반환

        Returns:
            List[Dict]: [{
                'video_id': str,
                'title': str,
                'published': datetime,
                'url': str,
                'channel_name': str,
                'thumbnail_url': str,
            }, ...]
        """
        rss_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'

        try:
            req = Request(rss_url, headers={'User-Agent': self.user_agent})
            response = urlopen(req, timeout=15)
            data = response.read()
            root = ET.fromstring(data)
        except URLError as e:
            logger.error(f"❌ RSS 피드 접근 실패 ({channel_id}): {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"❌ RSS XML 파싱 실패 ({channel_id}): {e}")
            return []

        # 채널 이름
        author_el = root.find('atom:author/atom:name', NS)
        channel_name = author_el.text if author_el is not None else ''

        entries = root.findall('atom:entry', NS)
        videos = []

        for entry in entries:
            try:
                video_id_el = entry.find('yt:videoId', NS)
                title_el = entry.find('atom:title', NS)
                published_el = entry.find('atom:published', NS)

                if video_id_el is None or title_el is None:
                    continue

                video_id = video_id_el.text
                title = title_el.text or ''
                published_str = published_el.text if published_el is not None else ''

                # 날짜 파싱
                published = None
                if published_str:
                    try:
                        published = datetime.fromisoformat(
                            published_str.replace('Z', '+00:00')
                        )
                    except ValueError:
                        published = datetime.now(timezone.utc)

                # 썸네일
                media_group = entry.find('media:group', NS)
                thumbnail_url = ''
                if media_group is not None:
                    thumb_el = media_group.find('media:thumbnail', NS)
                    if thumb_el is not None:
                        thumbnail_url = thumb_el.get('url', '')

                if not thumbnail_url:
                    thumbnail_url = f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'

                videos.append({
                    'video_id': video_id,
                    'title': title,
                    'published': published,
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'channel_name': channel_name,
                    'thumbnail_url': thumbnail_url,
                })

            except Exception as e:
                logger.warning(f"⚠️ 엔트리 파싱 실패: {e}")
                continue

        logger.info(f"📡 RSS 수집: {channel_name} ({channel_id}) → {len(videos)}개 영상")
        return videos

    # =========================================================
    # 최근 N시간 영상 필터링
    # =========================================================
    def get_recent_videos(self, channel_id: str, hours: int = 24) -> List[Dict]:
        """최근 N시간 이내 업로드된 영상만 반환"""
        videos = self.fetch_rss(channel_id)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent = []
        for v in videos:
            if v['published'] and v['published'] >= cutoff:
                recent.append(v)

        logger.info(f"🕐 최근 {hours}시간 필터: {len(recent)}/{len(videos)}개")
        return recent

    # =========================================================
    # 여러 채널 한번에 수집
    # =========================================================
    def collect_from_channels(self, channels: List[Dict], hours: int = 24) -> List[Dict]:
        """
        여러 채널에서 최근 영상 수집

        Args:
            channels: [{'channel_id': 'UCxxx', 'channel_name': '...'}, ...]
            hours: 최근 N시간 이내

        Returns:
            모든 채널의 최근 영상 통합 리스트
        """
        all_videos = []

        for ch in channels:
            channel_id = ch.get('channel_id', '')
            if not channel_id:
                continue

            try:
                videos = self.get_recent_videos(channel_id, hours)
                all_videos.extend(videos)
                logger.info(f"✅ {ch.get('channel_name', channel_id)}: {len(videos)}개 수집")
            except Exception as e:
                logger.error(f"❌ {ch.get('channel_name', channel_id)} 수집 실패: {e}")

        # 날짜 기준 정렬 (최신순)
        all_videos.sort(key=lambda x: x['published'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        logger.info(f"📊 전체 수집 결과: {len(channels)}개 채널 → {len(all_videos)}개 영상")
        return all_videos
