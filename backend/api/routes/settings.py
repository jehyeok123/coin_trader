import time

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    news_interval_minutes: int | None = None
    twitter_accounts: list[str] | None = None
    twitter_interval_seconds: int | None = None


@router.get("")
async def get_settings():
    """현재 설정 조회"""
    from backend.main import get_scheduler
    from backend.config import settings

    scheduler = get_scheduler()
    scheduler_status = await scheduler.get_status() if scheduler else {}

    # 활성 Gemini 모델명
    gemini_model = ""
    if scheduler:
        gemini_model = scheduler.news_monitor._analyzer.active_model_name

    return {
        "upbit_connected": bool(settings.upbit_access_key),
        "gemini_connected": bool(settings.gemini_api_key),
        "gemini_model": gemini_model,
        "news_interval_minutes": settings.news_check_interval_minutes,
        "twitter_accounts": settings.twitter_accounts,
        "twitter_interval_seconds": settings.twitter_check_interval_seconds,
        "system_status": scheduler_status,
    }


@router.get("/test-connection")
async def test_api_connection():
    """API 연결 실제 테스트 - 업비트/Gemini API를 실제로 호출하여 확인 (latency 포함)"""
    from backend.main import get_broker
    from backend.config import settings
    from backend.signals.gemini_analyzer import MODEL_PRIORITY
    import pyupbit
    import httpx
    import feedparser

    results = {
        "upbit": {
            "key_exists": False, "public_api": False, "authenticated": False,
            "error": None, "latency_ms": None,
        },
        "gemini": {
            "key_exists": False, "connected": False, "model": None,
            "error": None, "latency_ms": None,
        },
        "twitter": {
            "reachable": False, "error": None, "latency_ms": None,
        },
    }

    # 1. 업비트 공개 API 테스트 + latency
    t0 = time.time()
    try:
        tickers = pyupbit.get_tickers(fiat="KRW")
        if tickers and len(tickers) > 0:
            results["upbit"]["public_api"] = True
    except Exception as e:
        results["upbit"]["error"] = f"공개 API 실패: {str(e)}"
    results["upbit"]["latency_ms"] = round((time.time() - t0) * 1000)

    # 2. 업비트 인증 API 테스트
    if settings.upbit_access_key and settings.upbit_secret_key:
        results["upbit"]["key_exists"] = True
        broker = get_broker()
        if broker:
            try:
                t1 = time.time()
                balance = await broker.get_balance()
                auth_latency = round((time.time() - t1) * 1000)
                if isinstance(balance, dict) and "krw" in balance:
                    results["upbit"]["authenticated"] = True
                    results["upbit"]["krw_balance"] = balance["krw"]
                    results["upbit"]["auth_latency_ms"] = auth_latency
                else:
                    results["upbit"]["error"] = "잔고 조회 결과가 올바르지 않습니다."
            except Exception as e:
                error_msg = str(e)
                if "허용되지 않은 IP" in error_msg or "no_authorization_ip" in error_msg:
                    results["upbit"]["error"] = (
                        "업비트 API 키의 허용 IP에 현재 IP가 등록되지 않았습니다. "
                        "업비트 > 마이페이지 > Open API 관리에서 IP를 추가하세요."
                    )
                else:
                    results["upbit"]["error"] = f"인증 실패: {error_msg}"
    else:
        results["upbit"]["error"] = "API 키가 .env 파일에 설정되지 않았습니다."

    # 3. 트위터 RSS/Nitter 연결 테스트 + latency
    nitter_url = settings.nitter_instance_url.rstrip("/")
    test_account = settings.twitter_accounts[0] if settings.twitter_accounts else "elonmusk"
    t2 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{nitter_url}/{test_account}/rss")
            results["twitter"]["latency_ms"] = round((time.time() - t2) * 1000)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.text)
                results["twitter"]["reachable"] = len(feed.entries) > 0
                results["twitter"]["entries_count"] = len(feed.entries)
            else:
                results["twitter"]["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        results["twitter"]["latency_ms"] = round((time.time() - t2) * 1000)
        results["twitter"]["error"] = f"연결 실패: {str(e)}"

    # 4. Gemini API 테스트 (모델 fallback) + latency
    if settings.gemini_api_key:
        results["gemini"]["key_exists"] = True
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)

        for model_name in MODEL_PRIORITY:
            try:
                model = genai.GenerativeModel(model_name)
                t3 = time.time()
                response = model.generate_content("Say 'ok' in one word.")
                latency = round((time.time() - t3) * 1000)
                if response and response.text:
                    results["gemini"]["connected"] = True
                    results["gemini"]["model"] = model_name
                    results["gemini"]["latency_ms"] = latency
                    break
            except Exception as e:
                error_str = str(e)
                is_quota = "429" in error_str or "quota" in error_str.lower()
                is_unavailable = "404" in error_str or "no longer available" in error_str.lower()

                if is_quota or is_unavailable:
                    continue
                else:
                    results["gemini"]["error"] = f"Gemini API 실패: {error_str}"
                    break
        else:
            if not results["gemini"]["connected"]:
                results["gemini"]["error"] = (
                    f"모든 모델({', '.join(MODEL_PRIORITY)})의 할당량 초과 또는 사용 불가. "
                    "잠시 후 다시 시도하세요."
                )
    else:
        results["gemini"]["error"] = "GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다."

    return results


@router.put("")
async def update_settings(body: SettingsUpdate):
    """설정 변경 (런타임)"""
    from backend.main import get_scheduler
    scheduler = get_scheduler()

    updated = []

    if body.news_interval_minutes is not None and scheduler:
        scheduler.set_news_interval(body.news_interval_minutes)
        updated.append(f"뉴스 간격: {body.news_interval_minutes}분")

    if body.twitter_accounts is not None and scheduler:
        scheduler.set_twitter_accounts(body.twitter_accounts)
        updated.append(f"트위터 계정: {body.twitter_accounts}")

    if not updated:
        return {"success": False, "message": "변경 사항이 없습니다."}

    return {
        "success": True,
        "message": "설정이 업데이트되었습니다.",
        "updated": updated,
    }
