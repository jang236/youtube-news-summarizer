#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini AI 요약 시스템
- 단일 분석: 구조화된 JSON (감성/종목/중요도/AI코멘트)
- 심화 분석: 다각도 분석
- 다중 분석: 여러 영상 통합 비교
"""

import google.generativeai as genai
import logging
import time
import json
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class GeminiSummarizer:
    """Gemini 2.5 Flash 요약 시스템"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API 키가 필요합니다")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("✅ Gemini 2.5 Flash 초기화 완료")

    # =========================================================
    # 단일 분석 (구조화된 JSON 출력)
    # =========================================================
    def analyze_single(self, transcript: str, video_info: dict = None) -> str:
        """
        단일 영상 분석 - 구조화된 JSON 반환
        
        Returns: JSON 문자열 (감성, 종목, 중요도, AI코멘트 포함)
        """
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""당신은 증권/경제 전문 애널리스트입니다. YouTube 영상 자막을 분석하여 구조화된 JSON으로 응답하세요.

{'📺 영상 제목: ' + title if title else ''}

=== 자막 ===
{transcript[:80000]}
=== 끝 ===

반드시 아래 JSON 형식으로만 응답하세요. JSON 외에 다른 텍스트는 절대 포함하지 마세요.

```json
{{
    "sentiment": "positive 또는 negative 또는 neutral 중 하나",
    "importance": "urgent 또는 major 또는 normal 중 하나",
    "key_stocks": ["영상에서 언급된 핵심 종목/섹터명 최대 5개"],
    "key_points": [
        "핵심 포인트 1 (한 문장)",
        "핵심 포인트 2 (한 문장)",
        "핵심 포인트 3 (한 문장)"
    ],
    "market_impact": "시장에 미치는 영향 한 줄 요약",
    "investment_insight": "투자자를 위한 시사점 한 줄",
    "summary": "영상 전체 핵심 요약 (3~5문장, 구체적 수치와 팩트 포함)"
}}
```

판단 기준:
- sentiment: 시장/투자 관점에서 호재=positive, 악재=negative, 중립=neutral
- importance: 속보/시장 즉시 영향=urgent, 전략적 분석/전망=major, 일반 정보/교육=normal
- key_stocks: 구체적 종목명(삼성전자, SK하이닉스 등)이나 섹터명(반도체, 방산, 조선 등)
- 영상이 경제/투자가 아닌 경우에도 위 형식에 맞춰 적절히 분석

