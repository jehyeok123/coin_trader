from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.db_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """데이터베이스 테이블 생성 + 마이그레이션"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 기존 테이블에 누락된 컬럼 추가 (마이그레이션)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE trades ADD COLUMN fee_krw FLOAT"))
        except Exception:
            pass  # 이미 존재하면 무시


async def get_db():
    """FastAPI Dependency: DB 세션 제공"""
    async with async_session() as session:
        yield session
