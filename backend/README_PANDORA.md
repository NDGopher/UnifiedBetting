# Pandora Odds Subscriber - Direct Backend Connection

This connects **directly** to `pandora.ganchrow.com` Socket.IO server - no browser needed!

## Setup

1. **Install the dependency:**
   ```bash
   pip install python-socketio
   ```

   Or install all requirements:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

**Just run it:**
```bash
python backend/pandora_odds_subscriber.py
```

It will:
- Connect to `wss://pandora.ganchrow.com/socket.io/`
- Capture **ALL** odds updates from **ALL** games
- Display them in real-time
- Save final state to `pandora_odds_export.json` when you stop it (Ctrl+C)

## Options

- `--quiet` / `-q`: Less verbose output
- `--origin <url>`: Change Origin header (default: `https://plive.becoms.co`)

## Example Output

```
🚀 Connecting to pandora.ganchrow.com...
   Origin: https://plive.becoms.co
✅ Connected to pandora.ganchrow.com
   Socket ID: abc123

✅ Connected! Waiting for odds updates...
   (Press Ctrl+C to stop)

📧 Event #1: live.main.U0VWU1NWUkJSMFU9.eventCoefficients.170286421
   📦 JSON Patch update (7 operations)
      Market 10, Outcome 2: Price = $4.21
      Market 10, Outcome 2: +187 (18.73% implied)
      Market 5, Outcome 2.5: Price = $6.09
   ...

📊 Final stats:
   Messages received: 1523
   Odds state entries: 847
   Exported to: pandora_odds_export.json
```

## What It Captures

- **All odds updates** from all markets
- **All games** automatically (it's a broadcast feed)
- **Real-time** - updates as they happen
- **No rate limiting** - just a passive Socket.IO connection

## Next Steps

Once you confirm it works, we can:
1. Parse market IDs to game names
2. Filter to specific games/markets
3. Integrate with your betting system
4. Store in database
5. Calculate EV automatically

---

**That's it! No browser, no extensions, no complexity - just a direct connection to the source!** 🚀

