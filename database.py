# StructureIQ - Database Connection
# Handles all communication with Supabase

import logging
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

def create_supabase_client() -> Client:
    """
    Create and return Supabase client
    Uses service key for full database access
    """
    try:
        client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        logger.info("Supabase connected successfully")
        return client
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        raise e

# Single global instance used by all modules
supabase: Client = create_supabase_client()

# ─── DATABASE HELPER FUNCTIONS ────────────────────────────────

async def save_ohlcv(symbol: str, timeframe: str, candles: list):
    """Save price candles to database"""
    try:
        rows = []
        for c in candles:
            rows.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": c["timestamp"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c.get("volume", 0)
            })
        # Upsert - insert or update if exists
        supabase.table("ohlcv").upsert(rows).execute()
    except Exception as e:
        logger.error(f"Error saving OHLCV data: {e}")

async def save_structure_event(
    symbol: str,
    timeframe: str,
    event_type: str,
    price: float,
    timestamp: str,
    trend: str
):
    """Save a market structure event (HH, HL, BOS, CHoCH etc)"""
    try:
        supabase.table("structure_events").insert({
            "symbol": symbol,
            "timeframe": timeframe,
            "event_type": event_type,
            "price": price,
            "timestamp": timestamp,
            "trend": trend
        }).execute()
    except Exception as e:
        logger.error(f"Error saving structure event: {e}")

async def save_price_zone(
    symbol: str,
    timeframe: str,
    zone_type: str,
    price_high: float,
    price_low: float
):
    """Save a support/resistance or supply/demand zone"""
    try:
        supabase.table("price_zones").insert({
            "symbol": symbol,
            "timeframe": timeframe,
            "zone_type": zone_type,
            "price_high": price_high,
            "price_low": price_low,
            "created_at": "now()"
        }).execute()
    except Exception as e:
        logger.error(f"Error saving price zone: {e}")

async def get_recent_candles(symbol: str, timeframe: str, limit: int = 100):
    """Fetch recent candles from database"""
    try:
        result = supabase.table("ohlcv")\
            .select("*")\
            .eq("symbol", symbol)\
            .eq("timeframe", timeframe)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching candles: {e}")
        return []

async def get_active_signals():
    """Fetch all currently active signals"""
    try:
        result = supabase.table("signals")\
            .select("*")\
            .eq("status", "ACTIVE")\
            .order("created_at", desc=True)\
            .execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        return []

async def update_signal_status(signal_id: int, status: str):
    """Update signal outcome - HIT_T1, HIT_T2, HIT_SL, EXPIRED"""
    try:
        from datetime import datetime
        from config import settings
        supabase.table("signals").update({
            "status": status,
            "resolved_at": datetime.now(settings.TIMEZONE).isoformat()
        }).eq("id", signal_id).execute()
    except Exception as e:
        logger.error(f"Error updating signal status: {e}")

async def save_daily_snapshot(symbol: str, data: dict):
    """Save daily high/low/close snapshot for backup"""
    try:
        from datetime import datetime
        from config import settings
        today = datetime.now(settings.TIMEZONE).date().isoformat()
        supabase.table("daily_snapshots").upsert({
            "symbol": symbol,
            "date": today,
            **data
        }).execute()
    except Exception as e:
        logger.error(f"Error saving daily snapshot: {e}")
