# async-ticker
[Kite connect websocket](https://kite.trade/docs/connect/v3/websocket/) implementation in asyncio, to get away with twisted dependency.

## Installation
```
git clone https://github.com/ranjanrak/async-ticker.git
```

## Usage
Client side usage remains same as of [current kiteconnect websocket](https://github.com/zerodha/pykiteconnect#websocket-usage). 

```
import logging
from async_ticker import MainTicker

logging.basicConfig(level=logging.DEBUG)

# API credentials
api_key = "your_api_key"
access_token = "your_access_token"

# Initialize main ticker 
ws = MainTicker(api_key, access_token)

def on_ticks(ws, ticks):
    # Callback to receive ws ticks.
    logging.debug("Ticks: {}".format(ticks))

def on_connect(ws, response):
    # Callback on successful connect.
    ws.subscribe([738561, 5633])
    
    ws.set_mode(ws.MODE_LTP, [5633])
    ws.set_mode(ws.MODE_FULL, [738561])

ws.on_connect = on_connect
ws.on_ticks = on_ticks
ws.connect_ws()
```

## Response
Response structure remains the same of [current kiteconnect websocket](https://kite.trade/docs/connect/v3/websocket/#quote-packet-structure).
```
DEBUG:root:Ticks: [{'tradable': True, 'mode': 'ltp', 'instrument_token': 5633, 'last_price': 2298.85}, 
{'tradable': True, 'mode': 'full', 'instrument_token': 738561, 'last_price': 2483.45, 
'last_traded_quantity': 21, 
'average_traded_price': 2488.65, 'volume_traded': 6723054, 'total_buy_quantity': 184955, 
'total_sell_quantity': 1315993, 'ohlc': {'open': 2503.55, 'high': 2505.45, 'low': 2472.0, 
'close': 2489.9}, 'change': -0.2590465480541497, 'last_trade_time': None, 'oi': 0, 'oi_day_high': 0, 
'oi_day_low': 0, 'exchange_timestamp': None, 'depth': {.....}}]

```
