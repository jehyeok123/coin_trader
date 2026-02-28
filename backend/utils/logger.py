import logging
from datetime import datetime
from pathlib import Path

from .markdown_helper import MarkdownHelper

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class TradingLogger:
    """Markdown 형식으로 트레이딩 로그를 기록하는 로거"""

    def __init__(self, name: str = "coin_trader"):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            console.setFormatter(
                logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
            )
            self._logger.addHandler(console)

    def _get_daily_log_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return LOG_DIR / f"trading_{today}.md"

    def _append_to_daily_log(self, content: str):
        log_path = self._get_daily_log_path()
        if not log_path.exists():
            header = MarkdownHelper.heading(
                f"Trading Log - {datetime.now():%Y-%m-%d}", level=1
            )
            header += "\n" + MarkdownHelper.table_header(
                ["시간", "유형", "내용", "상세"]
            )
            log_path.write_text(header + "\n", encoding="utf-8")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def trade(self, symbol: str, side: str, price: float, amount: float, reason: str):
        msg = f"[TRADE] {side.upper()} {symbol} @ {price:,.0f} KRW ({amount:,.0f} KRW) - {reason}"
        self._logger.info(msg)
        md_line = (
            f"| {datetime.now():%H:%M:%S} "
            f"| {'🟢 BUY' if side == 'buy' else '🔴 SELL'} "
            f"| `{symbol}` @ {price:,.0f} KRW "
            f"| {reason} |"
        )
        self._append_to_daily_log(md_line)

    def signal(self, source: str, action: str, symbol: str, summary: str):
        msg = f"[SIGNAL] {source}/{action} {symbol} - {summary}"
        self._logger.info(msg)
        icon = {"news": "📰", "twitter": "🐦", "technical": "📊"}.get(source, "❓")
        md_line = (
            f"| {datetime.now():%H:%M:%S} "
            f"| {icon} SIGNAL "
            f"| {action.upper()} `{symbol}` "
            f"| {summary} |"
        )
        self._append_to_daily_log(md_line)

    def info(self, message: str, details: str = ""):
        self._logger.info(message)
        md_line = f"| {datetime.now():%H:%M:%S} | ℹ️ INFO | {message} | {details} |"
        self._append_to_daily_log(md_line)

    def warning(self, message: str, details: str = ""):
        self._logger.warning(message)
        md_line = f"| {datetime.now():%H:%M:%S} | ⚠️ WARN | {message} | {details} |"
        self._append_to_daily_log(md_line)

    def error(self, message: str, details: str = ""):
        self._logger.error(message)
        md_line = f"| {datetime.now():%H:%M:%S} | ❌ ERROR | {message} | {details} |"
        self._append_to_daily_log(md_line)


logger = TradingLogger()
