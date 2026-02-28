from fastapi import APIRouter

from .trading import router as trading_router
from .rules import router as rules_router
from .charts import router as charts_router
from .signals import router as signals_router
from .settings import router as settings_router

api_router = APIRouter(prefix="/api")
api_router.include_router(trading_router)
api_router.include_router(rules_router)
api_router.include_router(charts_router)
api_router.include_router(signals_router)
api_router.include_router(settings_router)
