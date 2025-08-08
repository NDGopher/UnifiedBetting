import threading
from typing import Callable, Optional

import socketio


class PLiveWebSocketClient:
    """Socket.IO v4 client to Pandora/Ganchrow. Uses python-socketio client.
    We'll join namespaces/rooms as we discover them, and forward incoming events.
    """

    def __init__(self, base_url: str = "https://pandora.ganchrow.com", on_message: Optional[Callable[[str], None]] = None, auth: Optional[dict] = None):
        self.base_url = base_url
        self.on_message = on_message
        self.sio = socketio.Client(reconnection=True)
        self.thread: Optional[threading.Thread] = None
        self.auth = auth or {}

        @self.sio.event
        def connect():
            # Connected to base namespace
            pass

        @self.sio.on('*')
        def catch_all(event, data=None):
            if self.on_message:
                try:
                    self.on_message(str({"event": event, "data": data}))
                except Exception:
                    pass

        @self.sio.event
        def disconnect():
            pass

    def start(self):
        def run():
            try:
                self.sio.connect(self.base_url, transports=["websocket"], wait_timeout=10, auth=self.auth)
                self.sio.wait()
            except Exception:
                pass
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass

