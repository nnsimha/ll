import kiteconnect as kt
import kiteapp as kt
import pandas as pd
from datetime import datetime, timedelta
import logging
from tabulate import tabulate
from instrument_config import instruments, trade_config
import threading
from time import sleep

import signal
import sys

# Constants
INTERVAL = "2minute"
DURATION = 3  # Duration for each sleep cycle in seconds (5 minutes)


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("DFS_check.log"), logging.StreamHandler()])

# Read token from file
with open('enctoken.txt', 'r') as rd:
    token = rd.read().strip()

# Initialize Kite API
kite = kt.KiteApp("kite", "PO5476", token)
logging.info("Kite API initialized successfully")

# Initialize Kite Ticker
kws = kite.kws()  # For Websocket

live_data = {}

def on_ticks(ws, ticks):
    for tick in ticks:
        live_data[tick['instrument_token']] = {
            "ltp": tick["last_price"],
            "high": tick["ohlc"]["high"],
            "low": tick["ohlc"]["low"]
        }
   # logging.info("Ticks received")

def on_connect(ws, response):
    ws.subscribe([instrument["token"] for instrument in instruments])
    ws.set_mode(ws.MODE_QUOTE, [instrument["token"] for instrument in instruments])
    logging.info("WebSocket connected and subscribed to instruments")

def on_close(ws, code, reason):
    ws.stop()
    logging.info("WebSocket closed")

kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.on_close = on_close

def fetch_historical_data(instrument):
    """Fetch historical OHLC data for the given instrument."""
    today = datetime.now()
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    to_date = today.strftime("%Y-%m-%d %H:%M:%S")

    #logging.info(f"Fetching data for {instrument['symbol']} from {from_date} to {to_date}")

    try:
        data = kite.historical_data(
            instrument_token=instrument["token"],
            from_date=from_date,
            to_date=to_date,
            interval=INTERVAL
        )

        df = pd.DataFrame(data)
        if df.empty:
            logging.warning(f"No data available for {instrument['symbol']}. Market might be closed.")
            return None
        return df
    except Exception as e:
        logging.error(f"Error fetching historical data for {instrument['symbol']}: {e}")
        return None

def calculate_moving_averages(df):
    """Calculate 20MA, 50MA, and Bollinger Bands for the stock."""
    if "close" not in df.columns:
        raise KeyError("Column 'close' is missing from DataFrame. Check the API response.")

    df["20MA"] = df["close"].rolling(window=20).mean()
    df["50MA"] = df["close"].rolling(window=50).mean()
    df["std_dev"] = df["close"].rolling(window=20).std()
    df["Upper_BB"] = df["20MA"] + (df["std_dev"] * 2)
    df["Lower_BB"] = df["20MA"] - (2 * df["std_dev"])

    return df

def print_candle_and_indicators(instruments):
    """Print candle price, lower Bollinger Band price, 50 MA price, and 20 MA price in a table format."""
    table_data = []
    headers = ["Instrument", "Candle Price", "Lower BB", "50 MA", "20 MA"]

    for instrument in instruments:
        if instrument["token"] not in live_data:
            logging.warning(f"No live data available for {instrument['symbol']}")
            continue

        df = fetch_historical_data(instrument)
        if df is None:
            continue

        df = calculate_moving_averages(df)

        latest_candle = df.iloc[-1]
        close_price = live_data[instrument["token"]]["ltp"]
        lower_bb = latest_candle["Lower_BB"]
        ma_50 = df["50MA"].dropna().iloc[-1] if not df["50MA"].dropna().empty else None
        ma_20 = df["20MA"].dropna().iloc[-1] if not df["20MA"].dropna().empty else None

        table_data.append([instrument['symbol'], close_price, lower_bb, ma_50, ma_20])

    logging.info("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))

def signal_handler(sig, frame):
    logging.info("Interrupt received, stopping...")
    kws.stop()
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Start WebSocket in the main thread
ws_thread = threading.Thread(target=kws.connect)
ws_thread.daemon = True
ws_thread.start()

try:
    # Main loop (Runs continuously)
    while True:
        logging.info("Starting new cycle")
        print_candle_and_indicators(instruments)
        logging.info(f"Sleeping for {DURATION} seconds...\n")
        sleep(DURATION)
except (KeyboardInterrupt, SystemExit):
    signal_handler(None, None)