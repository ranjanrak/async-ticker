import six
import asyncio
import struct
import json

from autobahn.asyncio.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory

class TickerClientProtocol(WebSocketClientProtocol):
    """ Kite ticker autobahn WebSocket base protocol """

    def onConnect(self, response):
        """
        Called when WebSocket server connection is established successfully
        """
        self.factory.ws = self
        self.factory.on_connect(self, response)

    def onOpen(self):
        """
        Called when the initial WebSocket opening handshake was completed
        """
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        """
        Called when text or payload is received.
        """
        if self.factory.on_message:
            self.factory.on_message(self, payload, isBinary)

    def onClose(self, wasClean, code, reason):
        """
        Called when connection is closed
        """
        print("WebSocket connection closed: {0}".format(reason))


class TickerClientFactory(WebSocketClientFactory):
    """
    Implement custom call backs for WebSocketClientFactory
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize with callback methods
        """
        self.ws = None
        self.on_message = None
        self.on_connect = None

        super(TickerClientFactory, self).__init__(*args, **kwargs)

class MainTicker():
    """
    Main Ticker client
    """
    # Exchange map for ticker
    EXCHANGE_MAP = {
        "nse": 1,
        "nfo": 2,
        "cds": 3,
        "bse": 4,
        "bfo": 5,
        "bsecds": 6,
        "mcx": 7,
        "mcxsx": 8,
        "indices": 9
    }

    # Available streaming modes.
    MODE_FULL = "full"
    MODE_QUOTE = "quote"
    MODE_LTP = "ltp"

    def __init__(self, api_key, access_token):
        """
        Initialise websocket client
        """
        self.ws_url = "wss://ws.kite.trade?api_key={}&access_token={}".format(api_key, access_token)

        # Placeholders for callbacks.
        self.on_ticks = None
        self.on_connect = None
        self.on_message = None

    def connect_ws(self):
        """
        Establish ws connection
        """
        self.factory = TickerClientFactory(self.ws_url)
        self.factory.protocol = TickerClientProtocol

        self.ws = self.factory.ws

        # Register private callback
        self.factory.on_connect = self._on_connect
        self.factory.on_message = self._on_message

        # Run an infinite loop using asyncio
        loop = asyncio.get_event_loop()
        coro = loop.create_connection(self.factory, "ws.kite.trade", 443, ssl=True)
        loop.run_until_complete(coro)
        loop.run_forever()

    def _on_connect(self, ws, response):
        """ 
        proxy for on_connect 
        """
        self.ws = ws
        if self.on_connect:
            self.on_connect(self, response)

    def subscribe(self, token_list):
        """
        Subscribe to required list of tokens
        """
        self.ws.sendMessage(six.b(json.dumps({"a": "subscribe", "v": token_list})))

    def set_mode(self, mode, token_list):
        """
        Set streaming mode for the given list of tokens
        """
        self.ws.sendMessage(six.b(json.dumps({"a": "mode", "v": [mode, token_list]})))

    def _on_message(self, ws, payload, isBinary):
        """
        proxy for on_message
        """
        if self.on_message:
            self.on_message(self, payload, isBinary)

        # If the message is binary, parse it and send it to the callback.
        if self.on_ticks and isBinary and len(payload) > 4:
            self.on_ticks(self, self._parse_binary(payload))

    def _parse_binary(self, bin):
        """
        Parse binary data to a (list of) ticks structure.
        """
        packets = self._split_packets(bin)  # split data to individual ticks packet
        data = []

        for packet in packets:
            instrument_token = self._unpack_int(packet, 0, 4)
            segment = instrument_token & 0xff  # Retrive segment constant from instrument_token

            # Add price divisor based on segment
            # This factor converts paisa to rupees
            if segment == self.EXCHANGE_MAP["cds"]:
                divisor = 10000000.0
            elif segment == self.EXCHANGE_MAP["bsecds"]:
                divisor = 10000.0
            else:
                divisor = 100.0

            # All indices are not tradable
            tradable = False if segment == self.EXCHANGE_MAP["indices"] else True

            # LTP packets
            if len(packet) == 8:
                data.append({
                    "tradable": tradable,
                    "mode": self.MODE_LTP,
                    "instrument_token": instrument_token,
                    "last_price": self._unpack_int(packet, 4, 8) / divisor
                })
            # Indices quote and full mode
            elif len(packet) == 28 or len(packet) == 32:
                mode = self.MODE_QUOTE if len(packet) == 28 else self.MODE_FULL

                d = {
                    "tradable": tradable,
                    "mode": mode,
                    "instrument_token": instrument_token,
                    "last_price": self._unpack_int(packet, 4, 8) / divisor,
                    "ohlc": {
                        "high": self._unpack_int(packet, 8, 12) / divisor,
                        "low": self._unpack_int(packet, 12, 16) / divisor,
                        "open": self._unpack_int(packet, 16, 20) / divisor,
                        "close": self._unpack_int(packet, 20, 24) / divisor
                    }
                }

                # Compute the change price using close price and last price
                d["change"] = 0
                if(d["ohlc"]["close"] != 0):
                    d["change"] = (d["last_price"] - d["ohlc"]["close"]) * 100 / d["ohlc"]["close"]

                # Full mode with timestamp
                if len(packet) == 32:
                    try:
                        timestamp = datetime.fromtimestamp(self._unpack_int(packet, 28, 32))
                    except Exception:
                        timestamp = None

                    d["exchange_timestamp"] = timestamp

                data.append(d)
            # Quote and full mode
            elif len(packet) == 44 or len(packet) == 184:
                mode = self.MODE_QUOTE if len(packet) == 44 else self.MODE_FULL

                d = {
                    "tradable": tradable,
                    "mode": mode,
                    "instrument_token": instrument_token,
                    "last_price": self._unpack_int(packet, 4, 8) / divisor,
                    "last_traded_quantity": self._unpack_int(packet, 8, 12),
                    "average_traded_price": self._unpack_int(packet, 12, 16) / divisor,
                    "volume_traded": self._unpack_int(packet, 16, 20),
                    "total_buy_quantity": self._unpack_int(packet, 20, 24),
                    "total_sell_quantity": self._unpack_int(packet, 24, 28),
                    "ohlc": {
                        "open": self._unpack_int(packet, 28, 32) / divisor,
                        "high": self._unpack_int(packet, 32, 36) / divisor,
                        "low": self._unpack_int(packet, 36, 40) / divisor,
                        "close": self._unpack_int(packet, 40, 44) / divisor
                    }
                }

                # Compute the change price using close price and last price
                d["change"] = 0
                if(d["ohlc"]["close"] != 0):
                    d["change"] = (d["last_price"] - d["ohlc"]["close"]) * 100 / d["ohlc"]["close"]

                # Parse full mode
                if len(packet) == 184:
                    try:
                        last_trade_time = datetime.fromtimestamp(self._unpack_int(packet, 44, 48))
                    except Exception:
                        last_trade_time = None

                    try:
                        timestamp = datetime.fromtimestamp(self._unpack_int(packet, 60, 64))
                    except Exception:
                        timestamp = None

                    d["last_trade_time"] = last_trade_time
                    d["oi"] = self._unpack_int(packet, 48, 52)
                    d["oi_day_high"] = self._unpack_int(packet, 52, 56)
                    d["oi_day_low"] = self._unpack_int(packet, 56, 60)
                    d["exchange_timestamp"] = timestamp

                    # Market depth entries.
                    depth = {
                        "buy": [],
                        "sell": []
                    }

                    # Compile the market depth lists.
                    for i, p in enumerate(range(64, len(packet), 12)):
                        depth["sell" if i >= 5 else "buy"].append({
                            "quantity": self._unpack_int(packet, p, p + 4),
                            "price": self._unpack_int(packet, p + 4, p + 8) / divisor,
                            "orders": self._unpack_int(packet, p + 8, p + 10, byte_format="H")
                        })

                    d["depth"] = depth

                data.append(d)

        return data

    def _unpack_int(self, bin, start, end, byte_format="I"):
        """Unpack binary data as unsgined interger."""
        return struct.unpack(">" + byte_format, bin[start:end])[0]

    def _split_packets(self, bin):
        """Split the data to individual packets of ticks."""
        # Ignore heartbeat data.
        if len(bin) < 2:
            return []

        number_of_packets = self._unpack_int(bin, 0, 2, byte_format="H")
        packets = []

        j = 2
        for i in range(number_of_packets):
            packet_length = self._unpack_int(bin, j, j + 2, byte_format="H")
            packets.append(bin[j + 2: j + 2 + packet_length])
            j = j + 2 + packet_length

        return packets
