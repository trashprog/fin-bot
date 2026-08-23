"""
LLM Trading Advisor
Primary:  Groq API  (free tier — llama-3.3-70b-versatile)
Fallback: Google Gemini (free tier — gemini-1.5-flash)

Sends structured market data → receives trading recommendation + reasoning.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

SYSTEM_PROMPT = """You are an expert quantitative trading analyst for US equities traded on Moomoo.
Your role is to synthesize technical indicators, price action, and recent news to provide
actionable trading insights.

RESPONSE FORMAT (always valid JSON, no markdown):
{
  "recommendation": "BUY | SELL | HOLD",
  "confidence": 0-100,
  "timeframe": "intraday | swing (1-5 days) | position (1-4 weeks)",
  "entry_zone": "price range or 'current market'",
  "stop_loss": "price level",
  "target_1": "first price target",
  "target_2": "second price target",
  "risk_reward": "ratio e.g. 1:2.5",
  "key_reasons": ["reason 1", "reason 2", "reason 3"],
  "risks": ["risk 1", "risk 2"],
  "sentiment": "bullish | bearish | neutral",
  "summary": "2-3 sentence plain English summary"
}

Rules:
- Be conservative: only recommend BUY/SELL when confidence >= 60
- Always consider risk management (stop loss mandatory)
- If data is insufficient, say HOLD with low confidence
- Never guarantee profits or give financial advice disclaimers (users understand this is algorithmic)
"""


class LLMAdvisor:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    def _build_prompt(
        self, ticker: str, quote: dict, indicators: dict,
        news: list, signal_score: dict
    ) -> str:
        news_text = "\n".join([
            f"- [{n['source']}] {n['headline']}"
            for n in news[:3]
        ]) or "No recent news available."

        signals_text = "\n".join([
            f"  • {s['name']}: {s['score']:+.0f} — {s['reason']}"
            for s in signal_score.get("signals", [])
        ])

        return f"""TICKER: {ticker}
DATE: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

PRICE ACTION:
- Current: ${quote['current']:.2f}
- Day Change: {quote['change_pct']:+.2f}%
- High/Low: ${quote['high']:.2f} / ${quote['low']:.2f}
- Prev Close: ${quote['prev_close']:.2f}

TECHNICAL INDICATORS:
- RSI(14): {indicators.get('rsi', 'N/A'):.1f if indicators.get('rsi') else 'N/A'}
- MACD Histogram: {indicators.get('macd_hist', 0):.4f}
- EMA9/21/50/200: ${indicators.get('ema9', 0) or 0:.2f} / ${indicators.get('ema21', 0) or 0:.2f} / ${indicators.get('ema50', 0) or 0:.2f} / ${indicators.get('ema200', 0) or 0:.2f}
- Bollinger Position: {(indicators.get('bb_position', 0.5)*100):.0f}% (0=lower band, 100=upper band)
- ATR(14): ${indicators.get('atr', 0) or 0:.2f}
- Volume Ratio vs 20-day avg: {indicators.get('volume_ratio', 1.0):.2f}x
- Trend: {indicators.get('trend', 'UNKNOWN')}

SIGNAL SCORES (-100 to +100):
{signals_text}
Composite Score: {signal_score.get('composite', 0):+.1f} → {signal_score.get('action', 'UNKNOWN')}

RECENT NEWS:
{news_text}

Analyse this data and provide your trading recommendation as a JSON object."""

    async def _call_groq(self, prompt: str) -> dict:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set")

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens":  600,
            "response_format": {"type": "json_object"},
        }
        r = await self._client.post(
            GROQ_URL,
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    async def _call_gemini(self, prompt: str) -> dict:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set")

        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}\n\nRespond with ONLY valid JSON, no markdown."
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600,
            }
        }
        r = await self._client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        # Strip any accidental markdown fencing
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(text)

    async def analyse(
        self, ticker: str, quote: dict, indicators: dict,
        news: list, signal_score: dict
    ) -> dict:
        prompt = self._build_prompt(ticker, quote, indicators, news, signal_score)

        # Try Groq first (faster, free), fall back to Gemini
        for attempt, (name, call) in enumerate([
            ("Groq",   lambda: self._call_groq(prompt)),
            ("Gemini", lambda: self._call_gemini(prompt)),
        ]):
            try:
                logger.info(f"LLM call via {name} for {ticker}")
                result = await call()
                result["_llm_provider"] = name
                return result
            except Exception as e:
                logger.warning(f"LLM {name} failed for {ticker}: {e}")
                if attempt == 1:
                    # Both failed — return rule-based fallback
                    return self._fallback(signal_score)

    def _fallback(self, signal_score: dict) -> dict:
        """Pure rule-based decision when both LLMs fail."""
        score = signal_score.get("composite", 0)
        if score >= 60:
            rec, sentiment = "BUY",  "bullish"
        elif score <= -60:
            rec, sentiment = "SELL", "bearish"
        else:
            rec, sentiment = "HOLD", "neutral"

        return {
            "recommendation": rec,
            "confidence":     abs(score),
            "timeframe":      "swing (1-5 days)",
            "entry_zone":     "current market",
            "stop_loss":      "Set manually based on ATR",
            "target_1":       "N/A — LLM unavailable",
            "target_2":       "N/A",
            "risk_reward":    "N/A",
            "key_reasons":    [s["reason"] for s in signal_score.get("signals", [])[:3]],
            "risks":          ["LLM analysis unavailable", "Use with caution"],
            "sentiment":      sentiment,
            "summary":        f"Rule-based {rec} signal (composite: {score:+.0f}). LLM analysis temporarily unavailable.",
            "_llm_provider":  "fallback_rules",
        }

    async def close(self):
        await self._client.aclose()