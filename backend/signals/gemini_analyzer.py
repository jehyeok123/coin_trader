import json
import google.generativeai as genai

from backend.config import settings
from backend.utils.logger import logger


ANALYSIS_PROMPT = """당신은 암호화폐 시장 분석 전문가입니다.
아래 뉴스/소셜미디어 내용을 분석하여 매매 시그널을 JSON 형태로 반환해주세요.

## 분석 내용:
{content}

## 응답 형식 (JSON):
{{
  "signals": [
    {{
      "action": "buy" | "sell" | "hold",
      "symbol": "KRW-BTC 형태의 업비트 심볼 (확실하지 않으면 null)",
      "confidence": 0.0 ~ 1.0 사이의 신뢰도,
      "summary": "1줄 요약 (한국어)"
    }}
  ]
}}

## 규칙:
1. 확실하지 않은 시그널은 confidence를 낮게 설정하세요.
2. 명확한 근거가 없으면 "hold"로 반환하세요.
3. summary는 반드시 1줄로 요약하세요.
4. 심볼은 업비트 형식(KRW-BTC, KRW-ETH 등)으로 반환하세요.
5. JSON만 반환하세요. 다른 텍스트는 포함하지 마세요.
"""

# 모델 우선순위: 최신 모델 먼저 시도, 할당량 초과 시 다음 모델로 fallback
MODEL_PRIORITY = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


class GeminiAnalyzer:
    """Google Gemini API를 활용한 뉴스/소셜미디어 분석기 (자동 모델 fallback)"""

    def __init__(self):
        self._models: list[genai.GenerativeModel] = []
        self._active_model_name: str = ""
        self._configured = False

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            for name in MODEL_PRIORITY:
                self._models.append(genai.GenerativeModel(name))
            self._active_model_name = MODEL_PRIORITY[0]
            self._configured = True
            logger.info(f"Gemini 분석기 초기화 완료 (모델: {', '.join(MODEL_PRIORITY)})")
        else:
            logger.warning("Gemini API 키가 설정되지 않았습니다.")

    @property
    def active_model_name(self) -> str:
        return self._active_model_name

    async def _call_with_fallback(self, prompt: str) -> str:
        """모델 우선순위에 따라 호출, 할당량 초과 시 다음 모델로 fallback"""
        if not self._configured or not self._models:
            logger.warning("Gemini 모델이 초기화되지 않았습니다.")
            return ""

        last_error = None
        for i, model in enumerate(self._models):
            model_name = MODEL_PRIORITY[i]
            try:
                response = await model.generate_content_async(prompt)
                if response and response.text:
                    self._active_model_name = model_name
                    return response.text.strip()
            except Exception as e:
                error_str = str(e)
                last_error = e
                is_quota = "429" in error_str or "quota" in error_str.lower()
                is_unavailable = "404" in error_str or "no longer available" in error_str.lower()

                if is_quota or is_unavailable:
                    reason = "할당량 초과" if is_quota else "모델 사용 불가"
                    logger.warning(f"Gemini {model_name} {reason}, 다음 모델로 전환 시도...")
                    continue
                else:
                    # 할당량/모델 문제가 아닌 다른 에러는 즉시 실패
                    raise

        # 모든 모델 실패
        if last_error:
            raise last_error
        return ""

    async def analyze(self, content: str) -> list[dict]:
        """텍스트 내용을 분석하여 매매 시그널 반환."""
        try:
            prompt = ANALYSIS_PROMPT.format(content=content)
            text = await self._call_with_fallback(prompt)
            if not text:
                return []

            # 코드 블록 제거
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)
            signals = result.get("signals", [])
            logger.info(f"Gemini 분석 완료 ({self._active_model_name}): {len(signals)}개 시그널")
            return signals

        except json.JSONDecodeError as e:
            logger.error(f"Gemini 응답 JSON 파싱 실패: {e}")
            return []
        except Exception as e:
            logger.error(f"Gemini 분석 실패: {e}")
            return []

    async def search_and_analyze(self, query: str) -> list[dict]:
        """Gemini를 활용하여 최신 뉴스를 검색하고 분석."""
        try:
            search_prompt = (
                f"다음 주제에 대한 최신 암호화폐 관련 뉴스를 검색하고 분석해주세요:\n"
                f"주제: {query}\n\n"
                f"최근 뉴스와 커뮤니티 반응을 바탕으로 매매 시그널을 "
                f"아래 JSON 형식으로 반환해주세요:\n\n"
                f'{{"signals": [{{"action": "buy|sell|hold", '
                f'"symbol": "KRW-BTC 형태 또는 null", '
                f'"confidence": 0.0~1.0, '
                f'"summary": "1줄 요약"}}]}}\n\n'
                f"JSON만 반환하세요."
            )

            text = await self._call_with_fallback(search_prompt)
            if not text:
                return []

            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)
            return result.get("signals", [])

        except Exception as e:
            logger.error(f"Gemini 검색 분석 실패: {e}")
            return []
