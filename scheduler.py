#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스케줄러 모듈
=============
APScheduler로 매일 지정 시간 자동 요약 파이프라인 실행
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def init_scheduler(app, run_daily_digest_func):
    """
    APScheduler 초기화 및 일일 요약 작업 등록

    Args:
        app: Flask 앱 인스턴스
        run_daily_digest_func: 일일 요약 실행 함수
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("⚠️ APScheduler 미설치. pip install apscheduler 필요")
        return None

    scheduler = BackgroundScheduler(daemon=True)

    # 매일 아침 8시 (KST) 실행
    schedule_hour = int(os.getenv('DAILY_DIGEST_HOUR', '8'))
    schedule_minute = int(os.getenv('DAILY_DIGEST_MINUTE', '0'))

    scheduler.add_job(
        func=lambda: _run_with_app_context(app, run_daily_digest_func),
        trigger=CronTrigger(
            hour=schedule_hour,
            minute=schedule_minute,
            timezone='Asia/Seoul'
        ),
        id='daily_digest',
        name='일일 유튜브 요약',
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"⏰ 스케줄러 시작: 매일 {schedule_hour:02d}:{schedule_minute:02d} KST 자동 실행")

    return scheduler


def _run_with_app_context(app, func):
    """Flask 앱 컨텍스트 내에서 함수 실행"""
    with app.app_context():
        try:
            logger.info("🔄 스케줄러: 일일 요약 시작...")
            result = func()
            logger.info(f"✅ 스케줄러: 일일 요약 완료 - {result}")
        except Exception as e:
            logger.error(f"❌ 스케줄러: 일일 요약 실패 - {e}")
            import traceback
            traceback.print_exc()
