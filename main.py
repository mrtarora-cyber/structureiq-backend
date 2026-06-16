    # StructureIQ - Main Application
# Complete backend with Options Engine

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from dhanhq import dhanhq
from config import DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
import logging
from datetime import datetime
import pytz

from config import settings
from database import supabase
from data_ingestion.upstox_client import UpstoxClient
from data_ingestion.structure_engine import StructureEngine
from data_ingestion.signal_builder import SignalBuilder
from data_ingestion.position_sizer import PositionSizer
from data_ingestion.telegram_bot import TelegramAlert
from data_ingestion.options_engine import OptionsEngine
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize Dhan Broker Client Connection
try:
    if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
        dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        print("Dhan API initialization successful.")
    else:
        print("Dhan API credentials missing from environment variables.")
except Exception as e:
    print(f"Failed to connect to Dhan Broker: {str(e)}")
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
upstox          = UpstoxClient()
structure_engine = StructureEngine()
signal_builder  = SignalBuilder()
position_sizer  = PositionSizer()
telegram        = TelegramAlert()
options_engine  = OptionsEngine()
scheduler       = AsyncIOScheduler(timezone=settings.TIMEZONE)

# Store active websocket connections
active_connections = []

# Cache for key levels
key_levels_cache = {
    "NIFTY": {},
    "SENSEX": {}
}

IST = pytz.timezone("Asia/Kolkata")

def is_market_open():
    """Check if Indian market is currently open"""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0)
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
    for conn in disconnected:
        active_connections.remove(conn)

