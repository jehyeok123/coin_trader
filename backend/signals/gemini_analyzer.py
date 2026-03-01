import json
import google.generativeai as genai

from backend.config import settings
from backend.utils.logger import logger


# 사용자 지정 키워드 점수 기반 시스템 프롬프트 (영어 고정)
SYSTEM_PROMPT = (
    "You are an elite cryptocurrency quantitative analyst. "
    "Your task is to analyze incoming news or tweets and calculate a "
    "'Sentiment Score' strictly based on the provided keyword weights.\n\n"
    "[Step 1: Determine Scope]\n"
    "Determine if the news is about a specific coin ('scope': 'ticker') "
    "or the broad macroeconomic/geopolitical market ('scope': 'macro').\n\n"
    "[Coin-Specific Keyword Scoring Dictionary]\n"
    "Positive:\n"
    " * 'Listing', 'List': +5 (Add +5 more if Binance, Upbit, or Coinbase is mentioned)\n"
    " * 'Approved', 'Approve', 'Acquisition', 'Acquired': +4\n"
    " * 'Partnership', 'Partner', 'Mainnet Launch': +3\n"
    " * 'Burn': +2\n\n"
    "Negative:\n"
    " * 'Hack', 'Hacked', 'Exploit', 'Delist', 'Delisting', 'Bankrupt': -5\n"
    " * 'SEC', 'Lawsuit', 'Sued': -4\n"
    " * 'Delay', 'Halted': -2\n\n"
    "[Macro Keyword Scoring Dictionary]\n"
    "Positive:\n"
    " * 'Rate Cut': +5\n"
    " * 'Lower CPI': +5\n"
    " * 'QE' (Quantitative Easing): +5\n"
    " * 'Stimulus': +5\n\n"
    "Negative:\n"
    " * 'Rate Hike': -5\n"
    " * 'Higher CPI': -5\n"
    " * 'War': -5\n"
    " * 'Invasion': -5\n"
    " * 'Missile': -5\n"
    " * 'Recession': -5\n"
    " * 'Emergency': -5\n\n"
    "[Instructions]\n"
    " * If the news is about a specific cryptocurrency, set scope to 'ticker' "
    "and identify the primary ticker (e.g., BTC, XRP, DOGE).\n"
    " * If the news is about macroeconomic or geopolitical events affecting "
    "the entire market, set scope to 'macro' and ticker to 'ALL'.\n"
    " * Calculate the total sentiment score using ONLY the matching Keyword "
    "Scoring Dictionary above. If no keywords match, the score is 0.\n"
    " * Return the result STRICTLY as a JSON object in the following format, "
    "with no markdown formatting or additional text:\n"
    '   {"scope": "ticker", "ticker": "TICKER_NAME", "score": CALCULATED_SCORE, '
    '"reason": "매칭된 키워드와 뉴스 내용을 한국어로 간단히 요약"}'
)

ANALYZE_PROMPT = "Analyze the following text:\n\n{content}"

SEARCH_PROMPT = (
    "Current UTC time: {current_time}\n"
    "Time window: {time_from} ~ {time_to} (only consider news within this window)\n\n"
    "Search for the latest cryptocurrency breaking news and events "
    "that occurred within the time window above.\n\n"
    "Query: {query}\n\n"
    "IMPORTANT RULES:\n"
    "1. Only consider news published within the specified time window.\n"
    "2. If there is impactful news, analyze it and return a JSON with ticker, score, and reason.\n"
    "3. If there is NO relevant news within the time window, you MUST return:\n"
    '   {{"scope": "none", "ticker": "NONE", "score": 0, "reason": "해당 시간 동안 주요 뉴스 없음"}}\n'
    "4. Return STRICTLY a JSON object, no markdown or extra text."
)

# 모델 우선순위: 최신 모델 먼저 시도, 할당량 초과 시 다음 모델로 fallback
MODEL_PRIORITY = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


class GeminiAnalyzer:
    """Google Gemini API를 활용한 뉴스/소셜미디어 키워드 점수 분석기"""

    def __init__(self):
        self._models: list[genai.GenerativeModel] = []
        self._active_model_name: str = ""
        self._configured = False

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            for name in MODEL_PRIORITY:
                self._models.append(genai.GenerativeModel(
                    name,
                    system_instruction=SYSTEM_PROMPT,
                ))
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
                    raise

        if last_error:
            raise last_error
        return ""

    @staticmethod
    def _parse_json_response(text: str) -> dict | None:
        """Gemini 응답에서 JSON 추출"""
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return None

    async def analyze(self, content: str) -> dict | None:
        """텍스트를 분석하여 키워드 기반 점수 반환.

        Returns:
            dict: {"ticker": "BTC", "score": 5, "reason": "..."} or None
        """
        try:
            prompt = ANALYZE_PROMPT.format(content=content)
            text = await self._call_with_fallback(prompt)
            if not text:
                return None

            result = self._parse_json_response(text)
            if result is None:
                logger.error(f"Gemini 응답 JSON 파싱 실패: {text[:200]}")
                return None

            logger.info(
                f"Gemini 점수 분석 ({self._active_model_name}): "
                f"ticker={result.get('ticker')}, score={result.get('score')}, "
                f"reason={result.get('reason')}"
            )
            return result

        except Exception as e:
            logger.error(f"Gemini 분석 실패: {e}")
            return None

    async def search_and_analyze(
        self, query: str, time_from: str = "", time_to: str = ""
    ) -> dict | None:
        """Gemini를 활용하여 최신 뉴스를 검색하고 점수 분석.

        Args:
            query: 검색 쿼리
            time_from: 검색 시작 시간 (ISO format)
            time_to: 검색 종료 시간 (ISO format)

        Returns:
            dict: {"ticker": "BTC", "score": 5, "reason": "..."} or None
        """
        try:
            from datetime import datetime as dt
            now = dt.utcnow()
            prompt = SEARCH_PROMPT.format(
                query=query,
                current_time=time_to or now.strftime("%Y-%m-%d %H:%M UTC"),
                time_from=time_from or now.strftime("%Y-%m-%d %H:%M UTC"),
                time_to=time_to or now.strftime("%Y-%m-%d %H:%M UTC"),
            )
            text = await self._call_with_fallback(prompt)
            if not text:
                return None

            result = self._parse_json_response(text)
            if result is None:
                logger.error(f"Gemini 검색 응답 JSON 파싱 실패: {text[:200]}")
                return None

            logger.info(
                f"Gemini 검색 분석 ({self._active_model_name}): "
                f"ticker={result.get('ticker')}, score={result.get('score')}"
            )
            return result

        except Exception as e:
            logger.error(f"Gemini 검색 분석 실패: {e}")
            return None
