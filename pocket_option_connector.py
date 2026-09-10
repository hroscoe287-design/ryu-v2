import os
import json
import time
import threading
import requests

try:
    import socketio
except ImportError:
    socketio = None


# ============================================================
# POCKET OPTION -> RYU V2 LIVE FEED CONNECTOR
# ============================================================
#
# SIGNAL ONLY.
# This connector reads market data and sends normalized
# ticks to Ryu V2.
#
# It does NOT place trades.
#
# ============================================================

RYU_URL = os.getenv(
    "RYU_FEED_URL",
    "http://localhost:10000/api/feed"
)

SSID = os.getenv(
    "POCKET_OPTION_SSID",
    ""
)

POCKET_OPTION_WS = os.getenv(
    "POCKET_OPTION_WS",
    "https://api.po.market"
)

DEFAULT_ASSET = os.getenv(
    "DEFAULT_ASSET",
    "EUR/USD"
)

ENABLE_CONNECTOR = os.getenv(
    "POCKET_OPTION_ENABLED",
    "false"
).lower() == "true"


session = requests.Session()


def send_tick(asset, price, timestamp=None, payout=None):

    payload = {
        "asset": asset,
        "price": price,
        "timestamp": timestamp or time.time(),
    }

    if payout is not None:
        payload["payout"] = payout

    try:

        response = session.post(
            RYU_URL,
            json=payload,
            timeout=10,
        )

        if response.ok:
            print(
                "[RYU] FEED",
                asset,
                price
            )
        else:
            print(
                "[RYU] Feed rejected:",
                response.status_code,
                response.text[:300]
            )

    except Exception as exc:

        print(
            "[RYU] Feed error:",
            repr(exc)
        )


def extract_number(value):

    try:

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):

            return float(value.replace(",", ""))

    except Exception:
        pass

    return None


def normalize_asset(asset):

    if not asset:
        return DEFAULT_ASSET

    asset = str(asset)

    replacements = {
        "_": "/",
        "-": "/",
    }

    for old, new in replacements.items():

        asset = asset.replace(old, new)

    return asset


def process_message(message):

    """
    Attempts to normalize common Pocket Option
    WebSocket message structures.

    Because Pocket Option's internal protocol is
    unofficial and can change, this intentionally
    accepts several structures rather than assuming
    one permanent payload format.
    """

    if message is None:
        return

    # --------------------------------------------------------
    # STRING MESSAGE
    # --------------------------------------------------------

    if isinstance(message, str):

        try:
            parsed = json.loads(message)

        except Exception:
            return

        return process_message(parsed)

    # --------------------------------------------------------
    # LIST MESSAGE
    # --------------------------------------------------------

    if isinstance(message, list):

        # Socket.IO event style:
        #
        # ["event", {...}]

        if len(message) >= 2:

            event = message[0]
            payload = message[1]

            if isinstance(payload, dict):

                process_message(payload)

            elif isinstance(payload, list):

                for item in payload:
                    process_message(item)

        return

    # --------------------------------------------------------
    # DICT MESSAGE
    # --------------------------------------------------------

    if not isinstance(message, dict):
        return

    asset = (
        message.get("asset")
        or message.get("symbol")
        or message.get("pair")
        or message.get("instrument")
        or DEFAULT_ASSET
    )

    price = (
        message.get("price")
        or message.get("rate")
        or message.get("quote")
        or message.get("close")
        or message.get("value")
    )

    timestamp = (
        message.get("timestamp")
        or message.get("time")
        or message.get("created_at")
    )

    payout = (
        message.get("payout")
        or message.get("profit")
    )

    price = extract_number(price)

    if price is None:
        return

    timestamp = extract_number(timestamp)

    if timestamp and timestamp > 100000000000:
        timestamp /= 1000

    payout = extract_number(payout)

    send_tick(
        normalize_asset(asset),
        price,
        timestamp,
        payout,
    )


def connect_socketio():

    if socketio is None:

        raise RuntimeError(
            "python-socketio is not installed"
        )

    if not SSID:

        raise RuntimeError(
            "POCKET_OPTION_SSID is missing"
        )

    sio = socketio.Client(
        reconnection=True,
        logger=False,
        engineio_logger=False,
    )

    @sio.event
    def connect():

        print(
            "[POCKET OPTION] WebSocket connected"
        )

        # Pocket Option community clients use an
        # auth/session message. Exact protocol can
        # change, so this is isolated here.

        auth_payload = {
            "session": SSID,
        }

        try:

            sio.emit(
                "auth",
                auth_payload
            )

            print(
                "[POCKET OPTION] Authentication sent"
            )

        except Exception as exc:

            print(
                "[POCKET OPTION] Auth error:",
                repr(exc)
            )

    @sio.event
    def disconnect():

        print(
            "[POCKET OPTION] WebSocket disconnected"
        )

    @sio.on("*")
    def catch_all(event, data):

        print(
            "[POCKET OPTION]",
            event
        )

        try:

            process_message(data)

        except Exception as exc:

            print(
                "[POCKET OPTION] Parse error:",
                repr(exc)
            )

    while True:

        try:

            print(
                "[POCKET OPTION] Connecting to",
                POCKET_OPTION_WS
            )

            sio.connect(
                POCKET_OPTION_WS,
                transports=["websocket"],
                wait_timeout=20,
            )

            sio.wait()

        except Exception as exc:

            print(
                "[POCKET OPTION] Connection failed:",
                repr(exc)
            )

            time.sleep(10)


def main():

    print("====================================")
    print("RYU V2 POCKET OPTION CONNECTOR")
    print("SIGNAL ONLY")
    print("====================================")

    print(
        "RYU_FEED_URL:",
        RYU_URL
    )

    print(
        "Pocket Option:",
        POCKET_OPTION_WS
    )

    print(
        "Enabled:",
        ENABLE_CONNECTOR
    )

    if not ENABLE_CONNECTOR:

        print(
            "POCKET_OPTION_ENABLED is false."
        )

        print(
            "Connector will not connect."
        )

        while True:
            time.sleep(60)

    connect_socketio()


if __name__ == "__main__":
    main()
