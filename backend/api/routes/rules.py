from fastapi import APIRouter
from pydantic import BaseModel

from backend.config.settings import load_trading_rules, save_trading_rules, RULES_FILE

router = APIRouter(prefix="/rules", tags=["Rules"])


class RulesUpdate(BaseModel):
    rules: dict


@router.get("")
async def get_rules():
    """현재 매매 규칙 조회"""
    rules = load_trading_rules()
    return {"rules": rules}


@router.put("")
async def update_rules(body: RulesUpdate):
    """매매 규칙 수정"""
    save_trading_rules(body.rules)

    # 엔진에 규칙 리로드 알림
    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler:
        scheduler._engine.rule_engine.reload_rules()

    return {"success": True, "message": "매매 규칙이 업데이트되었습니다.", "rules": body.rules}


@router.post("/reset")
async def reset_rules():
    """기본 매매 규칙으로 초기화"""
    import json
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        default_rules = json.load(f)
    save_trading_rules(default_rules)

    from backend.main import get_scheduler
    scheduler = get_scheduler()
    if scheduler:
        scheduler._engine.rule_engine.reload_rules()

    return {"success": True, "message": "기본 규칙으로 초기화되었습니다.", "rules": default_rules}
