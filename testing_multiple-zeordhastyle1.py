

import kiteapp as kt
import pandas as pd
import time
from datetime import datetime, timedelta

import pdb

# Read token from file
with open('enctoken.txt', 'r') as rd:


    token = rd.read()

# Initialize Kite API
kite = kt.KiteApp("kite", "YQ6639", token)

# WebSocket instance (not used in this script, but initialized)
kws = kite.kws()

# List of multiple instruments

instruments = [
    {"token": 871681, "symbol": "TATACHEM", "exchange": "NSE"},
    {"token": 5195009, "symbol": "TATATECH", "exchange": "NSE"},
    {"token": 492033, "symbol": "KOTAKBANK", "exchange": "NSE"},
    {"token": 113109255, "symbol": "NATURALGAS25APRFUT", "exchange": "MCX"},
    {"token": 112596231, "symbol": "CRUDEOIL25MARFUT", "exchange": "MCX"},
    {"token": 110560263, "symbol": "GOLD25APRFUT", "exchange": "MCX"},
]


trade_config = {
    "TATACHEM": {"sl_buffer": 1, "target_buffer": 3, "quantity": 1000},
    "TATATECH": {"sl_buffer": 1, "target_buffer": 3, "quantity": 2},
    "KOTAKBANK": {"sl_buffer": 4, "target_buffer": 8, "quantity": 2},
    "NATURALGAS25APRFUT": {"sl_buffer": 5, "target_buffer": 10, "quantity": 5},
    "CRUDEOIL25MARFUT": {"sl_buffer": 30, "target_buffer": 60, "quantity": 5},
    "GOLD25APRFUT": {"sl_buffer": 50, "target_buffer": 100, "quantity": 1},
}
'''
instruments = [
    {"token": 3394561, "symbol": "KEC", "exchange": "NSE"},
]

trade_config = {
    "KEC": {"sl_buffer": 1, "target_buffer": 3, "quantity": 2},
}
'''

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
    df["std_dev"] = df["close"].rolling(window=20).std()
    df["Upper_BB"] = df["20MA"] + (df["std_dev"] * 2)
    df["Lower_BB"] = df["20MA"] - (2 * df["std_dev"])
   
    return df

def check_trade_condition(instrument):
    """Check trade conditions for a given instrument and place a SELL order if conditions are met."""
    df = fetch_historical_data(instrument)
    if df is None:
        return

    df = calculate_moving_averages(df)

    latest_candle = df.iloc[-1]
    close_price = latest_candle["close"]
    low_price = latest_candle["low"]
    #ma_50 = latest_candle["50MA"]
    ma_50 = df["50MA"].dropna().iloc[-1] if not df["50MA"].dropna().empty else None
    lower_bb = latest_candle["Lower_BB"]
    
    print(f"{instrument['symbol']} - Latest Close: {close_price}, 50MA: {ma_50},Lower BB: {lower_bb}")
    

    if close_price < ma_50 or low_price <= lower_bb:
        if has_active_sell_order(instrument["symbol"]):
            print(close_price)
            print(f"Skipping SELL order for {instrument['symbol']} as an active order exists.")
        else:
            print(f"Condition met for {instrument['symbol']}: Placing SELL order!")
            print(close_price)
            place_sell_order(instrument, close_price)
    else:
        print(f"Condition not met for {instrument['symbol']}: No action taken.")
        print(close_price)


def place_sell_order(instrument, ltp):
    """Place a SELL order for the given instrument and set stop-loss and target orders only if the main order is executed."""
    try:

        config = trade_config.get(instrument["symbol"], {"sl_buffer": 2, "target_buffer": 2, "quantity": 1})
        sl_buffer = config["sl_buffer"]
        target_buffer = config["target_buffer"]
        quantity = config["quantity"]
        stop_loss = round(ltp + sl_buffer, 2)
        target = round(ltp - target_buffer, 2)
        
        order_id = kite.place_order(
            variety="amo",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="SELL",
            quantity=quantity,
            product="MIS",
            order_type="LIMIT",
            price=ltp,
            validity="DAY"
        )
        print(f"✅ SELL Order placed successfully for {instrument['symbol']}! Order ID: {order_id}")

        # Wait for order execution before placing SL and Target orders
        time.sleep(2)
        orders = kite.orders()
        #print(orders)
        for order in orders:
            #print(order)
            if order["order_id"] == order_id and order["status"] == "AMO REQ RECEIVED":
                # Place stop-loss order (BUY SL-M)
                sl_order_id = kite.place_order(
                    variety="amo",
                    exchange=instrument["exchange"],
                    tradingsymbol=instrument["symbol"],
                    transaction_type="BUY",
                    quantity=quantity,
                    product="MIS",
                    order_type="SL-M",
                    trigger_price=stop_loss,
                    validity="DAY"
                )
                print(f"🛑 Stop-Loss Order placed at {stop_loss} for {instrument['symbol']}! Order ID: {sl_order_id}")

                # Place target order (BUY LIMIT)
                target_order_id = kite.place_order(
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
                print(f"🎯 Target Order placed at {target} for {instrument['symbol']}! Order ID: {target_order_id}")
    except Exception as e:
        print(f"Error placing SELL order for {instrument['symbol']}: {e}")




# Main loop (Runs every 5 minutes)
duration = 10  # Change this to 300 for 5 minutes
while True:
    for instrument in instruments:
        check_trade_condition(instrument)
    print(f"Sleeping for {duration} seconds...\n")
    time.sleep(duration)
