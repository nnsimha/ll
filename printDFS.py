import kiteapp as kt
import pandas as pd
import time
from datetime import datetime, timedelta
import logging
from tabulate import tabulate
from instrument_config import instruments, trade_config

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
kite = kt.KiteApp("kite", "YQ6639", token)

# WebSocket instance (not used in this script, but initialized)
kws = kite.kws()
'''
# List of multiple instruments
instruments = [
    {"token": 871681, "symbol": "TATACHEM", "exchange": "NSE"},
    {"token": 5195009, "symbol": "TATATECH", "exchange": "NSE"},
    {"token": 492033, "symbol": "KOTAKBANK", "exchange": "NSE"},
    {"token": 113109255, "symbol": "NATURALGAS25APRFUT", "exchange": "MCX"},
    {"token": 112596231, "symbol": "CRUDEOIL25MARFUT", "exchange": "MCX"},
    {"token": 110560263, "symbol": "GOLD25APRFUT", "exchange": "MCX"},
    {"token": 11047938, "symbol": "M&M25MARFUT", "exchange": "NFO"},
    {"token": 519937, "symbol": "M&M", "exchange": "NSE"},
]

# Trade configuration for each instrument
trade_config = {
    "TATACHEM": {"sl_buffer": 1, "target_buffer": 3, "quantity": 1000},
    "TATATECH": {"sl_buffer": 1, "target_buffer": 3, "quantity": 2},
    "KOTAKBANK": {"sl_buffer": 4, "target_buffer": 8, "quantity": 2},
    "NATURALGAS25APRFUT": {"sl_buffer": 5, "target_buffer": 10, "quantity": 5},
    "CRUDEOIL25MARFUT": {"sl_buffer": 30, "target_buffer": 60, "quantity": 5},
    "GOLD25APRFUT": {"sl_buffer": 50, "target_buffer": 100, "quantity": 1},
}
'''
def fetch_historical_data(instrument):
    """Fetch historical OHLC data for the given instrument."""
    today = datetime.now()
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    to_date = today.strftime("%Y-%m-%d %H:%M:%S")

    logging.info(f"Fetching data for {instrument['symbol']} from {from_date} to {to_date}")

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
        df = fetch_historical_data(instrument)
        if df is None:
            continue

        df = calculate_moving_averages(df)

        latest_candle = df.iloc[-1]
        close_price = latest_candle["close"]
        lower_bb = latest_candle["Lower_BB"]
        ma_50 = df["50MA"].dropna().iloc[-1] if not df["50MA"].dropna().empty else None
        ma_20 = df["20MA"].dropna().iloc[-1] if not df["20MA"].dropna().empty else None

        table_data.append([instrument['symbol'], close_price, lower_bb, ma_50, ma_20])

    logging.info("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))

# Main loop (Runs every 5 minutes)
while True:
    logging.info("Starting new cycle")
    print_candle_and_indicators(instruments)
    logging.info(f"Sleeping for {DURATION} seconds...\n")
    time.sleep(DURATION)