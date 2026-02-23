#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 기반 YouTube 영상 분석 웹 애플리케이션
- 단일 분석 / 심화 분석 지원
- 채널 구독 + RSS 자동 수집
- 매일 자동 요약 (Daily Digest)
- SQLite 보관함
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import logging
import os
import sqlite3
import json
import re
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import pytz

# Import 모듈
from youtube_transcript_extractor import YouTubeTranscriptExtractor
from gemini_summarizer import GeminiSummarizer
from rss_collector import RSSCollector
from kakao_sender import KakaoSender, create_kakao_sender

# 환경 변수 로드
load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'youtube-summarizer-secret-key-2025')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KST 시간대
KST = pytz.timezone('Asia/Seoul')

# 모듈 초기화
transcript_extractor = YouTubeTranscriptExtractor()
rss_collector = RSSCollector()
kakao_sender = create_kakao_sender()

# DB 경로
DB_PATH = os.path.join(os.path.dirname(__file__), 'archive.db')


# =========================================================
# SQLite 데이터베이스
# =========================================================
def init_db():
    """데이터베이스 초기화"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 기존 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            video_url TEXT NOT NULL,
            title TEXT DEFAULT '',
            channel_name TEXT DEFAULT '',
            thumbnail_url TEXT DEFAULT '',
            transcript TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            analysis_type TEXT DEFAULT 'single',
            language TEXT DEFAULT '',
            method TEXT DEFAULT '',
            char_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 채널 구독 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_url TEXT NOT NULL UNIQUE,
            channel_name TEXT DEFAULT '',
            channel_id TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 데일리 다이제스트 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT NOT NULL,
            total_channels INTEGER DEFAULT 0,
            total_videos INTEGER DEFAULT 0,
            total_summarized INTEGER DEFAULT 0,
            summary_text TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ 데이터베이스 초기화 완료")


init_db()


def get_db():
    """DB 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# 유틸리티
