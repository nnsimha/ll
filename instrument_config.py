# List of multiple instruments
instruments = [
    {"token": 871681, "symbol": "TATACHEM", "exchange": "NSE"},
    {"token": 5195009, "symbol": "TATATECH", "exchange": "NSE"},
    {"token": 492033, "symbol": "KOTAKBANK", "exchange": "NSE"},
    
    {"token": 738561, "symbol": "RELIANCE", "exchange": "NSE"},
    {"token": 878593, "symbol": "TATACONSUM", "exchange": "NSE"},
    {"token": 408065, "symbol": "INFY", "exchange": "NSE"},
    {"token": 884737, "symbol": "TATAMOTORS", "exchange": "NSE"},
    {"token": 519937, "symbol": "M&M", "exchange": "NSE"},
    {"token": 779521, "symbol": "SBIN", "exchange": "NSE"},

]

# Trade configuration for each instrument
trade_config = {
    "TATACHEM": {"sl_buffer": 1, "target_buffer": 3, "quantity": 1},
    "TATATECH": {"sl_buffer": 1, "target_buffer": 3, "quantity": 2},
    "KOTAKBANK": {"sl_buffer": 2, "target_buffer": 4, "quantity": 2},
    "SBIN": {"sl_buffer": 2, "target_buffer": 4, "quantity": 2},
    "RELIANCE": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "KOTAKBANK": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "INFY": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "INFY25MARFUT": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "TATAMOTORS": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "M&M": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
    "TATACONSUM": {"sl_buffer": 2, "target_buffer": 4, "quantity": 1},
}