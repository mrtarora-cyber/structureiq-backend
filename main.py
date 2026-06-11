# StructureIQ - Main Application Entry Point
# This file starts the entire platform

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging
from datetime import datetime
import pytz

from config import settings
from database import supabase
from data_ingestion.upstox_client import UpstoxClient
from market_structure.structure_engine import StructureEngine
from signal_engine.signal_builder import SignalBuilder
from risk_engine.position_sizer import PositionSizer
from alerts.telegram_bot import TelegramAlert
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="StructureIQ",
    description="AI-Powered Market Structure Trading Platform",
    version="1.0.0"
)

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize all engines
upstox = UpstoxClient()
structure_engine = StructureEngine()
signal_builder = SignalBuilder()
position_sizer = PositionSizer()
telegram = TelegramAlert()
scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

# Store active websocket connections
active_connections = []

# Indian market timezone
IST = pytz.timezone("Asia/Kolkata")

def is_market_open():
    """Check if Indian market is currently open"""
    now = datetime.now(IST)
    # Skip weekends
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0)
    market_close = now.replace(hour=15, minute=30, second=0)
    return market_open <= now <= market_close

async def broadcast_to_clients(data: dict):
    """Send live data to all connected dashboard clients"""
    message = json.dumps(data)
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except:
            disconnected.append(connection)
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)

async def market_analysis_loop():
    """
    Main loop - runs every 30 seconds during market hours
    This is the brain of StructureIQ
    """
    if not is_market_open():
        logger.info("Market is closed. Skipping analysis.")
        return

    logger.info("Running market analysis...")

    for symbol in ["NIFTY", "SENSEX"]:
        try:
            # Step 1: Get latest price data
            price_data = await upstox.get_live_price(symbol)
            if not price_data:
                continue

            # Step 2: Get OHLCV candles for structure analysis
            candles = await upstox.get_candles(symbol, "15m", 100)
            if candles is None or len(candles) < 20:
                continue

            # Step 3: Run market structure engine
            structure = structure_engine.analyze(symbol, candles)

            # Step 4: Check for trading signals
            signal = signal_builder.generate_signal(symbol, structure, price_data)

            # Step 5: If signal found, validate with risk engine
            if signal:
                risk_check = position_sizer.validate_signal(signal)
                if risk_check["approved"]:
                    # Save signal to database
                    supabase.table("signals").insert(signal).execute()
                    # Send Telegram alert to Nitish
                    await telegram.send_signal(signal)
                    logger.info(f"Signal generated for {symbol}: {signal['signal_type']}")

            # Step 6: Broadcast live data to dashboard
            await broadcast_to_clients({
                "type": "price_update",
                "symbol": symbol,
                "price": price_data["last_price"],
                "change": price_data["change"],
                "change_percent": price_data["change_percent"],
                "timestamp": datetime.now(IST).isoformat(),
                "structure": {
                    "trend": structure.get("trend", "UNKNOWN"),
                    "last_event": structure.get("last_event", ""),
                }
            })

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")

# ─── REST API ROUTES ──────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "app": "StructureIQ",
        "status": "running",
        "market_open": is_market_open(),
        "time_ist": datetime.now(IST).strftime("%H:%M:%S")
    }

@app.get("/api/signals/active")
async def get_active_signals():
    """Get all currently active trading signals"""
    result = supabase.table("signals")\
        .select("*")\
        .eq("status", "ACTIVE")\
        .order("created_at", desc=True)\
        .limit(10)\
        .execute()
    return {"signals": result.data}

@app.get("/api/signals/history")
async def get_signal_history():
    """Get past signals with their outcomes"""
    result = supabase.table("signals")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(50)\
        .execute()
    return {"signals": result.data}

@app.get("/api/market/structure/{symbol}")
async def get_market_structure(symbol: str):
    """Get current market structure for a symbol"""
    result = supabase.table("structure_events")\
        .select("*")\
        .eq("symbol", symbol.upper())\
        .order("created_at", desc=True)\
        .limit(20)\
        .execute()
    return {"structure": result.data}

@app.get("/api/market/zones/{symbol}")
async def get_price_zones(symbol: str):
    """Get active support/resistance and supply/demand zones"""
    result = supabase.table("price_zones")\
        .select("*")\
        .eq("symbol", symbol.upper())\
        .eq("is_active", True)\
        .execute()
    return {"zones": result.data}

@app.get("/api/risk/daily-status")
async def get_daily_status():
    """Get today's P&L and risk status"""
    today = datetime.now(IST).date().isoformat()
    result = supabase.table("trade_journal")\
        .select("*")\
        .eq("trade_date", today)\
        .execute()
    trades = result.data
    total_pnl = sum(t.get("pnl", 0) or 0 for t in trades)
    settings_result = supaba
