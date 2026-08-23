"""
Market Data Client — Finnhub Free API
Handles rate limiting, retries, and caching.
Free tier: 60 req/min, 30 calls/sec
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

import httpx

logger = logging.getLogger(__name__)

FINNHUB_KEY   = os.getenv("NEWS_API_KEY")
BASE_URL      = "https://finnhub.io/api/v1"
RATE_LIMIT    = 55   # conservative, under 60/min
CACHE_TTL     = 60   # seconds for quote cache
CANDLE_CACHE  = 300  # 5 min for candle cache


class RateLimiter:
    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps older than 60 seconds
            self._timestamps = [t for t in self._timestamps if now - t < 60]
            if len(self._timestamps) >= self.calls_per_minute:
                sleep_for = 60 - (now - self._timestamps[0]) + 0.1
                logger.debug(f"Rate limit hit, sleeping {sleep_for:.2f}s")
                await asyncio.sleep(sleep_for)
                self._timestamps = []
            self._timestamps.append(time.monotonic())


class SimpleCache:
    def __init__(self):
        self._store: dict[str, tuple] = {}  # key -> (value, expires_at)

    def get(self, key: str):
        if key in self._store:
            val, exp = self._store[key]
            if time.monotonic() < exp:
                return val
            del self._store[key]
        return None

    def set(self, key: str, value, ttl: int):
        self._store[key] = (value, time.monotonic() + ttl)


class MarketDataClient:
    def __init__(self):
        self._limiter = RateLimiter(RATE_LIMIT)
        self._cache   = SimpleCache()
        self._client  = httpx.AsyncClient(
            base_url=BASE_URL,
            params={"token": FINNHUB_KEY},
            timeout=15.0,
            headers={"User-Agent": "TradingBot/1.0"}
        )

    async def _get(self, path: str, params: dict = None, retries: int = 3) -> dict:
        await self._limiter.acquire()
        for attempt in range(retries):
            try:
                r = await self._client.get(path, params=params or {})
                r.raise_for_status()
                data = r.json()
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait = 2 ** attempt * 10
                    logger.warning(f"429 rate limit, waiting {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise
            except httpx.RequestError as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"Failed after {retries} retries: {path}")

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_quote(self, ticker: str) -> dict:
        cache_key = f"quote:{ticker}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        data = await self._get("/quote", {"symbol": ticker})
        if not data.get("c"):
            raise ValueError(f"No quote data for {ticker}")

        quote = {
            "current":   data["c"],
            "open":      data["o"],
            "high":      data["h"],
            "low":       data["l"],
            "prev_close":data["pc"],
            "change":    data["c"] - data["pc"],
            "change_pct":(data["c"] - data["pc"]) / data["pc"] * 100 if data["pc"] else 0,
        }
        self._cache.set(cache_key, quote, CACHE_TTL)
        return quote

    async def get_candles(
        self, ticker: str, resolution: str = "D",
        count: int = 100, from_ts: int = None, to_ts: int = None
    ) -> dict:
        """
        resolution: 1, 5, 15, 30, 60, D, W, M
        Returns: {t, o, h, l, c, v} lists
        """
        cache_key = f"candles:{ticker}:{resolution}:{count}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        now = int(datetime.utcnow().timestamp())
        if not to_ts:
            to_ts = now
        if not from_ts:
            # Estimate enough bars going back
            seconds_map = {"1":60,"5":300,"15":900,"30":1800,"60":3600,"D":86400,"W":604800}
            secs = seconds_map.get(resolution, 86400)
            from_ts = now - (secs * count * 2)  # 2x buffer for weekends/holidays

        data = await self._get("/stock/candle", {
            "symbol": ticker,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
        })

        if data.get("s") != "ok" or not data.get("c"):
            raise ValueError(f"No candle data for {ticker} ({resolution})")

        candles = {
            "t": data["t"],
            "o": data["o"],
            "h": data["h"],
            "l": data["l"],
            "c": data["c"],
            "v": data["v"],
        }
        self._cache.set(cache_key, candles, CANDLE_CACHE)
        return candles

    async def get_news(self, ticker: str, limit: int = 5) -> list[dict]:
        cache_key = f"news:{ticker}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached[:limit]

        today  = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        data = await self._get("/company-news", {
            "symbol": ticker,
            "from": week_ago.isoformat(),
            "to": today.isoformat(),
        })

        if not isinstance(data, list):
            return []

        articles = [
            {
                "headline": item.get("headline", ""),
                "summary":  item.get("summary", ""),
                "datetime": item.get("datetime", 0),
                "source":   item.get("source", ""),
                "url":      item.get("url", ""),
            }
            for item in data[:limit]
            if item.get("headline")
        ]
        self._cache.set(cache_key, articles, 600)
        return articles

    async def get_company_profile(self, ticker: str) -> dict:
        cache_key = f"profile:{ticker}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        data = await self._get("/stock/profile2", {"symbol": ticker})
        if not data.get("name"):
            raise ValueError(f"No profile for {ticker}")
        self._cache.set(cache_key, data, 3600)
        return data

    async def validate_ticker(self, ticker: str) -> bool:
        try:
            quote = await self.get_quote(ticker)
            return bool(quote.get("current"))
        except Exception:
            return False

    async def get_market_status(self) -> dict:
        return await self._get("/stock/market-status", {"exchange": "US"})

    async def close(self):
        await self._client.aclose()