async def market_analysis_loop():
    """
    Main loop - runs every 30 seconds during market hours
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

            # Step 2: Get candles for structure analysis
            candles_15m = await upstox.get_candles(symbol, "15m", 100)
            candles_1d  = await upstox.get_candles(symbol, "1D", 10)

            if not candles_15m or len(candles_15m) < 20:
                continue

            # Step 3: Get key levels (PDH, PDL, PWH, PWL)
            key_levels = options_engine.get_key_levels(candles_1d, candles_15m)
            key_levels_cache[symbol] = key_levels

            # Step 4: Run market structure engine
            structure = structure_engine.analyze(symbol, candles_15m)

            # Step 5: Check for trading signals
            signal = signal_builder.generate_signal(symbol, structure, price_data)

            # Step 6: If signal found, add options recommendation
            if signal:
                # Get options recommendation
                option_rec = options_engine.get_option_recommendation(
                    signal, key_levels
                )
                if option_rec:
                    signal["option_recommendation"] = option_rec

                # Validate with risk engine
                risk_check = position_sizer.validate_signal(signal)
                if risk_check["approved"]:
                    # Save signal to database
                    supabase.table("signals").insert({
                        "symbol":       signal["symbol"],
                        "signal_type":  signal["signal_type"],
                        "timeframe":    signal["timeframe"],
                        "entry_price":  signal["entry_price"],
                        "stop_loss":    signal["stop_loss"],
                        "target_1":     signal["target_1"],
                        "target_2":     signal["target_2"],
                        "rr_ratio":     signal["rr_ratio"],
                        "confidence":   signal["confidence"],
                        "explanation":  signal["explanation"],
                        "status":       "ACTIVE"
                    }).execute()

                    # Send Telegram alert with options info
                    await telegram.send_signal_with_options(signal, option_rec, key_levels)
                    logger.info(f"Signal generated for {symbol}: {signal['signal_type']}")

            # Step 7: Broadcast live data to dashboard
            await broadcast_to_clients({
                "type":   "price_update",
                "symbol": symbol,
                "price":  price_data["last_price"],
                "change": price_data["change"],
                "change_percent": price_data["change_percent"],
                "timestamp": datetime.now(IST).isoformat(),
                "structure": {
                    "trend":      structure.get("trend", "UNKNOWN"),
                    "last_event": structure.get("last_event", ""),
                },
                "key_levels": key_levels
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
    result = supabase.table("signals")\
        .select("*")\
        .eq("status", "ACTIVE")\
        .order("created_at", desc=True)\
        .limit(10)\
        .execute()
    return {"signals": result.data}

@app.get("/api/signals/history")
async def get_signal_history():
    result = supabase.table("signals")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(50)\
        .execute()
    return {"signals": result.data}

@app.get("/api/market/structure/{symbol}")
async def get_market_structure(symbol: str):
    result = supabase.table("structure_events")\
        .select("*")\
        .eq("symbol", symbol.upper())\
        .order("created_at", desc=True)\
        .limit(20)\
        .execute()
    return {"structure": result.data}

@app.get("/api/market/zones/{symbol}")
async def get_price_zones(symbol: str):
    result = supabase.table("price_zones")\
        .select("*")\
        .eq("symbol", symbol.upper())\
        .eq("is_active", True)\
        .execute()
    return {"zones": result.data}

@app.get("/api/market/levels/{symbol}")
async def get_key_levels(symbol: str):
    """Get Previous Day/Week High Low for options trading"""
    levels = key_levels_cache.get(symbol.upper(), {})
    if not levels:
        # Try to fetch fresh if cache empty
        try:
            candles_1d  = await upstox.get_candles(symbol.upper(), "1D", 10)
            candles_15m = await upstox.get_candles(symbol.upper(), "15m", 20)
            levels = options_engine.get_key_levels(candles_1d, candles_15m)
            key_levels_cache[symbol.upper()] = levels
        except:
            pass
    return {"symbol": symbol.upper(), "levels": levels}

@app.get("/api/market/live/{symbol}")
async def get_live_price(symbol: str):
    price = await upstox.get_live_price(symbol.upper())
    return {"symbol": symbol.upper(), "price": price}

@app.get("/api/risk/daily-status")
async def get_daily_status():
    today = datetime.now(IST).date().isoformat()
    result = supabase.table("trade_journal")\
        .select("*")\
        .eq("trade_date", today)\
        .execute()
    trades = result.data
    total_pnl = sum(t.get("pnl", 0) or 0 for t in trades)
    settings_result = supabase.table("risk_settings")\
        .select("*").limit(1).execute()
    risk = settings_result.data[0] if settings_result.data else {}
    capital    = risk.get("capital", 10000)
    daily_limit = risk.get("daily_loss_limit", 2.0)
    max_loss   = capital * daily_limit / 100
    return {
        "total_pnl":        total_pnl,
        "trades_today":     len(trades),
        "daily_loss_limit": max_loss,
        "remaining_risk":   max_loss + total_pnl,
        "limit_breached":   total_pnl < -max_loss
    }

@app.get("/api/risk/position-size")
async def get_position_size(entry: float, stop_loss: float, symbol: str = "NIFTY"):
    result = position_sizer.calculate_position_size(entry, stop_loss, symbol)
    return result

@app.get("/api/journal/performance")
async def get_performance():
    result = supabase.table("trade_journal").select("*").execute()
    trades = result.data
    if not trades:
        return {"message": "No trades yet"}
    completed = [t for t in trades if t.get("pnl") is not None]
    winners   = [t for t in completed if t.get("pnl", 0) > 0]
    losers    = [t for t in completed if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in completed)
    win_rate  = len(winners) / len(completed) * 100 if completed else 0
    return {
        "total_trades": len(completed),
        "winners":      len(winners),
        "losers":       len(losers),
        "win_rate":     round(win_rate, 1),
        "total_pnl":    round(total_pnl, 2),
        "avg_win":      round(sum(t["pnl"] for t in winners) / len(winners), 2) if winners else 0,
        "avg_loss":     round(sum(t["pnl"] for t in losers)  / len(losers),  2) if losers  else 0,
    }

@app.get("/api/journal/trades")
async def get_trades():
    result = supabase.table("trade_journal")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(50)\
        .execute()
    return {"trades": result.data}

@app.post("/api/journal/trades")
async def log_trade(trade: dict):
    trade["trade_date"] = datetime.now(IST).date().isoformat()
    result = supabase.table("trade_journal").insert(trade).execute()
    return {"success": True, "trade": result.data}

# ─── WEBSOCKET ────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Dashboard connected. Total: {len(active_connections)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# ─── STARTUP ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("StructureIQ starting up...")
    scheduler.add_job(
        market_analysis_loop,
        "interval",
        seconds=30,
        id="market_analysis"
    )
    scheduler.start()
    logger.info("Scheduler started")
    await telegram.send_message(
        "StructureIQ is LIVE! Watching NIFTY & SENSEX for Nitish!"
    )

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    logger.info("StructureIQ shutting down...")            
