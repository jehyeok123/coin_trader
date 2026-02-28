from datetime import datetime


class MarkdownHelper:
    """Markdown 문서 생성을 위한 유틸리티 클래스"""

    @staticmethod
    def heading(text: str, level: int = 1) -> str:
        return f"{'#' * level} {text}\n"

    @staticmethod
    def bold(text: str) -> str:
        return f"**{text}**"

    @staticmethod
    def code(text: str) -> str:
        return f"`{text}`"

    @staticmethod
    def code_block(text: str, language: str = "") -> str:
        return f"```{language}\n{text}\n```\n"

    @staticmethod
    def table_header(columns: list[str]) -> str:
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        return f"{header}\n{separator}"

    @staticmethod
    def table_row(values: list[str]) -> str:
        return "| " + " | ".join(str(v) for v in values) + " |"

    @staticmethod
    def bullet(text: str, indent: int = 0) -> str:
        return f"{'  ' * indent}- {text}"

    @staticmethod
    def timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def trade_summary(trades: list[dict]) -> str:
        """거래 내역을 Markdown 테이블로 변환"""
        if not trades:
            return "> 거래 내역이 없습니다.\n"
        lines = [
            MarkdownHelper.heading("거래 내역", 2),
            MarkdownHelper.table_header(
                ["시간", "종류", "종목", "가격", "금액", "사유"]
            ),
        ]
        for t in trades:
            side_emoji = "🟢" if t.get("side") == "buy" else "🔴"
            lines.append(
                MarkdownHelper.table_row([
                    t.get("created_at", "-"),
                    f"{side_emoji} {t.get('side', '-').upper()}",
                    f"`{t.get('symbol', '-')}`",
                    f"{t.get('price', 0):,.0f}",
                    f"{t.get('amount_krw', 0):,.0f}",
                    t.get("reason", "-"),
                ])
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def portfolio_summary(positions: list[dict], total_krw: float) -> str:
        """포트폴리오를 Markdown으로 출력"""
        lines = [
            MarkdownHelper.heading("포트폴리오 요약", 2),
            f"> 총 자산: **{total_krw:,.0f} KRW**\n",
        ]
        if positions:
            lines.append(
                MarkdownHelper.table_header(
                    ["종목", "수량", "평균 단가", "현재가", "수익률"]
                )
            )
            for p in positions:
                pnl = p.get("pnl_pct", 0)
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                lines.append(
                    MarkdownHelper.table_row([
                        f"`{p.get('symbol', '-')}`",
                        f"{p.get('quantity', 0):.8f}",
                        f"{p.get('avg_price', 0):,.0f}",
                        f"{p.get('current_price', 0):,.0f}",
                        f"{pnl_emoji} {pnl:+.2f}%",
                    ])
                )
        else:
            lines.append("> 보유 중인 포지션이 없습니다.\n")
        return "\n".join(lines) + "\n"
