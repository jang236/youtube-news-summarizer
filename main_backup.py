#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube 뉴스 요약기 - 메인 애플리케이션
today_date 오류 수정 버전
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from datetime import datetime, timedelta
import secrets
import os
from youtube_api import (get_channel_id_from_any_url, get_recent_videos,
                         get_video_subtitles, test_channel_connection)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


# 데이터베이스 초기화
def init_db():
    """
    데이터베이스 테이블 생성
    """
    conn = sqlite3.connect('youtube_summarizer.db')
    cursor = conn.cursor()

    # 사용자 설정 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            openai_api_key TEXT,
            youtube_api_key TEXT,
            channel_url_1 TEXT,
            channel_url_2 TEXT,
            channel_url_3 TEXT,
            channel_id_1 TEXT,
            channel_id_2 TEXT,
            channel_id_3 TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 요약 결과 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            summary_date DATE NOT NULL,
            summary_content TEXT,
            keywords TEXT,
            video_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_settings (user_id)
        )
    ''')

    # 영상 상세 정보 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            video_title TEXT,
            video_url TEXT,
            thumbnail_url TEXT,
            channel_name TEXT,
            upload_time TIMESTAMP,
            subtitle_text TEXT,
            FOREIGN KEY (summary_id) REFERENCES summaries (id)
        )
    ''')

    conn.commit()
    conn.close()


def get_user_id():
    """
    세션에서 사용자 ID 가져오기 또는 생성
    """
    if 'user_id' not in session:
        session['user_id'] = secrets.token_hex(8)
    return session['user_id']


def save_user_settings(user_id, settings):
    """
    사용자 설정 저장
    """
    conn = sqlite3.connect('youtube_summarizer.db')
    cursor = conn.cursor()

    # 채널 URL에서 Channel ID 추출
    channel_ids = {}
    youtube_api_key = settings.get('youtube_api_key', '')

    for i in range(1, 4):
        url_key = f'channel_url_{i}'
        id_key = f'channel_id_{i}'

        if url_key in settings and settings[url_key]:
            channel_id = get_channel_id_from_any_url(
                settings[url_key],
                youtube_api_key if youtube_api_key else None)
            channel_ids[id_key] = channel_id
        else:
            channel_ids[id_key] = None

    # UPSERT 쿼리
    cursor.execute(
        '''
        INSERT INTO user_settings 
        (user_id, openai_api_key, youtube_api_key, 
         channel_url_1, channel_url_2, channel_url_3,
         channel_id_1, channel_id_2, channel_id_3, email, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            openai_api_key = excluded.openai_api_key,
            youtube_api_key = excluded.youtube_api_key,
            channel_url_1 = excluded.channel_url_1,
            channel_url_2 = excluded.channel_url_2,
            channel_url_3 = excluded.channel_url_3,
            channel_id_1 = excluded.channel_id_1,
            channel_id_2 = excluded.channel_id_2,
            channel_id_3 = excluded.channel_id_3,
            email = excluded.email,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, settings.get('openai_api_key', ''),
          settings.get('youtube_api_key', ''), settings.get(
              'channel_url_1', ''), settings.get(
                  'channel_url_2', ''), settings.get('channel_url_3', ''),
          channel_ids.get('channel_id_1'), channel_ids.get('channel_id_2'),
          channel_ids.get('channel_id_3'), settings.get('email', '')))

    conn.commit()
    conn.close()


def get_user_settings(user_id):
    """
    사용자 설정 조회
    """
    conn = sqlite3.connect('youtube_summarizer.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT * FROM user_settings WHERE user_id = ?
    ''', (user_id, ))

    result = cursor.fetchone()
    conn.close()

    if result:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, result))
    return None


