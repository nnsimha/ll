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

# Instrument details
instrument_token = 779521  # Example: SBIN
interval = "5minute"


def is_connected(self):
    """Check if WebSocket connection is established."""
    if self.ws and self.ws.state == self.ws.STATE_OPEN:
        return True
    else:
        return False
def fetch_historical_data():
    """Fetch historical OHLC data."""
    today = datetime.now()
    yesterday = today - timedelta(days=5)

    from_date = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    to_date = today.strftime("%Y-%m-%d %H:%M:%S")

    print(f"Fetching data from {from_date} to {to_date}")

    try:
        data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )
        print("Raw API Response:", data[:5])  # Debugging: Print first 5 data points
        
        df = pd.DataFrame(data)
        print("DataFrame Shape:", df.shape)
        print("Columns:", df.columns.tolist())

        if df.empty:
            print("No data available. Market might be closed.")
            return None

        return df
    except Exception as e:
        print("Error fetching historical data:", e)
        return None

def calculate_moving_averages(df):
    """Calculate 20MA and 50MA for the stock."""
    if "close" not in df.columns:
        raise KeyError("Column 'close' is missing from DataFrame. Check the API response.")

    df["20MA"] = df["close"].rolling(window=20).mean()
    df["50MA"] = df["close"].rolling(window=50).mean()
    
    print(df.tail(3))  # Debugging: Print last 3 rows with MAs
    
    return df

def has_active_sell_order():
    """Check if there's an active SELL order for the stock."""
    try:
        orders = kite.orders()
        for order in orders:
            if (order["tradingsymbol"] == "SBIN" and
                order["transaction_type"] == "SELL" and
                order["status"] in ["OPEN", "TRIGGER PENDING", "PARTIALLY EXECUTED", "PENDING", "AMO REQ RECEIVED"]):
                print("Active SELL order detected. Skipping new SELL order.")
                return True
        return False
    except Exception as e:
        print(f"Error checking active orders: {e}")
        return False

def has_active_sell_position():
    """Check if there's an active SELL position for SBIN."""
    try:
        positions = kite.positions()
        for position in positions.get("net", []):
            if (position["tradingsymbol"] == "SBIN" and
                position["quantity"] < 0):  # Negative quantity indicates an active SELL position
                print(f"Active SELL position detected: {position['quantity']} units of SBIN.")
                return True
        return False
    except Exception as e:
        print(f"Error checking active positions: {e}")
        return False
    

def check_trade_condition():
    """Check if the closing price is below the 50MA and place a SELL order."""
    df = fetch_historical_data()
    if df is None:
        return

    df = calculate_moving_averages(df)

    latest_candle = df.iloc[-1]
    close_price = latest_candle["close"]
    ma_20 = latest_candle["20MA"]
    ma_50 = latest_candle["50MA"]

    print(f"Latest Close Price: {close_price}")
    print(f"20MA: {ma_20}")
    print(f"50MA: {ma_50}")

    if close_price < ma_50:
        if has_active_sell_order():
            print("Sell order already exists. No new order placed.")
            return
        if has_active_sell_position():
            print("Sell position already exists. No new order placed.")
            return

        print("Condition met: Placing SELL order!")
        place_sell_order()
    else:
        print("Condition not met: No action taken.")




def place_sell_order():
    """Place a SELL order."""
    try:
        order_id = kite.place_order(
            variety="amo",
            exchange='NSE',
            tradingsymbol='SBIN',
            transaction_type='SELL',  # Changed to SELL
            quantity=5,
            product='MIS',
            order_type="MARKET",
            price=None,  # Set this dynamically based on market data
            validity="DAY"
        )
        print(f"SELL Order placed successfully! Order ID: {order_id}")
    except Exception as e:
        print(f"Error placing SELL order: {e}")

# Main loop (Runs every 5 minutes)
duration = 10  # 5 minutes
while True:
    check_trade_condition()
    print(f"Sleeping for {duration} seconds...")
    time.sleep(duration)
