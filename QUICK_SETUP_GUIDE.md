# 🚀 UnifiedBetting Quick Setup Guide

## Prerequisites (Install these first)

### 1. Python 3.8+ 
- Download from: https://www.python.org/downloads/
- **IMPORTANT**: Check "Add Python to PATH" during installation
- Verify: Open Command Prompt and run `python --version`

### 2. Node.js 16+ 
- Download from: https://nodejs.org/
- **IMPORTANT**: Choose the LTS version
- Verify: Open Command Prompt and run `node --version` and `npm --version`

### 3. Git
- Download from: https://git-scm.com/
- Verify: Open Command Prompt and run `git --version`

### 4. Chrome Browser
- Download from: https://www.google.com/chrome/
- Required for the Chrome extensions and Selenium automation

## 🎯 One-Click Setup (Recommended)

### Option 1: Automated Setup (Windows)
1. Clone the repository:
   ```bash
   git clone https://github.com/NDGopher/UnifiedBetting.git
   cd UnifiedBetting
   ```

2. Run the automated setup:
   ```bash
   python setup_dependencies.py
   ```

3. Launch the application:
   ```bash
   python launch.py
   ```

### Option 2: Manual Setup (if automated fails)

#### Backend Setup:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

#### Frontend Setup:
```bash
cd frontend
npm install
```

#### Launch:
```bash
python launch.py
```

## 🔧 Troubleshooting

### Common Issues:

#### 1. "python not found"
- **Solution**: Reinstall Python and check "Add to PATH"
- **Verify**: `python --version` in Command Prompt

#### 2. "npm not found" 
- **Solution**: Reinstall Node.js
- **Verify**: `npm --version` in Command Prompt

#### 3. "pip install fails"
- **Solution**: Upgrade pip first:
  ```bash
  python -m pip install --upgrade pip
  ```

#### 4. "npm install fails"
- **Solution**: Clear npm cache:
  ```bash
  npm cache clean --force
  ```

#### 5. "Chrome driver issues"
- **Solution**: The setup script should handle this automatically
- **Manual fix**: Download ChromeDriver from https://chromedriver.chromium.org/

### Windows-Specific Issues:

#### 1. PowerShell Execution Policy
If you get execution policy errors:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 2. Antivirus Blocking
- Add the project folder to your antivirus exclusions
- Temporarily disable real-time protection during setup

#### 3. Port Conflicts
If ports 3000 or 5001 are in use:
```bash
# Kill processes on these ports
netstat -ano | findstr :3000
netstat -ano | findstr :5001
taskkill /PID <PID> /F
```

## 📁 What Gets Installed

### Backend Dependencies:
- FastAPI (Web framework)
- Uvicorn (ASGI server)
- Selenium (Browser automation)
- BeautifulSoup4 (Web scraping)
- SQLAlchemy (Database ORM)
- And 20+ other packages

### Frontend Dependencies:
- React 18
- TypeScript
- Material-UI
- Axios (HTTP client)
- Day.js (Date handling)

## 🎮 How to Use

1. **Start the system**: `python launch.py`
2. **Access the web interface**: http://localhost:3000
3. **Backend API**: http://localhost:5001
4. **Stop the system**: Press `Ctrl+C` in the terminal

## 📋 System Requirements

- **OS**: Windows 10/11 (primary), macOS/Linux (secondary)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Network**: Internet connection required for odds fetching

## 🔐 Configuration

Your `config.json` and `config.py` files are included in the repository. You may need to:
1. Update API keys if they've been rotated
2. Adjust database settings for your environment
3. Configure Telegram bot tokens if using alerts

## 🆘 Getting Help

If you encounter issues:
1. Check the logs in `backend/logs/` directory
2. Run `python setup_dependencies.py` again
3. Try the manual setup steps above
4. Check the troubleshooting section

## 🚀 Ready to Rock!

Once setup is complete, you'll have:
- ✅ Backend API running on port 5001
- ✅ Frontend React app on port 3000  
- ✅ Chrome extensions for betting sites
- ✅ Automated odds scraping and matching
- ✅ Real-time EV calculations
- ✅ Telegram alerts (if configured)

**Happy betting! 🎯** 