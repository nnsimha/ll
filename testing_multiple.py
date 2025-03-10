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


def has_active_sell_order(symbol):
    """Check if there's an active SELL order for the given symbol."""
    try:
        orders = kite.orders()
        for order in orders:
            if order["tradingsymbol"] == symbol and order["transaction_type"] == "SELL":
                if order["status"] in ["OPEN", "TRIGGER PENDING", "PARTIALLY EXECUTED", "PENDING", "AMO REQ RECEIVED"]:
                    print(f"Active SELL order detected for {symbol}! Order ID: {order['order_id']}, Status: {order['status']}")
                    return True
        return False
    except Exception as e:
        print(f"Error checking active orders for {symbol}: {e}")
        return False


def fetch_historical_data(instrument):
    """Fetch historical OHLC data for the given instrument."""
    today = datetime.now()
    yesterday = today - timedelta(days=5)

    from_date = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    to_date = today.strftime("%Y-%m-%d %H:%M:%S")

    print(f"Fetching data for {instrument['symbol']} from {from_date} to {to_date}")

    try:
        data = kite.historical_data(
            instrument_token=instrument["token"],
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )
        
        df = pd.DataFrame(data)
        if df.empty:
            print(f"No data available for {instrument['symbol']}. Market might be closed.")
            return None
        return df
    except Exception as e:
        print(f"Error fetching historical data for {instrument['symbol']}: {e}")
        return None


def calculate_moving_averages(df):
    """Calculate 20MA and 50MA for the stock."""
    if "close" not in df.columns:
        raise KeyError("Column 'close' is missing from DataFrame. Check the API response.")

    df["20MA"] = df["close"].rolling(window=20).mean()
    df["50MA"] = df["close"].rolling(window=50).mean()
    return df


def check_trade_condition(instrument):
    """Check trade conditions for a given instrument and place a SELL order if conditions are met."""
    df = fetch_historical_data(instrument)
    if df is None:
        return

    df = calculate_moving_averages(df)

    latest_candle = df.iloc[-1]
    close_price = latest_candle["close"]
    ma_50 = latest_candle["50MA"]

    print(f"{instrument['symbol']} - Latest Close: {close_price}, 50MA: {ma_50}")

    if close_price < ma_50:
        if has_active_sell_order(instrument["symbol"]):
            print(f"Skipping SELL order for {instrument['symbol']} as an active order exists.")
        else:
            print(f"Condition met for {instrument['symbol']}: Placing SELL order!")
            place_sell_order(instrument)
    else:
        print(f"Condition not met for {instrument['symbol']}: No action taken.")


def place_sell_order(instrument):
    """Place a SELL order for the given instrument."""
    try:
        order_id = kite.place_order(
            variety="amo",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="SELL",
            quantity=5,
            product="MIS",
            order_type="MARKET",
            price=None,
            validity="DAY",
            
        )
        print(f"SELL Order placed successfully for {instrument['symbol']}! Order ID: {order_id}")
    except Exception as e:
        print(f"Error placing SELL order for {instrument['symbol']}: {e}")


# Main loop (Runs every 5 minutes)
duration = 10  # Change this to 300 for 5 minutes
while True:
    for instrument in instruments:
        check_trade_condition(instrument)
    print(f"Sleeping for {duration} seconds...\n")
    time.sleep(duration)
