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
DURATION = 3  # Duration for each sleep cycle in seconds
MANUAL_CLOSE_CHECK_INTERVAL = 60  # Interval to check for manually closed positions in seconds
RETRY_DELAY = 2  # Delay between retries in seconds
MAX_RETRIES = 3  # Maximum number of retries for placing SL and target orders

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("trading_script.log"), logging.StreamHandler()])

# Read token from file
with open('enctoken.txt', 'r') as rd:
    token = rd.read().strip()
    logging.info("Token read from file successfully")

# Initialize Kite API
kite = kt.KiteApp("kite", "YQ6639", token)
logging.info("Kite API initialized successfully")

# Initialize Kite Ticker
kws = kite.kws()  # For Websocket

live_data = {}
closed_positions_today = set()  # To track instruments with closed positions today
open_orders = {}  # To track SL and target orders
previous_candle_below_50ma = {}  # To track previous candle status for crossing below 50MA

def on_ticks(ws, ticks):
    for tick in ticks:
        live_data[tick['instrument_token']] = {
            "ltp": tick["last_price"],
            "high": tick["ohlc"]["high"],
            "low": tick["ohlc"]["low"]
        }
    # Log ticks received at less frequent intervals
    if ticks:
        logging.debug("Received ticks for instruments: %s", [tick['instrument_token'] for tick in ticks])

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

def has_active_sell_order_or_position(symbol):
    """Check if there's an active SELL order or any position (open or closed) for the given symbol."""
    try:
        orders = kite.orders()
        for order in orders:
            if order["tradingsymbol"] == symbol and order["transaction_type"] == "SELL":
                if order["status"] in ["OPEN", "TRIGGER PENDING", "PARTIALLY EXECUTED", "PENDING", "AMO REQ RECEIVED"]:
                    logging.info(f"Active SELL order detected for {symbol}! Order ID: {order['order_id']}, Status: {order['status']}")
                    return True

        positions = kite.positions()
        for position in positions["net"]:
            if position["tradingsymbol"] == symbol and position["quantity"] != 0:
                logging.info(f"Position detected for {symbol}! Quantity: {position['quantity']}")
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking active orders or positions for {symbol}: {e}")
        return False

def has_closed_position_today(symbol):
    """Check if the given symbol has a closed position today."""
    return symbol in closed_positions_today

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

def calculate_indicators(df):
    """Calculate 20MA, 50MA, Bollinger Bands, RSI, MACD for the stock."""
    if "close" not in df.columns or "volume" not in df.columns:
        raise KeyError("Required columns are missing from DataFrame. Check the API response.")

    # Moving Averages and Bollinger Bands
    df["20MA"] = df["close"].rolling(window=20).mean()
    df["50MA"] = df["close"].rolling(window=50).mean()
    df["std_dev"] = df["close"].rolling(window=20).std()
    df["Upper_BB"] = df["20MA"] + (df["std_dev"] * 2)
    df["Lower_BB"] = df["20MA"] - (2 * df["std_dev"])

    # Relative Strength Index (RSI)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    df["12EMA"] = df["close"].ewm(span=12, adjust=False).mean()
    df["26EMA"] = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["12EMA"] - df["26EMA"]
    df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df

