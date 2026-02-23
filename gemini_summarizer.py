#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini AI 요약 시스템
- 단일 분석: 핵심 요약
- 심화 분석: 다각도 분석 (투자/시사점/리스크 등)
- 다중 분석: 여러 영상 통합 비교
"""

import google.generativeai as genai
import logging
import time
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
    # 단일 분석 (기본)
    # =========================================================
    def analyze_single(self, transcript: str, video_info: dict = None) -> str:
        """
        단일 영상 분석 - 핵심 요약
        """
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""다음은 YouTube 영상의 자막입니다. 핵심 내용을 구조화하여 요약해주세요.

{'📺 영상 제목: ' + title if title else ''}

=== 자막 ===
{transcript}
=== 끝 ===

다음 형식으로 작성해주세요:

## 📌 주제
(영상의 핵심 주제를 1-2문장으로)

## 🔑 핵심 포인트
• (첫 번째 주요 포인트)
• (두 번째 주요 포인트)
• (세 번째 주요 포인트)
• (네 번째 주요 포인트 - 있는 경우)
• (다섯 번째 주요 포인트 - 있는 경우)

## 💡 결론 및 시사점
(영상의 결론과 시청자에게 주는 시사점을 2-3문장으로)

명확하고 간결하게, 친근한 설명 톤으로 작성해주세요.
"""
        return self._generate(prompt)

    # =========================================================
    # 심화 분석
    # =========================================================
    def analyze_advanced(self,
                         transcript: str,
                         video_info: dict = None) -> str:
        """
        심화 분석 - 전문 애널리스트급 다각도 심층 분석
        """
        title = video_info.get('title', '') if video_info else ''

        prompt = f"""당신은 해당 분야 최고 수준의 전문 콘텐츠 분석가입니다.
영상의 주제가 금융이든, 기술이든, 건강이든, 교육이든 — 해당 분야의 시니어 애널리스트 관점에서 분석합니다.
제공된 YouTube 영상 자막을 분석하여, 독자가 '이해→판단→행동'할 수 있도록 돕는 깊이 있는 인사이트 리포트를 작성해주세요.

{'📺 영상 제목: ' + title if title else ''}

=== 자막 ===
{transcript}
=== 끝 ===

**[필수 준수사항]**
1. 제공된 전체 자막을 기반으로 분석하되, 누락된 내용이 없는지 체크
2. 원본에 없는 해석, 비유, 추론은 "💭 놓치기 쉬운 함정들" 섹션에서만 허용
3. 모든 수치 데이터는 정확히 인용하고 출처 명시
4. 객관적 정보와 개인적 견해를 명확히 구분
5. 영상 화자의 주장과 일반적 통설이 다를 경우 반드시 지적

**[작성 원칙 — 8가지 모두 반드시 적용]**

1. **가설-검증-적용 구조**로 논리적 흐름을 만든다
   - 영상의 핵심 주장을 가설로 제시
   - 데이터와 사례로 검증
   - 독자가 적용할 수 있는 방법 제시

2. **독자 몰입 유도 기법**을 활용한다
   - "당신이 만약 이 상황에 있다면..."
   - "대부분의 사람들은 이렇게 생각하지만..."
   - "실제로는 어떤 일이 일어날까요?"

3. **다층적 인사이트 제공**
   - 1차: 영상에서 말한 내용 (What) — 핵심 팩트와 데이터
   - 2차: 왜 그런지 배경 설명 (Why) — 원인, 맥락, 역사적 배경
   - 3차: 어떻게 활용할지 (How) — 구체적 적용법과 실행 전략

4. **심리학적 접근**을 통해 깊이를 더한다
   - 인간의 편향성: 확증 편향, 손실 회피, 앵커링 효과 등 연결
   - 집단 심리 vs 개인 심리 비교
   - 감정적 반응 vs 합리적 판단의 차이 분석

5. **구체적 사례와 비유**로 이해를 돕는다
   - 역사적 사례, 일상적 경험과 연결
   - 복잡한 개념을 직관적 비유로 설명
   - 성공/실패 사례를 통한 교훈 도출

6. **예상 반론 대응**으로 신뢰성을 높인다
   - "하지만 이런 의견도 있습니다..."
   - "물론 예외적인 상황도 있지만..."
   - "완벽한 예측은 불가능하지만..."

7. **리듬감 있는 문체**를 사용한다
   - 짧은 문장으로 핵심 포인트를 강조
   - 긴 문장으로 상세한 배경과 맥락을 설명
   - 단락별 호흡을 조절하여 읽는 사람이 지치지 않게

8. **행동 유도**로 마무리한다
   - 구체적이고 실행 가능한 액션 아이템
   - 단계별 실행 방법 제시
   - 주의사항과 체크포인트

**[출력 구조 — 아래 순서와 형식을 정확히 따를 것]**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 핵심 인사이트 3줄 요약

▶ ① 첫 번째 핵심 인사이트
▶ ② 두 번째 핵심 인사이트
▶ ③ 세 번째 핵심 인사이트

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 인사이트 깊이 파기

What(팩트), Why(배경/원인), How(활용법)를 자연스러운 서술형으로 통합하여 작성.
각 층위를 명확히 구분하되 자연스럽게 연결한다.

■ 주요 팩트 정리 (What)
■ 배경과 원인 분석 (Why)
■ 실전 적용 방법 (How)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💭 놓치기 쉬운 함정들

영상 내용을 받아들일 때 빠지기 쉬운 인지편향과 실수들을 심리학적 관점에서 분석.
역사적 사례나 일상 경험과 연결하여 구체적으로 설명한다.

◆ 첫 번째 함정 (구체적으로 명시)
◆ 두 번째 함정 (구체적으로 명시)
◆ 세 번째 함정 (구체적으로 명시)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 실전 액션 아이템

단계별로 실행 가능한 구체적 행동 지침을 제시한다.
각 액션에 대해 '왜 이것을 해야 하는지'와 '어떻게 하는지'를 함께 설명한다.

① 1단계: (구체적 액션)
② 2단계: (구체적 액션)
③ 3단계: (구체적 액션)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 주의사항 및 한계

영상 정보의 한계점과 추가로 확인해야 할 사항.
영상 화자의 주장에서 과학적 근거가 부족하거나 개인 경험에 치우친 부분을 지적한다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**[순수 텍스트 가독성 지침]**
- HTML, 마크다운(**굵게**, ## 등) 완전 금지. 별표(*)도 사용 금지.
- 이모지 📊 💡 💭 🎯 ⚠️ + 특수문자 ━ ▶ ■ ◆ ① ② ③ 활용
- 긴 선 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 로 섹션 구분
- 중요 키워드는 『』나 「」로 감싸기
- 2-3문장마다 줄바꿈으로 호흡 조절
- 짧은 문장과 긴 문장을 조화롭게 배치하여 리듬감 유지

**[절대 금지사항]**
- "네, 제공된", "본 분석은", "자막이 없어서" 등 메타 설명 금지
- 어떤 서론, 안내문, 인사말도 쓰지 말 것
- 바로 첫 줄부터 "━━━━" 구분선 → "📊 핵심 인사이트" 형태로 시작
- 마크다운 문법(#, *, -, ```) 일체 사용 금지

**[품질 기준]**
- 전체 길이: 1500-2000자
- 문단당 150-200자 내외
- 자막 정보 보존율 80% 이상
- 8가지 작성 원칙이 모두 반영되었는지 자체 검증 후 출력

지금 분석을 시작해주세요.
"""
        return self._generate(prompt)

    # =========================================================
    # 다중 영상 통합 분석
    # =========================================================
    def analyze_multiple(self, transcripts: List[str]) -> str:
        """
        여러 영상 통합 분석 - 비교 및 종합
        """
        transcript_sections = ""
        for i, t in enumerate(transcripts, 1):
            # 각 자막이 너무 길면 앞부분만 사용
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
# 호환성 함수 (기존 코드용)
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
