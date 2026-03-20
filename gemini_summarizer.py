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
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
        logger.info("Gemini 3 Flash Preview 초기화 완료")

    # =========================================================
    # 단일 분석 (구조화된 JSON 출력)
    # =========================================================
    def analyze_single(self, transcript: str, video_info: dict = None) -> str:
        """
        단일 영상 분석 - 구조화된 JSON 반환

        Returns: JSON 문자열
        """
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""당신은 경제 뉴스를 쉽게 풀어주는 전문가입니다.

[규칙]
- 모든 분야의 영상을 경제/투자에 미치는 영향 중심으로 분석
- 입력된 내용을 내부적으로 3회 압축: 투자 관련 필터링 → 인과관계 구조화 → 핵심 판단 요소 추출. 이 과정은 출력하지 않음
- 친근한 말투 (~거든요, ~란 말이에요, ~거예요)
- 확정적 표현 금지, 가능성으로 표현
- 마크다운(**, *, -, 번호 목록 등) 절대 사용 금지. 일반 텍스트만 사용

영상 제목: {title if title else '(제목 없음)'}

--- 자막 시작 ---
{transcript[:80000]}
--- 자막 끝 ---

아래 JSON 형식으로만 응답하라. 다른 텍스트 없이 순수 JSON만 출력.

{{
    "sentiment": "positive / negative / neutral 중 택1",
    "importance": "urgent / major / normal 중 택1",
    "one_line_summary": "이 영상의 핵심을 한 문장으로 (30자 이내, 구체적 수치 포함)",
    "key_stocks": ["언급된 핵심 종목/섹터 최대 5개"],
    "key_points": [
        "핵심 팩트 1 (수치, 날짜, 근거 포함)",
        "핵심 팩트 2",
        "핵심 팩트 3"
    ],
    "market_impact": "시장 영향 한 줄 (구체적으로)",
    "investment_insight": "투자 시사점 한 줄 (실행 가능한 수준으로)",
    "risk_assessment": "리스크 요인 한 줄 (반대 시나리오 포함)",
    "summary": "아래 형식으로 작성. 반드시 이 형식을 지킬 것:\n\n📰 (제공된 제목을 그대로 사용)\n\n✅ 요약 (🟢긍정 / 🔴부정 / 🟡중립 중 하나):\n핵심 내용 3~4문장. 친근한 말투로. 누가 무엇을 왜 했는지, 경제/시장에 어떤 영향인지.\n\n📖 용어: 어려운 전문 용어 = 쉬운 설명 (최대 2~3개, 쉬운 내용이면 생략)\n\n🤖 AI 한줄평: 핵심을 비유나 쉬운 표현으로 한 줄 정리\n\n🏷️ 관련 섹터: 영향 받는 산업/섹터 나열"
}}

