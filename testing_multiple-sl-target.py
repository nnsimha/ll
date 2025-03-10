import kiteapp as kt
import pandas as pd
import time
from datetime import datetime, timedelta
from time import sleep

# Read token from file
with open('enctoken.txt', 'r') as rd:
    token = rd.read()

# Initialize Kite API
kite = kt.KiteApp("kite", "YQ6639", token)

# WebSocket setup
kws = kite.kws()

# Instrument mapping for WebSocket
stock = {
    779521: "SBIN",
    5633: "TCS",
    2953217: "RELIANCE",
    113109255: "NATURALGAS25APRFUT",
    112596231: "CRUDEOIL25MARFUT",
    110560263: "GOLD25APRFUT",
}
ltp_data = {}

# WebSocket event handlers
def on_ticks(ws, ticks):
    for symbol in ticks:
        if symbol['instrument_token'] in stock:
            ltp_data[stock[symbol['instrument_token']]] = symbol["last_price"]

def on_connect(ws, response):
    ws.subscribe(list(stock.keys()))
    ws.set_mode(ws.MODE_QUOTE, list(stock.keys()))

kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.connect(threaded=True)

# List of instruments
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
    """Check if there's an active SELL order."""
    try:
        orders = kite.orders()
        for order in orders:
            if order["tradingsymbol"] == symbol and order["transaction_type"] == "SELL":
                if order["status"] in ["OPEN", "TRIGGER PENDING", "PARTIALLY EXECUTED", "PENDING", "AMO REQ RECEIVED"]:
                    return True
        return False
    except Exception as e:
        print(f"Error checking active orders for {symbol}: {e}")
        return False

def fetch_historical_data(instrument):
    """Fetch historical OHLC data."""
    today = datetime.now()
    from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    to_date = today.strftime("%Y-%m-%d %H:%M:%S")

    try:
        data = kite.historical_data(
            instrument_token=instrument["token"],
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )
        df = pd.DataFrame(data)
        return df if not df.empty else None
    except Exception as e:
        print(f"Error fetching historical data for {instrument['symbol']}: {e}")
        return None

def calculate_moving_averages(df):
    """Calculate 20MA and 50MA."""
    df["20MA"] = df["close"].rolling(window=20).mean()
    df["50MA"] = df["close"].rolling(window=50).mean()
    return df

def check_trade_condition(instrument):
    """Check conditions and place a SELL order."""
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
            print(f"Skipping SELL order for {instrument['symbol']} (Active order exists)")
        else:
            print(f"✅ Condition met for {instrument['symbol']}: Placing SELL order!")
            place_sell_order(instrument)

def place_sell_order(instrument):
    """Place a SELL order with SL and Target."""
    ltp = ltp_data.get(instrument["symbol"])
    if not ltp:
        print(f"⚠️ No LTP available for {instrument['symbol']}. Skipping trade.")
        return

    quantity = 5
    stop_loss = round(ltp * 1.02, 2)  # 2% above LTP
    target = round(ltp * 0.98, 2)  # 2% below LTP

    try:
        order_id = kite.place_order(
            variety="amo",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="SELL",
            quantity=quantity,
            product="MIS",
            order_type="MARKET",
            validity="DAY"
        )
        print(f"✅ SELL Order placed for {instrument['symbol']}! Order ID: {order_id}")
        place_sl_target_orders(instrument, quantity, stop_loss, target)
    except Exception as e:
        print(f"❌ Error placing SELL order for {instrument['symbol']}: {e}")

def place_sl_target_orders(instrument, quantity, stop_loss, target):
    """Place Stop-Loss and Target orders."""
    try:
        kite.place_order(
            variety="amo",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="BUY",
            quantity=quantity,
            product="MIS",
            order_type="SL",
            price=stop_loss,
            validity="DAY"
        )
        print(f"🛑 Stop-Loss order placed for {instrument['symbol']} at {stop_loss}")
        kite.place_order(
            variety="amo",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="BUY",
            quantity=quantity,
            product="MIS",
            order_type="LIMIT",
            price=target,
            validity="DAY"
        )
        print(f"🎯 Target order placed for {instrument['symbol']} at {target}")
    except Exception as e:
        print(f"❌ Error placing SL/Target order for {instrument['symbol']}: {e}")

# Main loop
while True:
    for instrument in instruments:
        check_trade_condition(instrument)
    print("Sleeping for 10 seconds...\n")
    time.sleep(10)