반드시 유효한 JSON만 출력하세요. ```json``` 마커 없이 순수 JSON만 출력하세요."""

        raw = self._generate(prompt)
        
        # JSON 파싱 시도 및 검증
        parsed = self._parse_structured_response(raw, title)
        return json.dumps(parsed, ensure_ascii=False)

    def _parse_structured_response(self, raw: str, title: str = '') -> dict:
        """Gemini 응답에서 구조화된 JSON 추출"""
        default = {
            "sentiment": "neutral",
            "importance": "normal",
            "key_stocks": [],
            "key_points": [],
            "market_impact": "",
            "investment_insight": "",
            "summary": raw  # 파싱 실패 시 원본 텍스트를 summary로
        }
        
        try:
            # JSON 블록 추출 시도
            # ```json ... ``` 패턴
            json_match = re.search(r'```json\s*\n?(.*?)\n?\s*```', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(1)
            
            # { ... } 패턴
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            
            parsed = json.loads(raw)
            
            # 필수 필드 검증
            result = {
                "sentiment": parsed.get("sentiment", "neutral"),
                "importance": parsed.get("importance", "normal"),
                "key_stocks": parsed.get("key_stocks", []),
                "key_points": parsed.get("key_points", []),
                "market_impact": parsed.get("market_impact", ""),
                "investment_insight": parsed.get("investment_insight", ""),
                "summary": parsed.get("summary", "")
            }
            
            # sentiment 값 정규화
            s = result["sentiment"].lower()
            if s in ("positive", "호재", "긍정"):
                result["sentiment"] = "positive"
            elif s in ("negative", "악재", "부정"):
                result["sentiment"] = "negative"
            else:
                result["sentiment"] = "neutral"
            
            # importance 값 정규화
            i = result["importance"].lower()
            if i in ("urgent", "긴급"):
                result["importance"] = "urgent"
            elif i in ("major", "주요"):
                result["importance"] = "major"
            else:
                result["importance"] = "normal"
            
            logger.info(f"📊 구조화 분석 완료: {result['sentiment']}/{result['importance']}, 종목: {result['key_stocks']}")
            return result
            
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"⚠️ JSON 파싱 실패, 원본 텍스트 사용: {e}")
            return default

    # =========================================================
    # 심화 분석 (기존 유지)
    # =========================================================
    def analyze_advanced(self, transcript: str, video_info: dict = None) -> str:
        """심화 분석 - 전문 애널리스트급 다각도 심층 분석"""
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""당신은 해당 분야 최고 수준의 전문 콘텐츠 분석가입니다.
영상의 주제가 금융이든, 기술이든, 건강이든, 교육이든 — 해당 분야의 시니어 애널리스트 관점에서 분석합니다.
제공된 YouTube 영상 자막을 분석하여, 독자가 '이해→판단→행동'할 수 있도록 돕는 깊이 있는 인사이트 리포트를 작성해주세요.

{'📺 영상 제목: ' + title if title else ''}

=== 자막 ===
{transcript}
=== 끝 ===

**[출력 구조]**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 핵심 인사이트 3줄 요약

▶ ① 첫 번째 핵심 인사이트
▶ ② 두 번째 핵심 인사이트
▶ ③ 세 번째 핵심 인사이트

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 인사이트 깊이 파기

■ 주요 팩트 정리 (What)
■ 배경과 원인 분석 (Why)
■ 실전 적용 방법 (How)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💭 놓치기 쉬운 함정들

◆ 첫 번째 함정
◆ 두 번째 함정

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 실전 액션 아이템

① 1단계: (구체적 액션)
② 2단계: (구체적 액션)
③ 3단계: (구체적 액션)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 주의사항 및 한계

전체 길이: 1500-2000자. 바로 분석을 시작하세요.
"""
        return self._generate(prompt)

    # =========================================================
    # 다중 영상 통합 분석
    # =========================================================
    def analyze_multiple(self, transcripts: List[str]) -> str:
        """여러 영상 통합 분석 - 비교 및 종합"""
        transcript_sections = ""
        for i, t in enumerate(transcripts, 1):
            trimmed = t[:50000] if len(t) > 50000 else t
            transcript_sections += f"\n=== 영상 {i} 자막 ===\n{trimmed}\n"

        prompt = f"""당신은 전문 애널리스트입니다. 다음 {len(transcripts)}개의 YouTube 영상을 통합 분석해주세요.

{transcript_sections}

다음 형식으로 **통합 브리핑**을 작성해주세요:

## 📊 통합 브리핑 ({len(transcripts)}개 영상 분석)

### 🔑 공통 핵심 메시지
• (모든 영상에서 공통으로 다루는 핵심 주제와 메시지)

### 📋 영상별 요약
{chr(10).join([f'**영상 {i+1}**: (해당 영상의 핵심 내용 2-3문장)' for i in range(len(transcripts))])}

### 🔄 비교 분석
• **공통점**: (영상들이 공유하는 관점이나 정보)
• **차이점**: (영상마다 다른 의견이나 관점)
• **상충되는 내용**: (있을 경우)

### 💡 종합 인사이트
(모든 영상을 종합했을 때 얻을 수 있는 핵심 인사이트 3-4문장)

### ✅ 실행 아이템
• (종합 분석을 바탕으로 한 구체적 액션 아이템들)

전문적이면서도 이해하기 쉬운 톤으로 작성해주세요.
"""
        return self._generate(prompt)

    # =========================================================
    # 내부 생성 함수
    # =========================================================
    def _generate(self, prompt: str) -> str:
        """Gemini API 호출"""
        try:
            start = time.time()
            response = self.model.generate_content(prompt)
            elapsed = time.time() - start
            logger.info(f"⏱️ Gemini 응답 시간: {elapsed:.1f}초")

            if response and response.text:
                return response.text
            return "응답을 생성할 수 없습니다."
        except Exception as e:
            logger.error(f"❌ Gemini 생성 실패: {e}")
            return f"AI 분석 중 오류가 발생했습니다: {str(e)}"


# =========================================================
# 호환 함수
# =========================================================
def generate_summary_with_gemini(script: str, video_info: dict,
                                 api_key: str) -> Optional[str]:
    """기존 코드 호환용"""
    try:
        summarizer = GeminiSummarizer(api_key)
        return summarizer.analyze_single(script, video_info)
    except Exception as e:
        logger.error(f"요약 생성 실패: {e}")
        return None


def test_gemini_connection(api_key: str) -> dict:
    """Gemini 연결 테스트"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("테스트입니다. '연결 성공'이라고만 답해주세요.")
        if response and response.text:
            return {'success': True, 'message': '✅ Gemini API 연결 성공!'}
        return {'success': False, 'message': '응답이 비어있습니다.'}
    except Exception as e:
        return {'success': False, 'message': f'연결 실패: {str(e)}'}


def configure_gemini(api_key: str) -> bool:
    """Gemini 설정"""
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False
