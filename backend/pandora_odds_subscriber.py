#!/usr/bin/env python3
"""
Direct connection to pandora.ganchrow.com Socket.IO server for real-time odds.
No browser needed - connects directly to the backend API.
"""

import socketio
import json
import gzip
import base64
from typing import Dict, Any, List
from datetime import datetime
import argparse


class PandoraOddsSubscriber:
    """Subscribes to pandora.ganchrow.com Socket.IO and captures all odds updates."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.sio = socketio.Client()
        self.odds_state: Dict[str, Any] = {}
        self.message_count = 0
        
        # Set up event handlers
        self.sio.on('connect', self.on_connect)
        self.sio.on('disconnect', self.on_disconnect)
        self.sio.on('*', self.on_any_message)  # Catch all events
        
    def on_connect(self):
        """Called when connected to Socket.IO server."""
        print("[OK] Connected to pandora.ganchrow.com")
        print(f"   Socket ID: {self.sio.sid}")
        
    def on_disconnect(self):
        """Called when disconnected."""
        print("[ERROR] Disconnected from pandora.ganchrow.com")
        
    def on_any_message(self, event_name: str, *args):
        """Handle any Socket.IO event."""
        self.message_count += 1
        
        if self.verbose:
            print(f"\n[EVENT #{self.message_count}] {event_name}")
        
        # Process all arguments (Socket.IO can send multiple args)
        for i, arg in enumerate(args):
            self.process_message(arg, event_name)
    
    def process_message(self, data: Any, event_name: str = None):
        """Process a message - handles both text and binary."""
        try:
            # Handle binary data (gzipped JSON)
            if isinstance(data, bytes):
                decoded = self.decode_binary(data)
                if decoded:
                    self.handle_odds_update(decoded, event_name)
                return
                
            # Handle string data (event names/channels)
            if isinstance(data, str):
                if self.verbose:
                    print(f"   [TEXT] {data}")
                # Text messages might be event channels to subscribe to
                # Socket.IO v4 uses text for event names, binary for data
                return
                
            # Handle dict/list (already decoded JSON)
            if isinstance(data, (dict, list)):
                self.handle_odds_update(data, event_name)
                
        except Exception as e:
            print(f"[ERROR] Error processing message: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
    
    def decode_binary(self, binary_data: bytes) -> Dict[str, Any]:
        """Decode gzipped binary data from Socket.IO."""
        try:
            # Decompress gzip
            decompressed = gzip.decompress(binary_data)
            # Parse JSON
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            print(f"[ERROR] Error decoding binary: {e}")
            return None
    
    def parse_path(self, path: str) -> Dict[str, Any]:
        """Parse JSON Patch path like /c/m/10/o/2/0 into components."""
        parts = [p for p in path.split('/') if p]
        if len(parts) >= 5 and parts[0] == 'c' and parts[1] == 'm' and parts[3] == 'o':
            return {
                'market': int(parts[2]),
                'outcome': parts[4],
                'index': int(parts[5]) if len(parts) > 5 else None,
                'full_path': path
            }
        return None
    
    def handle_odds_update(self, data: Dict[str, Any], event_name: str = None):
        """Handle an odds update message."""
        if not isinstance(data, dict):
            return
            
        # Handle JSON Patch format (incremental updates)
        if data.get('isDiff') and 'payload' in data:
            if self.verbose:
                print(f"   [JSON Patch] {len(data['payload'])} operations")
            
            for op in data['payload']:
                if op.get('op') == 'replace' and 'path' in op:
                    parsed = self.parse_path(op['path'])
                    if parsed:
                        key = f"{parsed['market']}.{parsed['outcome']}.{parsed['index']}"
                        self.odds_state[key] = {
                            'value': op['value'],
                            'market': parsed['market'],
                            'outcome': parsed['outcome'],
                            'index': parsed['index'],
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        if self.verbose:
                            idx = parsed['index']
                            val = op['value']
                            if idx == 0:
                                print(f"      Market {parsed['market']}, Outcome {parsed['outcome']}: Price = ${val:.2f}")
                            elif idx == 1:
                                us_odds = f"+{int((val - 1) * 100)}" if val > 1 else f"{int((val - 1) * 100)}"
                                prob = (1 / val) * 100
                                print(f"      Market {parsed['market']}, Outcome {parsed['outcome']}: {us_odds} ({prob:.2f}% implied)")
                            else:
                                print(f"      Market {parsed['market']}, Outcome {parsed['outcome']}, Index {idx}: {val}")
                    else:
                        if self.verbose:
                            print(f"      Path: {op['path']}, Value: {op['value']}")
        
        # Handle other message formats
        else:
            if self.verbose:
                print(f"   [OTHER] Message format:")
                print(f"      {json.dumps(data, indent=2)}")
    
    def connect(self, origin: str = "https://plive.becoms.co"):
        """Connect to pandora.ganchrow.com Socket.IO server."""
        try:
            # Connect to Socket.IO server
            # EIO=4 means Socket.IO protocol version 4
            self.sio.connect(
                'wss://pandora.ganchrow.com',
                transports=['websocket'],
                socketio_path='/socket.io/',
                headers={
                    'Origin': origin,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                wait_timeout=10
            )
            return True
        except Exception as e:
            print(f"[ERROR] Connection error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def wait(self):
        """Wait for messages (blocks until disconnect)."""
        try:
            self.sio.wait()
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Shutting down...")
            self.sio.disconnect()
    
    def get_odds_state(self) -> Dict[str, Any]:
        """Get current odds state."""
        return self.odds_state.copy()
    
    def export_messages(self) -> List[Dict[str, Any]]:
        """Export all captured messages (for debugging)."""
        return {
            'message_count': self.message_count,
            'odds_state': self.odds_state,
            'timestamp': datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description='Subscribe to pandora.ganchrow.com odds feed')
    parser.add_argument('--quiet', '-q', action='store_true', help='Less verbose output')
    parser.add_argument('--origin', default='https://plive.becoms.co', help='Origin header to send')
    args = parser.parse_args()
    
    subscriber = PandoraOddsSubscriber(verbose=not args.quiet)
    
    print("[CONNECTING] Connecting to pandora.ganchrow.com...")
    print(f"   Origin: {args.origin}")
    
    if subscriber.connect(origin=args.origin):
        print("\n[OK] Connected! Waiting for odds updates...")
        print("   (Press Ctrl+C to stop)\n")
        
        try:
            subscriber.wait()
        except KeyboardInterrupt:
            print("\n\n[STATS] Final stats:")
            print(f"   Messages received: {subscriber.message_count}")
            print(f"   Odds state entries: {len(subscriber.odds_state)}")
            
            # Export final state
            export = subscriber.export_messages()
            with open('pandora_odds_export.json', 'w') as f:
                json.dump(export, f, indent=2)
            print(f"   Exported to: pandora_odds_export.json")


if __name__ == '__main__':
    main()

