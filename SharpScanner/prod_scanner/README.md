# Sports Liquidity Scanner - Production Release

A high-frequency sports betting arbitrage scanner that monitors Kalshi and Polymarket for steam moves, whale walls, and dam breaks.

## 🚀 Quick Start

### One-Click Launch (Windows)

**Double-click `Start_Scanner.bat`**

The launcher will:
- ✅ Check for Python
- ✅ Create/activate virtual environment
- ✅ Install dependencies automatically
- ✅ Run the scanner

### Manual Launch

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API credentials
# Copy .env.example to .env and add your credentials

# 5. Run the scanner
python main.py
```

## 📋 Requirements

- Python 3.8 or higher
- API credentials for Kalshi (optional, but recommended)
- Internet connection

## ⚙️ Configuration

1. Copy `env_example.txt` to `.env`
2. Add your Kalshi API credentials:

   **Option A: Using Key File (Recommended)**
   ```env
   KALSHI_API_KEY=your_key_id
   KALSHI_PRIVATE_KEY_PATH=kalshi.key
   ```
   Make sure `kalshi.key` is in the `prod_scanner` folder.

   **Option B: Using Direct Key Values**
   ```env
   KALSHI_API_KEY=your_key_id
   KALSHI_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----
   ...your private key content...
   -----END RSA PRIVATE KEY-----
   ```

   **Option C: Polymarket Credentials (Optional)**
   ```env
   POLY_API_KEY=your_poly_key
   POLY_API_SECRET=your_poly_secret
   POLY_PASSPHRASE=your_poly_passphrase
   ```

**Note:** 
- Polymarket does not require authentication for read-only access
- The scanner supports both `KALSHI_API_KEY` and `KALSHI_KEY_ID` (for backward compatibility)

## 🎯 Features

### Real-Time Detection

- **Steam Moves:** VWAP-based detection of significant price movements
- **Whale Walls:** Large limit orders indicating smart money positions
- **Dam Breaks:** High-conviction alerts when whale walls are consumed

### Quality Filters

- **Gold Zone:** Only processes markets with 20-80 cent midpoint prices
- **Tight Spread:** Maximum 4-cent spread for accurate pricing
- **Liquidity Depth:** Minimum $1,000 liquidity for actionable signals

### Professional UI

- **Visual Heartbeat:** 🟢/⚪ indicator shows scanner is running
- **American Odds:** All prices displayed as `-110 (52¢)` format
- **Clickable Links:** Click event names to open market pages
- **Pre-Flight Check:** Network health check before starting

### Audio Alerts

- **Whale:** Single beep
- **Steam:** Double beep
- **Dam Break:** Triple beep (highest priority)

## 📊 Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│         LIVE SPORTS LIQUIDITY SCANNER [PROD]            │
├──────────────────────┬──────────────────────────────────┤
│ 🐋 ACTIVE WHALE WATCH│  📉 MARKET TAPE                  │
│                      │                                  │
│ Platform | Event     │  Time | Platform | Event | ...  │
│ ...                  │  ...                            │
├──────────────────────┴──────────────────────────────────┤
│ 🟢 Scanning 150 Markets | API Latency: 120ms | ...     │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
prod_scanner/
├── main.py              # Entry point and UI
├── config.py            # Configuration and thresholds
├── connectors.py        # API connections (Kalshi, Polymarket)
├── analyzer.py          # Market analysis logic
├── utils.py             # Odds conversion and formatting
├── requirements.txt     # Python dependencies
├── .env                 # API credentials (create from env_example.txt)
├── Start_Scanner.bat    # One-click launcher (Windows)
├── build_exe.py         # PyInstaller build script (optional)
└── logs/                # CSV logs of all alerts
```

## 🔧 Advanced Usage

### Building Standalone Executable

```bash
python build_exe.py
```

This creates `dist/scanner.exe` (Windows) or `dist/scanner` (Linux/Mac).

**Important:** Copy your `.env` file next to the executable after building.

### Customizing Thresholds

Edit `config.py` to adjust:
- `GOLD_ZONE`: Price range filter (default: 0.20-0.80)
- `MAX_SPREAD_CENTS`: Maximum spread width (default: 0.04)
- `STEAM_THRESHOLD`: Price movement threshold (default: 0.025 = 2.5%)
- `WHALE_MIN_SIZE`: Minimum wall size (default: $5,000)
- `SCAN_INTERVAL`: Scan frequency in seconds (default: 5)

## 📝 Logging

All alerts are automatically logged to `logs/session_data_YYYYMMDD_HHMMSS.csv` with columns:
- Timestamp
- Platform
- Event
- Signal_Type
- Price
- Details

## 🐛 Troubleshooting

### "Python is not installed"
- Install Python 3.8+ from https://www.python.org/
- Make sure to check "Add Python to PATH" during installation

### "Module not found"
- Run: `pip install -r requirements.txt`
- Make sure virtual environment is activated

### "No data showing"
- Check your `.env` file has correct credentials
- Check internet connection
- Review logs for API errors

### "Heartbeat stopped blinking"
- Scanner loop may be frozen
- Restart the scanner (Ctrl+C, then restart)
- Check for API timeouts in logs

### Audio alerts not working
- VS Code terminal may mute system bell
- Run in OS terminal (PowerShell/CMD) to hear beeps
- Audio requires system sound to be enabled

## 📚 Documentation

- `PRODUCTION_SCANNER_GUIDE.md` - Full technical documentation
- `COMMERCIAL_GRADE_FEATURES.md` - UX features overview
- `FINAL_UX_POLISH.md` - UI polish details

## ⚠️ Disclaimer

This tool is for informational purposes only. Always verify signals on the exchange before placing bets. Past performance does not guarantee future results.

## 📄 License

See LICENSE file for details.

## 🤝 Support

For issues or questions, please review the documentation files or check the logs directory for error details.

---

**Ready to scan? Double-click `Start_Scanner.bat` and start finding opportunities!** 🚀