작성 원칙:
- sentiment: 시장/투자 관점 호재=positive, 악재=negative, 판단 불가=neutral
- importance: 속보/즉시 대응=urgent, 전략적=major, 참고=normal
- one_line_summary: 핵심 결론 한 문장
- summary: 반드시 📰✅📖🤖🏷️ 이모지 섹션 형식으로 작성
- summary에 영상 서론, 인사말, 홍보 내용은 제외
- summary 안에서는 마크다운 사용 금지, 일반 텍스트만"

        raw = self._generate(prompt)

        # JSON 파싱 시도 및 검증
        parsed = self._parse_structured_response(raw, title)
        return json.dumps(parsed, ensure_ascii=False)

    def _parse_structured_response(self, raw: str, title: str = '') -> dict:
        """Gemini 응답에서 구조화된 JSON 추출"""
        default = {
            "sentiment": "neutral",
            "importance": "normal",
            "one_line_summary": "",
            "key_stocks": [],
            "key_points": [],
            "market_impact": "",
            "investment_insight": "",
            "risk_assessment": "",
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
                "one_line_summary": parsed.get("one_line_summary", ""),
                "key_stocks": parsed.get("key_stocks", []),
                "key_points": parsed.get("key_points", []),
                "market_impact": parsed.get("market_impact", ""),
                "investment_insight": parsed.get("investment_insight", ""),
                "risk_assessment": parsed.get("risk_assessment", ""),
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
        """심화 분석 - 2차 효과 분석 포함 다각도 심층 분석"""
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""당신은 경제 뉴스를 쉽게 풀어주는 전문가입니다.

[규칙]
- 모든 분야의 영상을 경제/투자에 미치는 영향 중심으로 분석
- 입력된 내용을 내부적으로 3회 압축: 투자 관련 필터링 → 인과관계 구조화 → 핵심 판단 요소 추출. 이 과정은 출력하지 않음
- 친근한 말투 (~거든요, ~란 말이에요, ~거예요)
- 확정적 표현 금지, 가능성으로 표현
- 마크다운(**, *, -, 번호 목록 등) 절대 사용 금지. 일반 텍스트만 사용
- 각 섹션 사이에 빈 줄을 넣어 문단을 명확히 구분

영상 제목: {title if title else '(제목 없음)'}

=== 자막 ===
{transcript}
=== 끝 ===

[출력 형식 — 반드시 지킬 것]

📰 (제공된 제목을 그대로 사용. 절대 수정하거나 요약하지 말 것)

✅ 핵심 요약 (🟢긍정 / 🔴부정 / 🟡중립):
이 영상이 말하고자 하는 핵심 3~4문장.
각 문장 사이에 빈 줄을 넣어 문단을 구분할 것.
인과관계 중심, 친근한 말투.

🔍 깊이 파기:
핵심 주장의 근거와 배경을 구체적으로 풀어서 설명.
"왜 이런 일이 벌어졌는지" → "그래서 어떤 결과가 예상되는지"
7~10문장 정도로 충분히.

🔄 2차 효과 분석:
영상이 직접 말하지 않은 파급 효과를 분석.
"이 뉴스의 1차 효과는 ~이지만, 진짜 주목할 건 ~거든요."
연쇄적으로 어떤 산업/종목/정책에 영향이 퍼지는지.
숨은 수혜자나 피해자가 있다면 짚어줄 것.
3~5문장.

⚖️ 다른 시각:
영상이 놓치고 있는 반대 관점이나 리스크.
"하지만 이런 가능성도 있거든요..."
2~3문장.

🎯 실전 액션:
시청자가 당장 할 수 있는 구체적 행동 2~3개.
"~한 사람은 ~하는 게 좋겠어요" 형태로.

📖 용어: 어려운 전문 용어 = 쉬운 설명 (최대 2~3개, 쉬운 내용이면 생략 가능)

🤖 AI 한줄평: 영상의 핵심을 비유나 쉬운 표현으로 한 줄 정리. 누구나 "아, 그런 거구나" 하고 바로 이해할 수 있게.

전체 길이: 2000~3000자. 바로 분석을 시작하세요.
"""
        return self._generate(prompt)

    # =========================================================
    # 일일 종합 인사이트 (오늘의 핵심 정보용)
    # =========================================================
    def generate_daily_insight(self, analyses: List[Dict]) -> dict:
        """
        당일 전체 분석 결과를 종합하여 핵심 인사이트 생성
        
        Args:
            analyses: 개별 분석 결과 리스트 (sentiment, key_stocks, key_points, summary 등)
        
        Returns: dict (headline, key_insights, risk_factors, action_items)
        """
        if not analyses:
            return {"headline": "", "key_insights": [], "risk_factors": [], "action_items": []}

        # 개별 분석 요약본 구성
        summary_text = ""
        for i, a in enumerate(analyses, 1):
            title = a.get('title', '')
            sentiment = a.get('sentiment', 'neutral')
            one_line = a.get('one_line_summary', '')
            summary = a.get('summary', '')
            stocks = a.get('key_stocks', [])
            if isinstance(stocks, str):
                try:
                    stocks = json.loads(stocks)
                except:
                    stocks = []
            points = a.get('key_points', [])
            if isinstance(points, str):
                try:
                    points = json.loads(points)
                except:
                    points = []
            
            summary_text += f"\n[영상 {i}] {title}\n"
            summary_text += f"감성: {sentiment} | 종목: {', '.join(stocks) if stocks else '없음'}\n"
            if one_line:
                summary_text += f"핵심: {one_line}\n"
            if points:
                for p in points[:3]:
                    summary_text += f"  - {p}\n"
            if summary:
                summary_text += f"요약: {summary[:200]}\n"

        prompt = f"""당신은 시니어 투자 전략가다. 오늘 수집된 {len(analyses)}개 영상의 분석 결과를 종합하여 핵심 인사이트를 추출하라.

--- 오늘의 분석 결과 ---
{summary_text}
--- 끝 ---

아래 JSON 형식으로만 응답하라. 순수 JSON만 출력.

{{
    "headline": "오늘 시장의 핵심을 한 문장으로 (40자 이내, 구체적)",
    "key_insights": [
        "종합 인사이트 1 (채널 간 공통 의견이나 핵심 트렌드, 구체적 수치 포함)",
        "종합 인사이트 2",
        "종합 인사이트 3"
    ],
    "risk_factors": [
        "리스크 요인 1 (반대 의견이나 주의사항)",
        "리스크 요인 2"
    ],
    "action_items": [
        "실행 아이템 1 (구체적으로 무엇을 해야 하는지)",
        "실행 아이템 2"
    ]
}}

작성 원칙:
- 이모지 사용 금지
- 개별 영상 요약 반복 금지 — 영상 간 교차 분석 결과만 작성
- 여러 채널이 같은 종목/이슈를 언급했다면 어떤 공통 결론이 있는지 추출
- 채널 간 의견이 갈리는 부분이 있다면 명확히 지적
- headline은 투자자가 오늘 가장 먼저 봐야 할 한 문장"""

        raw = self._generate(prompt)
        
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            parsed = json.loads(raw)
            return {
                "headline": parsed.get("headline", ""),
                "key_insights": parsed.get("key_insights", []),
                "risk_factors": parsed.get("risk_factors", []),
                "action_items": parsed.get("action_items", [])
            }
        except Exception as e:
            logger.warning(f"일일 인사이트 JSON 파싱 실패: {e}")
            return {"headline": raw[:100], "key_insights": [], "risk_factors": [], "action_items": []}

    # =========================================================
    # 다중 영상 통합 분석
    # =========================================================
    def analyze_multiple(self, transcripts: List[str]) -> str:
        """여러 영상 통합 분석 - 비교 및 종합"""
        transcript_sections = ""
        for i, t in enumerate(transcripts, 1):
            trimmed = t[:50000] if len(t) > 50000 else t
            transcript_sections += f"\n=== 영상 {i} 자막 ===\n{trimmed}\n"

        prompt = f"""당신은 시니어 애널리스트다. 다음 {len(transcripts)}개 영상을 통합 분석하라.

{transcript_sections}

아래 구조로 통합 브리핑을 작성하라:

[공통 핵심 메시지]
모든 영상의 공통 주제와 결론

[영상별 핵심]
{chr(10).join([f'영상 {i+1}: 핵심 내용 2문장' for i in range(len(transcripts))])}

[교차 분석]
- 공통점: 영상들이 공유하는 관점
- 차이점: 영상마다 다른 견해
- 상충: 서로 반대되는 주장 (있을 경우)

[종합 인사이트]
모든 영상을 종합한 핵심 결론 3~4문장

[실행 아이템]
구체적 액션 아이템

이모지 사용 금지. 팩트와 수치 중심으로 작성."""
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
        model = genai.GenerativeModel('gemini-3-flash-preview')
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
