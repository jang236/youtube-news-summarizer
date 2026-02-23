#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
카카오톡 메시지 발송 모듈
- 나에게 보내기 (talk_message)
- 토큰 자동 갱신 (refresh_token)
- 데일리 다이제스트 요약 결과를 카카오톡으로 발송
"""

import requests
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KakaoSender:
    """카카오톡 메시지 발송 클래스"""
    
    # 카카오 API URLs
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    TOKEN_INFO_URL = "https://kapi.kakao.com/v1/user/access_token_info"
    
    def __init__(self, rest_api_key=None, access_token=None, refresh_token=None):
        """
        초기화
        환경변수 우선, 파라미터 폴백
        """
        self.rest_api_key = rest_api_key or os.environ.get('KAKAO_REST_API_KEY', '')
        self.access_token = access_token or os.environ.get('KAKAO_ACCESS_TOKEN', '')
        self.refresh_token = refresh_token or os.environ.get('KAKAO_REFRESH_TOKEN', '')
        
        # 토큰 파일 경로 (Replit 환경에서 토큰 유지용)
        self.token_file = os.path.join(os.path.dirname(__file__) or '.', 'kakao_tokens.json')
        
        # 파일에서 토큰 로드 (환경변수에 없을 경우)
        if not self.access_token or not self.refresh_token:
            self._load_tokens()
    
    def _load_tokens(self):
        """파일에서 토큰 로드"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if not self.access_token:
                        self.access_token = tokens.get('access_token', '')
                    if not self.refresh_token:
                        self.refresh_token = tokens.get('refresh_token', '')
                    logger.info("📱 카카오 토큰 파일에서 로드 완료")
        except Exception as e:
            logger.warning(f"토큰 파일 로드 실패: {e}")
    
    def _save_tokens(self):
        """토큰을 파일에 저장"""
        try:
            tokens = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f, indent=2)
            logger.info("💾 카카오 토큰 파일 저장 완료")
        except Exception as e:
            logger.warning(f"토큰 파일 저장 실패: {e}")
    
    def is_configured(self):
        """카카오톡 발송이 설정되어 있는지 확인"""
        return bool(self.access_token and self.refresh_token and self.rest_api_key)
    
    def check_token(self):
        """액세스 토큰 유효성 확인"""
        if not self.access_token:
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            resp = requests.get(self.TOKEN_INFO_URL, headers=headers, timeout=5)
            if resp.status_code == 200:
                info = resp.json()
                logger.info(f"✅ 카카오 토큰 유효 (남은 시간: {info.get('expires_in', 0)}초)")
                return True
            else:
                logger.warning(f"⚠️ 카카오 토큰 만료 또는 무효")
                return False
        except Exception as e:
            logger.error(f"토큰 확인 실패: {e}")
            return False
    
    def refresh_access_token(self):
        """리프레시 토큰으로 액세스 토큰 갱신"""
        if not self.refresh_token or not self.rest_api_key:
            logger.error("❌ 리프레시 토큰 또는 REST API 키가 없습니다")
            return False
        
        try:
            data = {
                "grant_type": "refresh_token",
                "client_id": self.rest_api_key,
                "refresh_token": self.refresh_token
            }
            resp = requests.post(self.TOKEN_URL, data=data, timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                self.access_token = result.get('access_token', self.access_token)
                # 리프레시 토큰도 갱신될 수 있음 (만료 1개월 미만일 때)
                if 'refresh_token' in result:
                    self.refresh_token = result['refresh_token']
                
                self._save_tokens()
                logger.info("🔄 카카오 토큰 갱신 성공")
                return True
            else:
                error = resp.json()
                logger.error(f"❌ 토큰 갱신 실패: {error}")
                return False
        except Exception as e:
            logger.error(f"❌ 토큰 갱신 오류: {e}")
            return False
    
    def _ensure_token(self):
        """토큰이 유효한지 확인하고, 필요시 갱신"""
        if not self.check_token():
            logger.info("🔄 토큰 갱신 시도...")
            return self.refresh_access_token()
        return True
    
    def send_text(self, text, link_url=None):
        """
        텍스트 메시지를 나에게 보내기
        
        Args:
            text: 메시지 텍스트 (최대 4000자)
            link_url: 메시지 클릭 시 이동할 URL (선택)
        Returns:
            bool: 발송 성공 여부
        """
        if not self._ensure_token():
            logger.error("❌ 카카오 토큰이 유효하지 않습니다")
            return False
        
        template = {
            "object_type": "text",
            "text": text[:4000],  # 최대 4000자
            "link": {
                "web_url": link_url or "https://youtube-news-summarizer-myfreelove12.replit.app",
                "mobile_web_url": link_url or "https://youtube-news-summarizer-myfreelove12.replit.app"
            }
        }
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        data = {"template_object": json.dumps(template)}
        
        try:
            resp = requests.post(self.SEND_ME_URL, headers=headers, data=data, timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get('result_code') == 0:
                    logger.info("📩 카카오톡 메시지 발송 성공")
                    return True
                else:
                    logger.error(f"❌ 발송 실패: {result}")
                    return False
            else:
                error = resp.json()
                logger.error(f"❌ API 오류 ({resp.status_code}): {error}")
                return False
        except Exception as e:
            logger.error(f"❌ 카카오톡 발송 오류: {e}")
            return False
    
    def send_daily_digest(self, digest_data):
        """
        데일리 다이제스트 결과를 카카오톡으로 발송
        
        Args:
            digest_data: 다이제스트 결과 dict
                {
                    'total_channels': int,
                    'total_videos': int,
                    'total_summarized': int,
                    'summarized': [
                        {'title': str, 'channel_name': str, 'summary_preview': str, ...}
                    ]
                }
        """
        if not digest_data or not digest_data.get('success'):
            logger.warning("⚠️ 다이제스트 데이터가 없거나 실패 상태")
            return False
        
        # 메시지 포맷 구성
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        total_ch = digest_data.get('total_channels', 0)
        total_vid = digest_data.get('total_videos', 0)
        total_sum = digest_data.get('total_summarized', 0)
        
        lines = [
            f"📺 YouTube 데일리 요약",
            f"📅 {now}",
            f"━━━━━━━━━━━━━━━",
            f"📊 {total_ch}개 채널 | {total_vid}개 영상 | {total_sum}개 요약",
            f"━━━━━━━━━━━━━━━",
            ""
        ]
        
        # 각 영상 요약 추가
        summaries = digest_data.get('summarized', [])
        for i, item in enumerate(summaries[:5], 1):  # 최대 5개
            title = item.get('title', '제목 없음')
            channel = item.get('channel_name', '채널 없음')
            preview = item.get('summary_preview', '')
            
            # 미리보기에서 첫 2줄만 추출
            preview_lines = preview.split('\n')
            short_preview = '\n'.join(preview_lines[:3])[:200]
            
            lines.append(f"▶ {i}. [{channel}]")
            lines.append(f"   {title[:60]}")
            lines.append(f"   {short_preview}")
            lines.append("")
        
        if len(summaries) > 5:
            lines.append(f"... 외 {len(summaries) - 5}개 영상")
        
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("🔗 전체 보기: YouTube 요약기에서 확인")
        
        message = '\n'.join(lines)
        return self.send_text(message)
    
    def send_single_summary(self, title, channel_name, summary, video_url=None):
        """
        개별 영상 요약을 카카오톡으로 발송
        
        Args:
            title: 영상 제목
            channel_name: 채널명
            summary: 요약 텍스트
            video_url: 원본 영상 URL (선택)
        """
        lines = [
            f"📺 YouTube 영상 요약",
            f"━━━━━━━━━━━━━━━",
            f"📢 {channel_name}",
            f"🎬 {title}",
            f"━━━━━━━━━━━━━━━",
            "",
            summary[:3000],  # 요약 본문 (최대 3000자)
        ]
        
        if video_url:
            lines.append("")
            lines.append(f"🔗 원본: {video_url}")
        
        message = '\n'.join(lines)
        return self.send_text(message, link_url=video_url)


def create_kakao_sender():
    """카카오 발송기 인스턴스 생성 (팩토리 함수)"""
    sender = KakaoSender()
    if sender.is_configured():
        logger.info("📱 카카오톡 발송 모듈 초기화 완료")
    else:
        logger.warning("⚠️ 카카오톡 발송 설정 미완료 (환경변수 또는 토큰 파일 필요)")
    return sender