# =========================================================
def extract_video_id(url: str) -> str:
    """URL에서 video_id 추출"""
    patterns = [
        r'(?:v=)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be/)([0-9A-Za-z_-]{11})',
        r'(?:embed/)([0-9A-Za-z_-]{11})',
        r'(?:shorts/)([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_video_info_from_api(video_id: str, api_key: str) -> dict:
    """YouTube Data API로 영상 정보 가져오기"""
    try:
        import requests
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': video_id,
            'key': api_key
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('items'):
            return None

        item = data['items'][0]
        snippet = item['snippet']
        return {
            'title': snippet.get('title', '제목 없음'),
            'channel_name': snippet.get('channelTitle', ''),
            'published_at': snippet.get('publishedAt', ''),
            'description': snippet.get('description', ''),
            'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
        }
    except Exception as e:
        logger.warning(f"영상 정보 가져오기 실패: {e}")
        return None


def get_gemini_key():
    """Gemini API 키 가져오기 (환경변수 우선, 세션 폴백)"""
    return os.getenv('GEMINI_API_KEY', '') or session.get('gemini_api_key', '')


# =========================================================
# 라우트: 페이지
# =========================================================
@app.route('/')
def home():
    """메인 페이지"""
    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    return render_template('home.html', current_time=now)


@app.route('/setup')
def setup():
    """API 키 설정 페이지"""
    return render_template('setup.html')


@app.route('/archive')
def archive():
    """보관함 페이지"""
    conn = get_db()
    analyses = conn.execute(
        'SELECT * FROM analyses ORDER BY created_at DESC LIMIT 50'
    ).fetchall()
    conn.close()
    return render_template('archive.html', analyses=analyses)


@app.route('/archive/<int:analysis_id>')
def archive_detail(analysis_id):
    """보관함 상세 페이지"""
    conn = get_db()
    analysis = conn.execute(
        'SELECT * FROM analyses WHERE id = ?', (analysis_id,)
    ).fetchone()
    conn.close()
    if not analysis:
        return redirect(url_for('archive'))
    return render_template('archive_detail.html', analysis=analysis)


# =========================================================
# API: 설정
# =========================================================
@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    """API 키 저장"""
    try:
        data = request.get_json() or request.form
        gemini_key = data.get('gemini_api_key', '').strip()
        youtube_key = data.get('youtube_api_key', '').strip()

        if gemini_key:
            session['gemini_api_key'] = gemini_key
        if youtube_key:
            session['youtube_api_key'] = youtube_key

        return jsonify({'success': True, 'message': '설정이 저장되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/check_settings', methods=['GET'])
def check_settings():
    """설정 상태 확인"""
    return jsonify({
        'gemini_api_configured': bool(get_gemini_key()),
        'youtube_api_configured': bool(session.get('youtube_api_key')),
    })


@app.route('/api/test_gemini', methods=['POST'])
def test_gemini():
    """Gemini API 연결 테스트"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        if not api_key:
            return jsonify({'success': False, 'message': 'API 키를 입력해주세요.'})

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("테스트입니다. '연결 성공'이라고만 답해주세요.")

        if response and response.text:
            return jsonify({'success': True, 'message': '✅ Gemini API 연결 성공!'})
        return jsonify({'success': False, 'message': '응답이 비어있습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'연결 실패: {str(e)}'})


# =========================================================
# API: 분석 (핵심)
# =========================================================
@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    YouTube 영상 분석
    - analysis_type: 'single' (단일) 또는 'advanced' (심화)
    """
    try:
        data = request.get_json()
        video_url = data.get('video_url', '').strip()
        analysis_type = data.get('analysis_type', 'single')

        if not video_url:
            return jsonify({'success': False, 'message': 'YouTube URL을 입력해주세요.'})

        gemini_key = get_gemini_key()
        youtube_key = session.get('youtube_api_key')

        if not gemini_key:
            return jsonify({'success': False, 'message': 'Gemini API 키를 먼저 설정해주세요.'})

        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'success': False, 'message': '유효하지 않은 YouTube URL입니다.'})

        logger.info(f"🎬 분석 시작: {video_id} (모드: {analysis_type})")

        # 1) 영상 정보 가져오기
        video_info = None
        if youtube_key:
            video_info = get_video_info_from_api(video_id, youtube_key)

        if not video_info:
            video_info = {
                'title': f'YouTube 영상 ({video_id})',
                'channel_name': '',
                'thumbnail_url': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
            }

        # 2) 자막 추출
        logger.info("📥 자막 추출 중...")
        extract_result = transcript_extractor.extract(video_url)

        if not extract_result['success']:
            return jsonify({
                'success': False,
                'message': f"자막 추출 실패: {extract_result['error']}"
            })

        transcript = extract_result['transcript']
        logger.info(f"✅ 자막 추출 완료: {extract_result['char_count']:,}자 ({extract_result['method']})")

        # 3) AI 요약
        logger.info(f"🤖 AI 요약 생성 중... (모드: {analysis_type})")
        try:
            summarizer = GeminiSummarizer(gemini_key)

            if analysis_type == 'advanced':
                summary = summarizer.analyze_advanced(transcript, video_info)
            else:
                summary = summarizer.analyze_single(transcript, video_info)

            if not summary:
                summary = "요약을 생성할 수 없습니다."
        except Exception as e:
            logger.error(f"AI 요약 실패: {e}")
            summary = f"AI 요약 중 오류 발생: {str(e)}"

        logger.info(f"✅ AI 요약 완료: {len(summary):,}자")

        # 4) DB에 저장
        try:
            conn = get_db()
            conn.execute(
                '''INSERT INTO analyses
                   (video_id, video_url, title, channel_name, thumbnail_url,
                    transcript, summary, analysis_type, language, method, char_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (video_id, video_url, video_info.get('title', ''),
                 video_info.get('channel_name', ''),
                 video_info.get('thumbnail_url', ''),
                 transcript, summary, analysis_type,
                 extract_result['language'], extract_result['method'],
                 extract_result['char_count'])
            )
            conn.commit()
            analysis_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()
        except Exception as e:
            logger.warning(f"DB 저장 실패: {e}")
            analysis_id = None

        # 5) 결과 반환
        return jsonify({
            'success': True,
            'analysis_id': analysis_id,
            'video_info': {
                'title': video_info.get('title', ''),
                'channel_name': video_info.get('channel_name', ''),
                'thumbnail_url': video_info.get('thumbnail_url', ''),
                'video_id': video_id,
            },
            'transcript': transcript,
            'summary': summary,
            'analysis_type': analysis_type,
            'extraction': {
                'method': extract_result['method'],
                'language': extract_result['language'],
                'char_count': extract_result['char_count'],
            }
        })

    except Exception as e:
        logger.error(f"❌ 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'분석 중 오류 발생: {str(e)}'})


# =========================================================
# API: 다중 영상 분석
# =========================================================
@app.route('/api/analyze_multiple', methods=['POST'])
def analyze_multiple():
    """여러 영상 통합 분석"""
    try:
        data = request.get_json()
        video_urls = data.get('video_urls', [])

        if not video_urls:
            return jsonify({'success': False, 'message': 'YouTube URL을 입력해주세요.'})

        if len(video_urls) > 3:
            return jsonify({'success': False, 'message': '최대 3개까지만 분석 가능합니다.'})

        gemini_key = get_gemini_key()
        if not gemini_key:
            return jsonify({'success': False, 'message': 'Gemini API 키를 먼저 설정해주세요.'})

        results = []
        transcripts = []

        for i, url in enumerate(video_urls):
            url = url.strip()
            if not url:
                continue

            video_id = extract_video_id(url)
            if not video_id:
                continue

            logger.info(f"📥 [{i+1}/{len(video_urls)}] 자막 추출 중: {video_id}")
            extract_result = transcript_extractor.extract(url)

            if extract_result['success']:
                transcripts.append(extract_result['transcript'])
                results.append({
                    'video_id': video_id,
                    'url': url,
                    'success': True,
                    'char_count': extract_result['char_count'],
                    'method': extract_result['method'],
                })
            else:
                results.append({
                    'video_id': video_id,
                    'url': url,
                    'success': False,
                    'error': extract_result['error'],
                })

        if not transcripts:
            return jsonify({'success': False, 'message': '추출 가능한 자막이 없습니다.'})

        # 통합 AI 분석
        logger.info(f"🤖 {len(transcripts)}개 영상 통합 분석 중...")
        try:
            summarizer = GeminiSummarizer(gemini_key)
            summary = summarizer.analyze_multiple(transcripts)
        except Exception as e:
            summary = f"통합 분석 중 오류: {str(e)}"

        return jsonify({
            'success': True,
            'results': results,
            'summary': summary,
            'total_analyzed': len(transcripts),
        })

    except Exception as e:
        logger.error(f"❌ 다중 분석 실패: {e}")
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# API: 보관함
# =========================================================
@app.route('/api/archive/delete/<int:analysis_id>', methods=['DELETE'])
def delete_analysis(analysis_id):
    """분석 기록 삭제"""
    try:
        conn = get_db()
        conn.execute('DELETE FROM analyses WHERE id = ?', (analysis_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/archive/list', methods=['GET'])
def list_analyses():
    """분석 기록 목록"""
    try:
        conn = get_db()
        analyses = conn.execute(
            'SELECT id, video_id, title, channel_name, thumbnail_url, '
            'summary, analysis_type, char_count, created_at '
            'FROM analyses ORDER BY created_at DESC LIMIT 50'
        ).fetchall()
        conn.close()

        return jsonify({
            'success': True,
            'analyses': [dict(a) for a in analyses]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/archive/<int:analysis_id>', methods=['GET'])
def get_analysis_detail(analysis_id):
    """분석 상세 조회"""
    try:
        conn = get_db()
        analysis = conn.execute(
            'SELECT * FROM analyses WHERE id = ?', (analysis_id,)
        ).fetchone()
        conn.close()

        if not analysis:
            return jsonify({'success': False, 'message': '분석을 찾을 수 없습니다.'})

        return jsonify({
            'success': True,
            'analysis': dict(analysis)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# API: 채널 관리 (신규)
# =========================================================
@app.route('/api/channels', methods=['GET'])
def list_channels():
    """등록된 채널 목록"""
    try:
        conn = get_db()
        channels = conn.execute(
            'SELECT * FROM channels ORDER BY added_at DESC'
        ).fetchall()
        conn.close()
        return jsonify({
            'success': True,
            'channels': [dict(ch) for ch in channels]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/channels', methods=['POST'])
def add_channel():
    """채널 등록"""
    try:
        data = request.get_json()
        channel_url = data.get('channel_url', '').strip()

        if not channel_url:
            return jsonify({'success': False, 'message': '채널 URL을 입력해주세요.'})

        # YouTube 채널 URL 검증
        if 'youtube.com' not in channel_url and 'youtu.be' not in channel_url:
            return jsonify({'success': False, 'message': '유효한 YouTube 채널 URL이 아닙니다.'})

        # 중복 확인
        conn = get_db()
        existing = conn.execute(
            'SELECT id FROM channels WHERE channel_url = ?', (channel_url,)
        ).fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'message': '이미 등록된 채널입니다.'})

        # channel_id 추출
        logger.info(f"🔍 채널 ID 추출 중: {channel_url}")
        channel_id = rss_collector.extract_channel_id(channel_url)

        if not channel_id:
            conn.close()
            return jsonify({'success': False, 'message': '채널 ID를 추출할 수 없습니다. URL을 확인해주세요.'})

        # 채널 이름 추출
        channel_name = rss_collector.extract_channel_name(channel_url)

        # DB 저장
        conn.execute(
            'INSERT INTO channels (channel_url, channel_name, channel_id) VALUES (?, ?, ?)',
            (channel_url, channel_name, channel_id)
        )
        conn.commit()
        new_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()

        logger.info(f"✅ 채널 등록: {channel_name} ({channel_id})")
        return jsonify({
            'success': True,
            'channel': {
                'id': new_id,
                'channel_url': channel_url,
                'channel_name': channel_name,
                'channel_id': channel_id,
            }
        })

    except Exception as e:
        logger.error(f"❌ 채널 등록 실패: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/channels/<int:channel_id>', methods=['DELETE'])
def delete_channel(channel_id):
    """채널 삭제"""
    try:
        conn = get_db()
        conn.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# API: 데일리 다이제스트 (신규)
# =========================================================
@app.route('/api/daily_digest', methods=['POST'])
def trigger_daily_digest():
    """데일리 다이제스트 수동 트리거"""
    try:
        data = request.get_json() or {}
        hours = data.get('hours', 24)  # 기본 24시간
        result = run_daily_digest(hours=hours)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ 다이제스트 트리거 실패: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/daily_digest/latest', methods=['GET'])
def get_latest_digest():
    """최신 데일리 다이제스트 조회"""
    try:
        conn = get_db()
        digest = conn.execute(
            'SELECT * FROM daily_digests ORDER BY created_at DESC LIMIT 1'
        ).fetchone()

        if not digest:
            conn.close()
            return jsonify({'success': True, 'digest': None, 'message': '아직 데일리 다이제스트가 없습니다.'})

        # 해당 다이제스트에 포함된 분석 목록
        digest_date = digest['digest_date']
        analyses = conn.execute(
            "SELECT id, video_id, title, channel_name, thumbnail_url, summary, "
            "analysis_type, created_at FROM analyses "
            "WHERE analysis_type = 'daily' AND date(created_at) = ? "
            "ORDER BY created_at DESC",
            (digest_date,)
        ).fetchall()
        conn.close()

        return jsonify({
            'success': True,
            'digest': dict(digest),
            'analyses': [dict(a) for a in analyses],
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/daily_digest/history', methods=['GET'])
def get_digest_history():
    """데일리 다이제스트 히스토리"""
    try:
        conn = get_db()
        digests = conn.execute(
            'SELECT * FROM daily_digests ORDER BY created_at DESC LIMIT 30'
        ).fetchall()
        conn.close()
        return jsonify({
            'success': True,
            'digests': [dict(d) for d in digests],
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# 데일리 다이제스트 실행 함수 (핵심 파이프라인)
# =========================================================
def run_daily_digest(hours: int = 24) -> dict:
    """
    일일 자동 요약 파이프라인

    흐름: 채널 목록 → RSS 수집 → 자막 추출 → AI 요약 → DB 저장

    Returns:
        dict: 실행 결과
    """
    logger.info(f"🚀 데일리 다이제스트 시작 (최근 {hours}시간)")

    gemini_key = get_gemini_key()
    if not gemini_key:
        return {'success': False, 'message': 'Gemini API 키가 설정되지 않았습니다.'}

    # 1) 등록 채널 목록 가져오기
    conn = get_db()
    channels = conn.execute('SELECT * FROM channels').fetchall()
    channels = [dict(ch) for ch in channels]
    conn.close()

    if not channels:
        return {'success': False, 'message': '등록된 채널이 없습니다. 먼저 채널을 등록해주세요.'}

    logger.info(f"📡 {len(channels)}개 채널에서 수집 시작...")

    # 2) RSS로 최근 영상 수집
    all_videos = rss_collector.collect_from_channels(channels, hours=hours)

    if not all_videos:
        # 다이제스트 기록 (영상 없음)
        today = datetime.now(KST).strftime('%Y-%m-%d')
        conn = get_db()
        conn.execute(
            'INSERT INTO daily_digests (digest_date, total_channels, total_videos, status, summary_text) '
            'VALUES (?, ?, 0, ?, ?)',
            (today, len(channels), 'completed', '최근 영상이 없습니다.')
        )
        conn.commit()
        conn.close()
        return {
            'success': True,
            'message': f'최근 {hours}시간 내 새 영상이 없습니다.',
            'total_channels': len(channels),
            'total_videos': 0,
        }

    logger.info(f"🎬 {len(all_videos)}개 영상 발견, 요약 시작...")

    # 3) 각 영상 트랜스크립트 추출 + AI 요약
    summarizer = GeminiSummarizer(gemini_key)
    summarized = []

    for i, video in enumerate(all_videos):
        try:
            logger.info(f"📥 [{i+1}/{len(all_videos)}] {video['title'][:50]}...")

            # 중복 확인 (이미 분석된 영상인지)
            conn = get_db()
            existing = conn.execute(
                'SELECT id FROM analyses WHERE video_id = ?', (video['video_id'],)
            ).fetchone()
            if existing:
                conn.close()
                logger.info(f"  ⏭️ 이미 분석됨, 스킵")
                continue
            conn.close()

            # 자막 추출
            extract_result = transcript_extractor.extract(video['url'])
            if not extract_result['success']:
                logger.warning(f"  ⚠️ 자막 추출 실패: {extract_result['error']}")
                continue

            # AI 요약
            video_info = {
                'title': video['title'],
                'channel_name': video['channel_name'],
            }
            summary = summarizer.analyze_single(extract_result['transcript'], video_info)

            if not summary:
                continue

            # DB 저장
            conn = get_db()
            conn.execute(
                '''INSERT INTO analyses
                   (video_id, video_url, title, channel_name, thumbnail_url,
                    transcript, summary, analysis_type, language, method, char_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'daily', ?, ?, ?)''',
                (video['video_id'], video['url'], video['title'],
                 video['channel_name'], video['thumbnail_url'],
                 extract_result['transcript'], summary,
                 extract_result['language'], extract_result['method'],
                 extract_result['char_count'])
            )
            conn.commit()
            conn.close()

            summarized.append({
                'video_id': video['video_id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'summary_preview': summary[:200],
            })

            logger.info(f"  ✅ 요약 완료")

            # API 부하 방지
            time.sleep(2)

        except Exception as e:
            logger.error(f"  ❌ 처리 실패: {e}")
            continue

    # 4) 다이제스트 기록
    today = datetime.now(KST).strftime('%Y-%m-%d')
    digest_summary = f"총 {len(channels)}개 채널에서 {len(all_videos)}개 영상 수집, {len(summarized)}개 요약 완료"

    conn = get_db()
    conn.execute(
        'INSERT INTO daily_digests (digest_date, total_channels, total_videos, '
        'total_summarized, status, summary_text, completed_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (today, len(channels), len(all_videos), len(summarized),
         'completed', digest_summary, datetime.now(KST).isoformat())
    )
    conn.commit()
    conn.close()

    logger.info(f"🎉 데일리 다이제스트 완료: {digest_summary}")

    result = {
        'success': True,
        'message': digest_summary,
        'total_channels': len(channels),
        'total_videos': len(all_videos),
        'total_summarized': len(summarized),
        'summarized': summarized,
    }

    # 카카오톡 자동 발송
    if kakao_sender.is_configured() and summarized:
        try:
            kakao_sender.send_daily_digest(result)
            logger.info("📩 카카오톡 데일리 다이제스트 발송 완료")
        except Exception as e:
            logger.warning(f"⚠️ 카카오톡 발송 실패: {e}")

    return result


# =========================================================
# API: RSS 수집 테스트
# =========================================================
@app.route('/api/rss/test', methods=['POST'])
def test_rss():
    """RSS 수집 테스트 (채널 URL 입력 → 최근 영상 목록)"""
    try:
        data = request.get_json()
        channel_url = data.get('channel_url', '').strip()
        hours = data.get('hours', 72)

        if not channel_url:
            return jsonify({'success': False, 'message': '채널 URL을 입력해주세요.'})

        channel_id = rss_collector.extract_channel_id(channel_url)
        if not channel_id:
            return jsonify({'success': False, 'message': '채널 ID를 추출할 수 없습니다.'})

        videos = rss_collector.get_recent_videos(channel_id, hours=hours)

        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'total': len(videos),
            'videos': [{
                'video_id': v['video_id'],
                'title': v['title'],
                'published': v['published'].isoformat() if v['published'] else '',
                'url': v['url'],
                'thumbnail_url': v['thumbnail_url'],
            } for v in videos]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# API: 카카오톡 (신규)
# =========================================================
@app.route('/api/kakao/test', methods=['POST'])
def test_kakao():
    """카카오톡 테스트 메시지 발송"""
    try:
        if not kakao_sender.is_configured():
            return jsonify({
                'success': False,
                'message': '카카오톡이 설정되지 않았습니다. KAKAO_REST_API_KEY, KAKAO_ACCESS_TOKEN, KAKAO_REFRESH_TOKEN 환경변수를 설정해주세요.'
            })

        success = kakao_sender.send_text('[YouTube 요약봇] 카카오톡 연동 테스트 성공! 🎉')
        return jsonify({
            'success': success,
            'message': '카카오톡 발송 성공!' if success else '카카오톡 발송 실패'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/kakao/status', methods=['GET'])
def kakao_status():
    """카카오톡 설정 상태 확인"""
    try:
        configured = kakao_sender.is_configured()
        token_valid = kakao_sender.check_token() if configured else False
        return jsonify({
            'success': True,
            'configured': configured,
            'token_valid': token_valid,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# API: 스케줄러 상태
# =========================================================
@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """스케줄러 상태 확인"""
    try:
        hour = int(os.getenv('DAILY_DIGEST_HOUR', '8'))
        minute = int(os.getenv('DAILY_DIGEST_MINUTE', '0'))
        return jsonify({
            'success': True,
            'enabled': scheduler is not None,
            'schedule_time': f'{hour:02d}:{minute:02d} KST',
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================================
# 실행
# =========================================================
scheduler = None

if __name__ == '__main__':
    # 스케줄러 초기화
    try:
        from scheduler import init_scheduler
        scheduler = init_scheduler(app, run_daily_digest)
    except Exception as e:
        logger.warning(f"⚠️ 스케줄러 초기화 실패: {e}")

    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 YouTube 요약기 서버 시작 (포트: {port})")
    logger.info(f"📊 하이브리드 자막 추출 (youtube-transcript-api + yt-dlp)")
    logger.info(f"📡 채널 구독 + RSS 자동 수집 기능 활성화")
    app.run(host='0.0.0.0', port=port, debug=False)
