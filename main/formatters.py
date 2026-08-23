"""
Message Formatter — all Telegram message templates.
Uses Markdown V1 (safe for all Telegram clients).
"""

from datetime import datetime


def _action_emoji(action: str) -> str:
    icons = {
        "STRONG BUY": "🚀", "BUY": "✅", "WEAK BUY": "📈",
        "STRONG SELL": "🔴", "SELL": "❌", "WEAK SELL": "📉",
        "HOLD / NEUTRAL": "⏸️",
    }
    return icons.get(action, "❓")


def _score_bar(score: float) -> str:
    """Visual score bar: -100 to +100."""
    normalized = int((score + 100) / 200 * 10)  # 0-10
    filled = "█" * normalized
    empty  = "░" * (10 - normalized)
    return f"`[{filled}{empty}]` {score:+.0f}"


def _confidence_stars(conf: float) -> str:
    stars = int(conf / 20)
    return "⭐" * stars + "☆" * (5 - stars)


class MessageFormatter:

    def welcome_message(self, name: str) -> str:
        return (
            f"👋 *Welcome, {name}!*\n\n"
            "I'm your AI-powered trading analyst for Moomoo.\n\n"
            "I combine *RSI*, *MACD*, *Bollinger Bands*, *Moving Averages*, "
            "and *LLM reasoning* to surface high-probability setups.\n\n"
            "⚠️ _This bot provides analysis only — not financial advice. "
            "Always do your own due diligence._\n\n"
            "Use the menu below to get started:"
        )

    def help_text(self) -> str:
        return (
            "📖 *Commands*\n\n"
            "`/analyse AAPL` — Full AI analysis of a ticker\n"
            "`/watch AAPL TSLA` — Add tickers to watchlist\n"
            "`/watch` — Show current watchlist\n"
            "`/remove AAPL` — Remove from watchlist\n"
            "`/scan` — Scan all watchlist tickers for signals\n"
            "`/price AAPL` — Quick price + change\n"
            "`/report` — Daily market report\n"
            "`/help` — Show this message\n\n"
            "🔔 *Auto-alerts*: Strong signals (score ≥65) trigger instant alerts.\n"
            "📅 *Daily report*: Sent at 9 AM ET every trading day."
        )

    def watchlist_display(self, tickers: list) -> str:
        if not tickers:
            return "📋 *Watchlist is empty.*\nUse `/watch AAPL` to add tickers."
        rows = "\n".join(f"  • `{t}`" for t in tickers)
        return f"📋 *Watchlist* ({len(tickers)} tickers)\n\n{rows}"

    def quote_display(self, ticker: str, quote: dict) -> str:
        direction = "🟢" if quote["change_pct"] >= 0 else "🔴"
        return (
            f"{direction} *{ticker}*\n"
            f"Price:  `${quote['current']:.2f}`\n"
            f"Change: `{quote['change_pct']:+.2f}%`  (${quote['change']:+.2f})\n"
            f"H/L:    `${quote['high']:.2f}` / `${quote['low']:.2f}`\n"
            f"Prev:   `${quote['prev_close']:.2f}`"
        )

    def full_analysis_report(
        self, ticker: str, quote: dict, indicators: dict,
        signal_score: dict, llm: dict, news: list
    ) -> str:
        action    = signal_score.get("action", "UNKNOWN")
        composite = signal_score.get("composite", 0)
        rec       = llm.get("recommendation", "HOLD")
        conf      = llm.get("confidence", 0)
        provider  = llm.get("_llm_provider", "?")

        direction = "🟢" if quote["change_pct"] >= 0 else "🔴"

        # Signals breakdown
        sig_lines = "\n".join([
            f"  {_action_emoji(s['name'])} *{s['name']}*: {s['score']:+.0f} — _{s['reason']}_"
            for s in signal_score.get("signals", [])
        ])

        # News
        news_lines = "\n".join([
            f"  • {n['headline'][:80]}..." if len(n['headline']) > 80 else f"  • {n['headline']}"
            for n in news[:3]
        ]) or "  _No recent news_"

        # LLM section
        key_reasons = "\n".join(f"  ✓ {r}" for r in llm.get("key_reasons", [])[:3])
        risks       = "\n".join(f"  ⚠️ {r}" for r in llm.get("risks", [])[:2])

        return (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *{ticker} Analysis*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{direction} *${quote['current']:.2f}*  ({quote['change_pct']:+.2f}%)\n\n"

            f"*🤖 AI Recommendation*\n"
            f"{_action_emoji(rec)} *{rec}*  |  Confidence: {_confidence_stars(conf)} ({conf:.0f}%)\n"
            f"Timeframe: _{llm.get('timeframe', 'N/A')}_  |  Provider: _{provider}_\n\n"

            f"*📐 Trade Levels*\n"
            f"  Entry:    `{llm.get('entry_zone', 'N/A')}`\n"
            f"  Stop:     `{llm.get('stop_loss', 'N/A')}`\n"
            f"  Target 1: `{llm.get('target_1', 'N/A')}`\n"
            f"  Target 2: `{llm.get('target_2', 'N/A')}`\n"
            f"  R:R       `{llm.get('risk_reward', 'N/A')}`\n\n"

            f"*📈 Signal Scores*\n"
            f"  Composite: {_score_bar(composite)}\n"
            f"  Action:    *{action}*\n\n"
            f"{sig_lines}\n\n"

            f"*🔧 Key Technicals*\n"
            f"  RSI(14): `{indicators.get('rsi', 0) or 0:.1f}`  "
            f"MACD Hist: `{indicators.get('macd_hist', 0) or 0:.4f}`\n"
            f"  EMA50: `${indicators.get('ema50', 0) or 0:.2f}`  "
            f"EMA200: `${indicators.get('ema200', 0) or 0:.2f}`\n"
            f"  BB Pos: `{(indicators.get('bb_position', 0.5) or 0.5)*100:.0f}%`  "
            f"Vol Ratio: `{indicators.get('volume_ratio', 1.0) or 1.0:.2f}x`\n"
            f"  Trend: `{indicators.get('trend', 'N/A')}`  "
            f"ATR: `${indicators.get('atr', 0) or 0:.2f}`\n\n"

            f"*💡 AI Reasoning*\n"
            f"{key_reasons}\n\n"
            f"*⚠️ Risks*\n"
            f"{risks}\n\n"

            f"*📰 News*\n"
            f"{news_lines}\n\n"

            f"*Summary:* _{llm.get('summary', 'N/A')}_\n\n"
            f"_⚠️ Not financial advice. {datetime.utcnow().strftime('%H:%M UTC')}_"
        )

    def scan_results(self, results: list) -> str:
        if not results:
            return "❌ Scan failed — no data returned."

        lines = ["🔎 *Watchlist Scan Results*\n"]
        for r in results:
            score  = r["score"]
            action = score["action"]
            comp   = score["composite"]
            emoji  = _action_emoji(action)
            change = r.get("change_pct", 0)
            dir_e  = "🟢" if change >= 0 else "🔴"
            lines.append(
                f"{emoji} *{r['ticker']}*  ${r['price']:.2f}  {dir_e}{change:+.2f}%\n"
                f"   Score: {comp:+.0f} → _{action}_\n"
            )

        lines.append(f"\n_Scanned {len(results)} tickers at {datetime.utcnow().strftime('%H:%M UTC')}_")
        return "\n".join(lines)

    def alert_message(self, alerts: list) -> str:
        lines = ["🚨 *TRADING ALERT* 🚨\n"]
        for ticker, quote, indicators, score in alerts:
            action = score["action"]
            comp   = score["composite"]
            emoji  = _action_emoji(action)
            lines.append(
                f"{emoji} *{ticker}*  ${quote['current']:.2f}  "
                f"({quote['change_pct']:+.2f}%)\n"
                f"   Signal: *{action}*  |  Score: `{comp:+.0f}`\n"
                f"   RSI: `{indicators.get('rsi', 0) or 0:.1f}`  "
                f"Trend: `{indicators.get('trend', 'N/A')}`\n"
                f"   _Use /analyse {ticker} for full report_\n"
            )
        lines.append("_⚠️ Signals only — not financial advice_")
        return "\n".join(lines)

    def daily_report(self, results: list) -> str:
        if not results:
            return "📊 *Daily Report*\n\nNo watchlist data available."

        lines = [
            f"📊 *Daily Market Report*\n"
            f"_{datetime.utcnow().strftime('%A, %B %d %Y')}_\n"
        ]

        buys   = [(t, q, i, s) for t, q, i, s in results if s["composite"] >= 40]
        sells  = [(t, q, i, s) for t, q, i, s in results if s["composite"] <= -40]
        holds  = [(t, q, i, s) for t, q, i, s in results if -40 < s["composite"] < 40]

        if buys:
            lines.append("✅ *BUY Signals*")
            for t, q, i, s in buys:
                lines.append(f"  🚀 `{t}` ${q['current']:.2f} ({q['change_pct']:+.2f}%) — _{s['action']}_")

        if sells:
            lines.append("\n❌ *SELL Signals*")
            for t, q, i, s in sells:
                lines.append(f"  🔴 `{t}` ${q['current']:.2f} ({q['change_pct']:+.2f}%) — _{s['action']}_")

        if holds:
            lines.append("\n⏸️ *Neutral*")
            for t, q, i, s in holds:
                lines.append(f"  ⚪ `{t}` ${q['current']:.2f} ({q['change_pct']:+.2f}%)")

        lines.append(f"\n_⚠️ Not financial advice. {len(results)} tickers scanned._")
        return "\n".join(lines)