def get_user_summaries(user_id, limit=10):
    """
    사용자의 요약 히스토리 조회
    """
    conn = sqlite3.connect('youtube_summarizer.db')
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT s.*, 
               COUNT(vd.id) as video_count_actual,
               GROUP_CONCAT(vd.thumbnail_url) as thumbnails
        FROM summaries s
        LEFT JOIN video_details vd ON s.id = vd.summary_id
        WHERE s.user_id = ?
        GROUP BY s.id
        ORDER BY s.created_at DESC
        LIMIT ?
    ''', (user_id, limit))

    results = cursor.fetchall()
    conn.close()

    summaries = []
    if results:
        columns = [desc[0] for desc in cursor.description]
        for result in results:
            summary = dict(zip(columns, result))
            if summary['thumbnails']:
                summary['thumbnail_list'] = summary['thumbnails'].split(
                    ',')[:3]
            else:
                summary['thumbnail_list'] = []
            summaries.append(summary)

    return summaries


@app.route('/')
def index():
    """
    메인 페이지 - 설정이 없으면 설정 페이지로 리다이렉트
    """
    user_id = get_user_id()
    settings = get_user_settings(user_id)

    if not settings or not settings.get('openai_api_key'):
        return redirect(url_for('setup'))

    return redirect(url_for('dashboard'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """
    설정 페이지
    """
    user_id = get_user_id()

    if request.method == 'POST':
        # 폼 데이터 수집
        settings = {
            'openai_api_key': request.form.get('openai_api_key', '').strip(),
            'youtube_api_key': request.form.get('youtube_api_key', '').strip(),
            'channel_url_1': request.form.get('channel_url_1', '').strip(),
            'channel_url_2': request.form.get('channel_url_2', '').strip(),
            'channel_url_3': request.form.get('channel_url_3', '').strip(),
            'email': request.form.get('email', '').strip(),
        }

        # 필수 항목 검증
        if not settings['openai_api_key']:
            flash('OpenAI API 키는 필수입니다.', 'error')
            return render_template('setup.html', settings=settings)

        if not any([
                settings['channel_url_1'], settings['channel_url_2'],
                settings['channel_url_3']
        ]):
            flash('최소 1개의 채널 URL을 입력해주세요.', 'error')
            return render_template('setup.html', settings=settings)

        try:
            # 설정 저장
            save_user_settings(user_id, settings)
            flash('설정이 저장되었습니다!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'설정 저장 중 오류가 발생했습니다: {str(e)}', 'error')

    # GET 요청 시 기존 설정 로드
    settings = get_user_settings(user_id) or {}
    return render_template('setup.html', settings=settings)


@app.route('/dashboard')
def dashboard():
    """
    대시보드 - 요약 결과 표시 (today_date 오류 수정 버전)
    """
    user_id = get_user_id()
    settings = get_user_settings(user_id)

    if not settings:
        return redirect(url_for('setup'))

    # 요약 히스토리 가져오기
    summaries = get_user_summaries(user_id)

    # 오늘의 요약 찾기
    today = datetime.now().date()
    today_summary = None
    for summary in summaries:
        summary_date = datetime.strptime(summary['summary_date'],
                                         '%Y-%m-%d').date()
        if summary_date == today:
            today_summary = summary
            break

    return render_template('dashboard.html',
                           settings=settings,
                           today_summary=today_summary,
                           summaries=summaries,
                           today_date=today)  # 🔧 이 줄이 수정된 부분!


@app.route('/test_videos')
def test_videos():
    """
    영상 수집 테스트
    """
    user_id = get_user_id()
    settings = get_user_settings(user_id)

    if not settings:
        return jsonify({'error': '설정을 먼저 완료해주세요.'})

    try:
        all_videos = []
        youtube_api_key = settings.get('youtube_api_key', '')

        # 각 채널에서 영상 수집
        for i in range(1, 4):
            channel_id = settings.get(f'channel_id_{i}')
            channel_url = settings.get(f'channel_url_{i}')

            if channel_id and channel_url:
                try:
                    videos = get_recent_videos(
                        channel_id,
                        youtube_api_key if youtube_api_key else None,
                        hours_back=14)

                    if videos:
                        all_videos.extend(videos)

                except Exception as e:
                    print(f"채널 {i} 영상 수집 실패: {e}")

        return jsonify({
            'success': True,
            'video_count': len(all_videos),
            'videos': all_videos[:10]  # 최대 10개만 미리보기
        })

    except Exception as e:
        return jsonify({'error': f'영상 수집 실패: {str(e)}'})


@app.route('/collect_videos')
def collect_videos():
    """
    영상 수집 (dashboard.html 템플릿 호환용)
    test_videos와 동일한 기능
    """
    return test_videos()


@app.route('/test_channel')
def test_channel():
    """
    채널 연결 테스트 (영상 URL 지원)
    """
    channel_url = request.args.get('url', '').strip()
    user_id = get_user_id()
    settings = get_user_settings(user_id)

    if not channel_url:
        return jsonify({'error': 'URL이 제공되지 않았습니다.'})

    youtube_api_key = settings.get('youtube_api_key', '') if settings else ''

    try:
        result = test_channel_connection(
            channel_url, youtube_api_key if youtube_api_key else None)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': f'채널 테스트 실패: {str(e)}'})


@app.route('/test_summary')
def test_summary():
    """
    요약 생성 테스트 (더미 데이터)
    """
    user_id = get_user_id()

    try:
        # 더미 요약 데이터 생성
        conn = sqlite3.connect('youtube_summarizer.db')
        cursor = conn.cursor()

        today = datetime.now().date()

        # 기존 오늘 요약 삭제
        cursor.execute(
            'DELETE FROM summaries WHERE user_id = ? AND summary_date = ?',
            (user_id, today))

        # 더미 요약 생성
        summary_content = """
        **오늘의 주요 뉴스 3가지**

        1. **경제 뉴스**: 한국 증시가 2.3% 상승하며 강세를 보였습니다. 
           - 반도체 업종이 상승세를 주도했습니다.
           - 외국인 순매수가 2주 연속 이어졌습니다.

        2. **국제 뉴스**: 미국 연방준비제도가 금리 동결을 발표했습니다.
           - 인플레이션 둔화 신호가 포착되었습니다.
           - 달러 강세가 일시적으로 완화될 것으로 전망됩니다.

        3. **정치 뉴스**: 정부가 새로운 부동산 정책을 발표했습니다.
           - 청년층 주택 공급 확대 방안이 포함되었습니다.
           - 부동산 투기 방지책이 강화됩니다.
        """

        keywords = "증시상승, 금리동결, 부동산정책, 반도체, 인플레이션"

        # 요약 저장
        cursor.execute(
            '''
            INSERT INTO summaries (user_id, summary_date, summary_content, keywords, video_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, today, summary_content, keywords, 3))

        summary_id = cursor.lastrowid

        # 더미 영상 상세 정보 저장
        dummy_videos = [{
            'video_id': 'test123',
            'title': '오늘의 증시 분석 - 반도체 업종 급등',
            'url': 'https://www.youtube.com/watch?v=test123',
            'thumbnail': 'https://img.youtube.com/vi/test123/hqdefault.jpg',
            'channel': '경제 뉴스 채널',
            'upload_time': datetime.now()
        }, {
            'video_id': 'test456',
            'title': '미국 연준 금리 동결 배경과 전망',
            'url': 'https://www.youtube.com/watch?v=test456',
            'thumbnail': 'https://img.youtube.com/vi/test456/hqdefault.jpg',
            'channel': '국제 뉴스 채널',
            'upload_time': datetime.now()
        }, {
            'video_id': 'test789',
            'title': '정부 부동산 정책 브리핑',
            'url': 'https://www.youtube.com/watch?v=test789',
            'thumbnail': 'https://img.youtube.com/vi/test789/hqdefault.jpg',
            'channel': '정치 뉴스 채널',
            'upload_time': datetime.now()
        }]

        for video in dummy_videos:
            cursor.execute(
                '''
                INSERT INTO video_details 
                (summary_id, video_id, video_title, video_url, thumbnail_url, channel_name, upload_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (summary_id, video['video_id'], video['title'], video['url'],
                  video['thumbnail'], video['channel'], video['upload_time']))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': '테스트 요약이 생성되었습니다!'})

    except Exception as e:
        return jsonify({'error': f'요약 생성 실패: {str(e)}'})


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
