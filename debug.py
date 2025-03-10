import kiteapp as kt
import pandas as pd
import time
from datetime import datetime, timedelta

# Read token from file
with open('enctoken.txt', 'r') as rd:
    token = rd.read()

# Initialize Kite API
kite = kt.KiteApp("kite", "YQ6639", token)

# WebSocket instance (not used in this script, but initialized)
kws = kite.kws()

# List of multiple instruments
instruments = [
    {"token": 779521, "symbol": "SBIN", "exchange": "NSE"},
    {"token": 5633, "symbol": "TCS", "exchange": "NSE"},
    {"token": 2953217, "symbol": "RELIANCE", "exchange": "NSE"},
    {"token": 113109255, "symbol": "NATURALGAS25APRFUT", "exchange": "MCX"},
    {"token": 112596231, "symbol": "CRUDEOIL25MARFUT", "exchange": "MCX"},
    {"token": 110560263, "symbol": "GOLD25APRFUT", "exchange": "MCX"},
]


interval = "5minute"
import time

def get_ltp(instrument):
    """Fetch Last Traded Price (LTP) for a given instrument."""
    try:
        instrument_key = f"{instrument['exchange']}:{instrument['symbol']}"
        print(f"📌 Fetching LTP for: {instrument_key}")

        time.sleep(1)  # Avoid hitting API limits
        ltp_data = kite.ltp([instrument_key])  # Pass list instead of a single string
        
        print(f"🔍 Raw API Response: {ltp_data}")  # Debugging step

        last_traded_price = ltp_data[instrument_key]["last_price"]
        print(f"✅ LTP for {instrument['symbol']}: {last_traded_price}")
        return last_traded_price

    except Exception as e:
        print(f"❌ Error fetching LTP for {instrument['symbol']}: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    instrument = {"exchange": "NSE", "symbol": "RELIANCE"}
    get_ltp(instrument)