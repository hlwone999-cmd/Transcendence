"""MT5 Socket Bridge — adaptasi dari huy-bui-tech/mt5_api (MIT).

Hanya komponen inti yang diintegrasikan: protocol, server, trading.
Komponen UI (Tkinter order panel), timing/latency, dan dependensi
telegram/aiohttp sengaja TIDAK disalin karena tidak diperlukan —
integrasi di kalkulator XAUUSD bersifat READ-ONLY.

Dokumentasi: docs/MT5-BRIDGE.md
"""

from .trading import MT5Bridge, MT5BridgeError, NotConnectedError, TradeError
from .protocol import (
    Action,
    OrderType,
    Timeframe,
    OrderResult,
    TickData,
    AccountInfo,
    Position,
    CloseResult,
)

__all__ = [
    "MT5Bridge",
    "MT5BridgeError",
    "NotConnectedError",
    "TradeError",
    "Action",
    "OrderType",
    "Timeframe",
    "OrderResult",
    "TickData",
    "AccountInfo",
    "Position",
    "CloseResult",
]

__version__ = "0.1.0"