def check_trade_condition(instrument):
    """Check trade conditions for a given instrument and place a SELL order if conditions are met."""
    if instrument["token"] not in live_data:
        logging.warning(f"No live data available for {instrument['symbol']}")
        return

    if has_closed_position_today(instrument["symbol"]):
        logging.info(f"Skipping {instrument['symbol']} as it has a closed position today.")
        return

    df = fetch_historical_data(instrument)
    if df is None:
        return

    df = calculate_indicators(df)

    latest_candle = df.iloc[-1]
    close_price = live_data[instrument["token"]]["ltp"]
    ma_50 = df["50MA"].dropna().iloc[-1] if not df["50MA"].dropna().empty else None
    lower_bb = latest_candle["Lower_BB"]
    rsi = latest_candle["RSI"]
    macd = latest_candle["MACD"]
    signal_line = latest_candle["Signal_Line"]

    logging.info(f"{instrument['symbol']} - Latest Close: {close_price}, 50MA: {ma_50}, Lower BB: {lower_bb}, RSI: {rsi}, MACD: {macd}, Signal Line: {signal_line}")

    # Example enhanced trade condition
    if close_price < ma_50 and not previous_candle_below_50ma.get(instrument["symbol"], False):
        if has_active_sell_order_or_position(instrument["symbol"]):
            logging.info(f"Skipping SELL order for {instrument['symbol']} as an active order or position exists.")
        else:
            logging.info(f"Condition met for {instrument['symbol']}: Placing SELL order!")
            place_sell_order(instrument, close_price)
        previous_candle_below_50ma[instrument["symbol"]] = True
    elif close_price >= ma_50:
        previous_candle_below_50ma[instrument["symbol"]] = False

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
            variety="regular",
            exchange=instrument["exchange"],
            tradingsymbol=instrument["symbol"],
            transaction_type="SELL",
            quantity=quantity,
            product="MIS",
            order_type="LIMIT",
            price=ltp,
            validity="DAY"
        )
        logging.info(f"✅ SELL Order placed successfully for {instrument['symbol']}! Order ID: {order_id}")

        # Wait for order execution before placing SL and Target orders
        sleep(2)
        orders = kite.orders()

        for order in orders:
            if order["order_id"] == order_id and order["status"] == "COMPLETE":
                # Place stop-loss order (BUY SL-M)
                sl_order_id = place_order_with_retry(
                    variety="regular",
                    exchange=instrument["exchange"],
                    tradingsymbol=instrument["symbol"],
                    transaction_type="BUY",
                    quantity=quantity,
                    product="MIS",
                    order_type="SL-M",
                    trigger_price=stop_loss,
                    validity="DAY"
                )
                logging.info(f"🛑 Stop-Loss Order placed at {stop_loss} for {instrument['symbol']}! Order ID: {sl_order_id}")

                # Place target order (BUY LIMIT)
                target_order_id = place_order_with_retry(
                    variety="regular",
                    exchange=instrument["exchange"],
                    tradingsymbol=instrument["symbol"],
                    transaction_type="BUY",
                    quantity=quantity,
                    product="MIS",
                    order_type="LIMIT",
                    price=target,
                    validity="DAY"
                )
                logging.info(f"🎯 Target Order placed at {target} for {instrument['symbol']}! Order ID: {target_order_id}")

                # Save the SL and target order IDs
                open_orders[instrument["symbol"]] = (sl_order_id, target_order_id)
                # Start monitoring the orders for OCO functionality
                monitor_oco_orders(sl_order_id, target_order_id, instrument["symbol"])
    except Exception as e:
        logging.error(f"Error placing SELL order for {instrument['symbol']}: {e}")

def place_order_with_retry(**order_params):
    """Place an order with retry logic."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            order_id = kite.place_order(**order_params)
            return order_id
        except Exception as e:
            retries += 1
            logging.error(f"Error placing order: {e}. Retrying {retries}/{MAX_RETRIES}...")
            sleep(RETRY_DELAY)
    raise Exception("Failed to place order after maximum retries")

def monitor_oco_orders(sl_order_id, target_order_id, symbol):
    """Monitor SL and target orders and cancel the other if one is executed."""
    try:
        while True:
            orders = kite.orders()
            sl_order_status = next((order["status"] for order in orders if order["order_id"] == sl_order_id), None)
            target_order_status = next((order["status"] for order in orders if order["order_id"] == target_order_id), None)

            if sl_order_status == "COMPLETE":
                logging.info(f"Stop-Loss order executed. Cancelling target order {target_order_id}.")
                kite.cancel_order(variety="regular", order_id=target_order_id)
                closed_positions_today.add(symbol)  # Mark as closed position for today
                del open_orders[symbol]  # Remove from open orders
                break
            elif target_order_status == "COMPLETE":
                logging.info(f"Target order executed. Cancelling stop-loss order {sl_order_id}.")
                kite.cancel_order(variety="regular", order_id=sl_order_id)
                closed_positions_today.add(symbol)  # Mark as closed position for today
                del open_orders[symbol]  # Remove from open orders
                break

            sleep(1)
    except Exception as e:
        logging.error(f"Error monitoring OCO orders: {e}")

def check_manually_closed_positions():
    """Check for manually closed positions and cancel any remaining SL and target orders."""
    try:
        positions = kite.positions()
        for symbol, (sl_order_id, target_order_id) in list(open_orders.items()):
            position = next((p for p in positions["net"] if p["tradingsymbol"] == symbol), None)
            if position and position["quantity"] == 0:
                logging.info(f"Manually closed position detected for {symbol}. Cancelling remaining orders.")
                kite.cancel_order(variety="regular", order_id=sl_order_id)
                kite.cancel_order(variety="regular", order_id=target_order_id)
                closed_positions_today.add(symbol)  # Mark as closed position for today
                del open_orders[symbol]  # Remove from open orders
    except Exception as e:
        logging.error(f"Error checking manually closed positions: {e}")

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
        for instrument in instruments:
            check_trade_condition(instrument)
        check_manually_closed_positions()  # Check for manually closed positions
        logging.info(f"Sleeping for {DURATION} seconds...\n")
        sleep(DURATION)
except (KeyboardInterrupt, SystemExit):
    signal_handler(None, None)