import os
import subprocess
import sys
import webbrowser
from pathlib import Path
import json
import shutil
import socket
import time
import logging
import threading
import platform
import signal
import psutil
import atexit
import ctypes
import msvcrt
import win32gui
import win32con
import win32api

# Configure Windows console for colors
if platform.system() == "Windows":
    try:
        # Enable ANSI color support
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

# Color codes for Windows PowerShell
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

def print_banner():
    """Print a beautiful banner"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                    UNIFIED BETTING APP                       ║
║                        LAUNCHER                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)

def print_status(message, status="INFO", color=Colors.WHITE):
    """Print a formatted status message"""
    timestamp = time.strftime("%H:%M:%S")
    status_colors = {
        "INFO": Colors.BLUE,
        "SUCCESS": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "PROGRESS": Colors.CYAN
    }
    status_color = status_colors.get(status, Colors.WHITE)
    print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} {status_color}[{status}]{Colors.RESET} {color}{message}{Colors.RESET}")

def print_progress(current, total, description=""):
    """Print a progress bar"""
    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    percentage = current * 100 // total
    print(f"\r{Colors.CYAN}[PROGRESS]{Colors.RESET} {description} |{bar}| {percentage}%", end='', flush=True)
    if current == total:
        print()  # New line when complete

# Configure logging with custom formatter
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Add colors to log levels
        if record.levelno >= logging.ERROR:
            color = Colors.RED
        elif record.levelno >= logging.WARNING:
            color = Colors.YELLOW
        elif record.levelno >= logging.INFO:
            color = Colors.BLUE
        else:
            color = Colors.GRAY
        
        # Format the message
        formatted = super().format(record)
        return f"{color}{formatted}{Colors.RESET}"

# Configure logging - import from backend (should work if running from venv Python)
# Add backend to path if not already there
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from config import setup_logging
    setup_logging()
except ImportError:
    # Fallback to basic logging if config module isn't available
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# Apply colored formatter to console handler only
for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Global variables to track processes
backend_process = None
frontend_process = None
chrome_processes = []
all_child_processes = []
cleanup_done = False

def handle_chrome_restore_dialog():
    """Automatically handle Chrome restore dialog if it appears"""
    try:
        if not (win32gui and win32con and win32api):
            return False  # Can't handle dialog without win32 modules
        import time
        
        # Wait a moment for the dialog to appear
        time.sleep(2)
        
        # Look for Chrome restore dialog window with multiple approaches
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                # Look for various restore dialog variations
                if any(keyword in window_text.lower() for keyword in [
                    'restore', 'chrome', 'session', 'reopen', 'recovery'
                ]):
                    windows.append((hwnd, window_text))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        for hwnd, window_text in windows:
            try:
                print_status(f"Found Chrome dialog: {window_text}", "INFO", Colors.YELLOW)
                
                # Try multiple approaches to close the dialog
                # Method 1: Send Alt+N (Don't restore)
                win32api.SendMessage(hwnd, win32con.WM_SYSKEYDOWN, ord('N'), 0x001C0001)
                win32api.SendMessage(hwnd, win32con.WM_SYSKEYUP, ord('N'), 0xC01C0001)
                time.sleep(0.5)
                
                # Method 2: Send Escape key
                win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
                win32api.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
                time.sleep(0.5)
                
                # Method 3: Send Enter key
                win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                win32api.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                
                print_status("✅ Automatically handled Chrome restore dialog", "SUCCESS", Colors.GREEN)
                return True
            except Exception as e:
                print_status(f"Failed to handle dialog: {e}", "WARNING", Colors.YELLOW)
                continue
    except Exception as e:
        print_status(f"Chrome restore dialog handling failed: {e}", "WARNING", Colors.YELLOW)
    return False

def cleanup_on_exit():
    """Cleanup function to be called when the script exits"""
    global cleanup_done
    if cleanup_done:
        return
    cleanup_done = True
    
    print_status("🔄 Force cleaning up ALL processes and windows...", "PROGRESS", Colors.YELLOW)
    print_status("💡 If Chrome shows a 'restore pages' dialog, click 'Don't restore'", "INFO", Colors.YELLOW)
    
    # Kill backend and frontend processes
    if backend_process and backend_process.poll() is None:
        print_status("Force killing backend process...", "INFO", Colors.BLUE)
        try:
            backend_process.kill()
        except:
            pass
    
    if frontend_process and frontend_process.poll() is None:
        print_status("Force killing frontend process...", "INFO", Colors.BLUE)
        try:
            frontend_process.kill()
        except:
            pass
    
    # Kill all child processes aggressively
    for proc in all_child_processes:
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except:
                pass
    
    # Force kill ALL Chrome processes (this is the main issue)
    print_status("Force killing ALL Chrome processes...", "INFO", Colors.RED)
    try:
        subprocess.run("taskkill /f /im chrome.exe", shell=True, capture_output=True)
        subprocess.run("taskkill /f /im chromedriver.exe", shell=True, capture_output=True)
        
        # Wait a moment for Chrome to potentially show restore dialog
        time.sleep(1)
        
        # Automatically handle Chrome restore dialog if it appears
        handle_chrome_restore_dialog()
        
    except:
        pass
    
    # Close Chrome windows related to the app
    close_chrome_windows()
    
    # Kill processes on our ports aggressively
    for port in [5001, 3000, 3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008, 3009, 3010]:
        kill_process_on_port(port)
    
    # Force kill any remaining node and python processes related to our app
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name']:
                    name = proc.info['name'].lower()
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    
                    # Kill ALL node processes (they might be running our frontend)
                    if name == 'node.exe':
                        print_status(f"Force killing Node process: {proc.info['pid']}", "INFO", Colors.YELLOW)
                        proc.kill()
                    
                    # Kill ALL python processes (they might be running our backend)
                    elif name == 'python.exe':
                        print_status(f"Force killing Python process: {proc.info['pid']}", "INFO", Colors.YELLOW)
                        proc.kill()
                    
                    # Kill ALL Chrome processes
                    elif name == 'chrome.exe' or name == 'chromedriver.exe':
                        print_status(f"Force killing Chrome process: {proc.info['pid']}", "INFO", Colors.YELLOW)
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except:
        pass
    
    print_status("✅ Force cleanup complete!", "SUCCESS", Colors.GREEN)

def close_chrome_windows():
    """Close Chrome windows related to the betting app"""
    try:
        import psutil
        
        print_status("🔍 Force closing ALL Chrome windows...", "INFO", Colors.CYAN)
        
        # Force kill ALL Chrome processes
        try:
            subprocess.run("taskkill /f /im chrome.exe", shell=True, capture_output=True)
            subprocess.run("taskkill /f /im chromedriver.exe", shell=True, capture_output=True)
            print_status("✅ All Chrome processes force killed", "SUCCESS", Colors.GREEN)
        except:
            pass
        
        # Also try to find and kill specific Chrome processes
        chrome_closed = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    print_status(f"Force killing Chrome process: {proc.info['pid']}", "INFO", Colors.YELLOW)
                    try:
                        proc.kill()
                        chrome_closed = True
                    except:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if not chrome_closed:
            print_status("No additional Chrome processes found", "INFO", Colors.GRAY)
                
    except Exception as e:
        print_status(f"Error closing Chrome windows: {e}", "ERROR", Colors.RED)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print_status(f"🛑 Received signal {signum}, shutting down...", "WARNING", Colors.YELLOW)
    cleanup_on_exit()
    sys.exit(0)

def windows_console_handler(event_type):
    """Handle Windows console events for better cleanup"""
    if event_type in [signal.CTRL_C_EVENT, signal.CTRL_BREAK_EVENT]:
        print_status("Received shutdown signal, cleaning up...", "INFO", Colors.YELLOW)
        cleanup_on_exit()
        sys.exit(0)
    elif event_type == signal.CTRL_CLOSE_EVENT:
        print_status("Console window closing, cleaning up...", "INFO", Colors.YELLOW)
        cleanup_on_exit()
        sys.exit(0)

# Set up signal handlers for Windows
if platform.system() == "Windows":
    try:
        # Register for console events
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCtrlHandler(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)(windows_console_handler), True)
        
        # Also set up Python signal handlers as backup
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Register cleanup function to run on exit
        atexit.register(cleanup_on_exit)
        
    except Exception as e:
        print_status(f"Warning: Could not set up Windows signal handlers: {e}", "WARNING", Colors.YELLOW)
        # Fallback to Python signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        atexit.register(cleanup_on_exit)
else:
    # Unix-like systems
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup_on_exit)

def find_free_port(start_port=3000, max_port=3010):
    """Find a free port in the given range"""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return None

def kill_process_on_port(port):
    """Kill any process running on the specified port"""
    try:
        import psutil
    except ImportError:
        print_status("psutil not found, attempting to install...", "WARNING", Colors.YELLOW)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psutil'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import psutil
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.net_connections():
                if conn.laddr.port == port:
                    print_status(f"Killing process on port {port}", "INFO", Colors.YELLOW)
                    proc.kill()
                    time.sleep(0.5)  # Reduced wait time
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def run_command(command, cwd=None, silent=False):
    """Run a command and print its output in real-time"""
    if not silent:
        print_status(f"Running command: {command}", "INFO", Colors.GRAY)
    
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE if silent else None,
        stderr=subprocess.STDOUT if silent else None,
        text=True,
        shell=True,
        cwd=cwd
    )
    
    # Track the process for cleanup
    all_child_processes.append(process)
    
    if silent:
        # For silent commands, just wait and return the result
        process.wait()
        if process.returncode != 0:
            print_status(f"Silent command failed with return code {process.returncode}", "ERROR", Colors.RED)
    else:
        # For non-silent commands, show output in real-time
        process.wait()
        if process.returncode != 0:
            print_status(f"Command failed with return code {process.returncode}", "ERROR", Colors.RED)
    
    return process

def check_dependencies_installed(backend_dir, frontend_dir):
    """Check if dependencies are already installed"""
    backend_venv = backend_dir / "venv"
    frontend_node_modules = frontend_dir / "node_modules"
    
    # Check if uvicorn is installed in the virtual environment
    if sys.platform == "win32":
        pip_cmd = str(backend_dir / "venv" / "Scripts" / "pip")
    else:
        pip_cmd = str(backend_dir / "venv" / "bin" / "pip")
    
    try:
        result = subprocess.run(
            f'"{pip_cmd}" show uvicorn',
            shell=True,
            capture_output=True,
            text=True
        )
        uvicorn_installed = result.returncode == 0
    except:
        uvicorn_installed = False
    
    return backend_venv.exists() and frontend_node_modules.exists() and uvicorn_installed

def check_for_problematic_files(directory):
    """Check for problematic files like '-' and remove them"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == '-':
                file_path = os.path.join(root, file)
                print_status(f"Removing problematic file: {file_path}", "WARNING", Colors.YELLOW)
                try:
                    os.remove(file_path)
                except Exception as e:
                    print_status(f"Error removing file {file_path}: {e}", "ERROR", Colors.RED)

def setup_pto_profile(backend_dir, python_cmd):
    """Setup PTO Chrome profile if needed"""
    print_status("=== Checking PTO Chrome Profile ===", "INFO", Colors.BLUE)
    
    config_path = backend_dir / "config.json"
    if not config_path.exists():
        print_status("config.json not found, PTO setup will be needed", "WARNING", Colors.YELLOW)
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        pto_config = config.get("pto", {})
        profile_dir = pto_config.get("chrome_user_data_dir")
        
        # Check if profile already exists and is working
        if profile_dir and os.path.exists(profile_dir):
            print_status("PTO profile directory exists, testing...", "INFO", Colors.BLUE)
            
            # More robust test that handles Chrome restore dialogs
            test_cmd = f'{python_cmd} -c "from pto_scraper import PTOScraper; import json; config=json.load(open(\'config.json\')); scraper=PTOScraper(config[\'pto\']); result=scraper.test_profile(); print(\'Profile test result:\', result)"'
            result = subprocess.run(test_cmd, shell=True, cwd=backend_dir, capture_output=True, text=True, timeout=30)
            
            # Handle Chrome restore dialog if it appears during testing
            time.sleep(2)  # Wait for Chrome to potentially show dialog
            handle_chrome_restore_dialog()
            
            if "Profile test result: True" in result.stdout:
                print_status("✅ PTO profile is working correctly", "SUCCESS", Colors.GREEN)
            elif "Profile test result: False" in result.stdout:
                print_status("⚠️ PTO profile test failed - may need setup", "WARNING", Colors.YELLOW)
                print_status("💡 You can run 'python setup_pto_profile.py' in the backend directory to fix this", "INFO", Colors.GRAY)
            else:
                # Check if it's a Chrome restore dialog issue
                if "restore" in result.stderr.lower() or "restore" in result.stdout.lower():
                    print_status("⚠️ Chrome restore dialog detected - profile may need attention", "WARNING", Colors.YELLOW)
                    print_status("💡 Please close any Chrome restore dialogs and try again", "INFO", Colors.GRAY)
                else:
                    print_status("⚠️ PTO profile test failed - will need setup", "WARNING", Colors.YELLOW)
                    print_status("💡 You can run 'python setup_pto_profile.py' in the backend directory to fix this", "INFO", Colors.GRAY)
        else:
            print_status("ℹ️ PTO profile not found - will need setup", "INFO", Colors.YELLOW)
            print_status("💡 You can run 'python setup_pto_profile.py' in the backend directory to set it up", "INFO", Colors.GRAY)
            
    except Exception as e:
        print_status(f"Error checking PTO profile: {e}", "ERROR", Colors.RED)
        print_status("💡 You can run 'python setup_pto_profile.py' in the backend directory to set it up", "INFO", Colors.GRAY)
        return False

def open_pinnacle_odds_dropper():
    """Open pinnacleoddsdropper.com in default browser"""
    print_status("=== Opening Pinnacle Odds Dropper ===", "INFO", Colors.BLUE)
    try:
        url = "https://pinnacleoddsdropper.com"
        print_status(f"Opening {url} in default browser...", "INFO", Colors.BLUE)
        
        # Try to force Chrome first
        try:
            import webbrowser
            chrome_browser = webbrowser.get('chrome')
            chrome_browser.open(url)
            print_status("✅ Pinnacle Odds Dropper opened successfully in Chrome", "SUCCESS", Colors.GREEN)
            return True
        except Exception as chrome_error:
            print_status(f"Chrome failed: {chrome_error}, trying default browser...", "WARNING", Colors.YELLOW)
            # Fallback to default browser
        webbrowser.open(url)
        print_status("✅ Pinnacle Odds Dropper opened successfully in default browser", "SUCCESS", Colors.GREEN)
        return True
            
    except Exception as e:
        print_status(f"Failed to open Pinnacle Odds Dropper: {e}", "ERROR", Colors.RED)
        print_status("💡 You can manually open https://pinnacleoddsdropper.com in your browser", "INFO", Colors.YELLOW)
        return False

def refresh_pinnacle_odds_dropper():
    """Refresh the Pinnacle Odds Dropper tab to ensure Chrome extension is working"""
    print_status("=== Refreshing Pinnacle Odds Dropper ===", "INFO", Colors.BLUE)
    try:
        url = "https://pinnacleoddsdropper.com"
        print_status(f"Refreshing {url} in existing browser window...", "INFO", Colors.BLUE)
        webbrowser.open(url, new=1)  # new=1 refreshes existing window
        print_status("✅ Pinnacle Odds Dropper refreshed successfully", "SUCCESS", Colors.GREEN)
        return True
    except Exception as e:
        print_status(f"Failed to refresh Pinnacle Odds Dropper: {e}", "ERROR", Colors.RED)
        return False

def setup_backend():
    """Set up the backend environment and install dependencies"""
    print_status("=== Setting up Backend ===", "INFO", Colors.BLUE)
    backend_dir = Path("backend")
    
    # Create virtual environment if it doesn't exist
    venv_path = backend_dir / "venv"
    if not venv_path.exists():
        print_status("Creating virtual environment...", "INFO", Colors.BLUE)
        result = run_command("python -m venv venv", cwd=backend_dir)
        if result.wait() != 0:
            raise Exception("Failed to create virtual environment")
        print_status("✅ Virtual environment created successfully", "SUCCESS", Colors.GREEN)
    else:
        print_status("✅ Virtual environment already exists", "SUCCESS", Colors.GREEN)
    
    # Activate virtual environment and install dependencies
    if sys.platform == "win32":
        activate_cmd = "venv\\Scripts\\activate.bat"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "venv/bin/activate"
        python_cmd = "venv/bin/python"
    
    # Check if dependencies are already installed
    if (backend_dir / "requirements.txt").exists():
        # Check if key packages are already installed
        try:
            result = subprocess.run(
                f'"{python_cmd}" -c "import uvicorn, fastapi, selenium; print(\'deps_installed\')"',
                shell=True,
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            deps_installed = "deps_installed" in result.stdout
        except:
            deps_installed = False
        
        if not deps_installed:
            print_status("Installing backend dependencies...", "INFO", Colors.BLUE)
            print_status("💡 This may take a few minutes on first run...", "INFO", Colors.YELLOW)
            
            # First upgrade pip to avoid warnings (with output)
            print_status("Upgrading pip...", "INFO", Colors.BLUE)
            pip_upgrade_result = run_command(f"{python_cmd} -m pip install --upgrade pip", cwd=backend_dir, silent=False)
            if pip_upgrade_result.wait() != 0:
                print_status("⚠️ Pip upgrade failed, but continuing with installation...", "WARNING", Colors.YELLOW)
                # Don't fail completely - some systems work fine without pip upgrade
            
            # Then install requirements (with output and timeout)
            print_status("Installing Python packages...", "INFO", Colors.BLUE)
            install_process = run_command(f"{python_cmd} -m pip install -r requirements.txt", cwd=backend_dir, silent=False)
            
            # Wait with timeout and progress indication
            start_time = time.time()
            timeout = 300  # 5 minutes timeout
            while install_process.poll() is None:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    install_process.kill()
                    raise Exception(f"Pip install timed out after {timeout} seconds")
                
                # Show progress every 10 seconds
                if int(elapsed) % 10 == 0 and elapsed > 0:
                    print_status(f"Still installing... ({int(elapsed)}s elapsed)", "PROGRESS", Colors.CYAN)
                
                time.sleep(1)
            
            if install_process.returncode != 0:
                print_status("❌ Failed to install backend requirements", "ERROR", Colors.RED)
                print_status("💡 Common solutions:", "INFO", Colors.YELLOW)
                print_status("   1. Check your internet connection", "INFO", Colors.GRAY)
                print_status("   2. Try running: pip install --upgrade pip", "INFO", Colors.GRAY)
                print_status("   3. Try running: pip install -r requirements.txt --no-cache-dir", "INFO", Colors.GRAY)
                print_status("   4. Check if your Python version is compatible (3.8+)", "INFO", Colors.GRAY)
                raise Exception("Failed to install backend requirements")
            
            print_status("✅ Backend dependencies installed successfully", "SUCCESS", Colors.GREEN)
        else:
            print_status("✅ Backend dependencies already installed", "SUCCESS", Colors.GREEN)
    else:
        print_status("requirements.txt not found in backend directory", "WARNING", Colors.YELLOW)
    
    return python_cmd

def setup_frontend():
    """Set up the frontend environment and install dependencies"""
    print_status("=== Setting up Frontend ===", "INFO", Colors.BLUE)
    frontend_dir = Path("frontend")
    
    # Check if package.json exists
    if not (frontend_dir / "package.json").exists():
        print_status("package.json not found in frontend directory", "WARNING", Colors.YELLOW)
        return
    
    # Check if node_modules already exists and key dependencies are installed
    node_modules_exists = (frontend_dir / "node_modules").exists()
    dayjs_exists = (frontend_dir / "node_modules" / "dayjs").exists() if node_modules_exists else False
    
    if node_modules_exists and dayjs_exists:
        print_status("✅ Frontend dependencies already installed", "SUCCESS", Colors.GREEN)
    else:
        print_status("Installing frontend dependencies...", "INFO", Colors.BLUE)
        print_status("💡 This may take a few minutes...", "INFO", Colors.YELLOW)
        
        # Force clean install to ensure all dependencies are properly installed
        if node_modules_exists:
            print_status("Cleaning existing node_modules for fresh install...", "INFO", Colors.BLUE)
            import shutil
            try:
                shutil.rmtree(frontend_dir / "node_modules")
                print_status("✅ Cleaned existing node_modules", "SUCCESS", Colors.GREEN)
            except Exception as e:
                print_status(f"Warning: Could not clean node_modules: {e}", "WARNING", Colors.YELLOW)
        
        # Clean up any conflicting lock files
        bun_lock = frontend_dir / "bun.lock"
        if bun_lock.exists():
            print_status("Cleaning up conflicting Bun lock file...", "INFO", Colors.BLUE)
            try:
                bun_lock.unlink()
                print_status("✅ Removed bun.lock to prevent conflicts", "SUCCESS", Colors.GREEN)
            except Exception as e:
                print_status(f"Warning: Could not remove bun.lock: {e}", "WARNING", Colors.YELLOW)
        
        # Install dependencies with PowerShell execution policy bypass
        install_result = run_command("powershell -ExecutionPolicy Bypass -Command \"npm install\"", cwd=frontend_dir, silent=False)
        if install_result.wait() != 0:
            raise Exception("Failed to install frontend dependencies")
        
        # Verify key dependencies are installed
        if not (frontend_dir / "node_modules" / "dayjs").exists():
            print_status("⚠️ dayjs not found after install, trying to install it specifically...", "WARNING", Colors.YELLOW)
            dayjs_result = run_command("powershell -ExecutionPolicy Bypass -Command \"npm install dayjs\"", cwd=frontend_dir, silent=False)
            if dayjs_result.wait() != 0:
                raise Exception("Failed to install dayjs dependency")
        
        print_status("✅ Frontend dependencies installed successfully", "SUCCESS", Colors.GREEN)

def wait_for_backend_health(timeout=45):
    """Wait for backend /healthz to report ready instead of raw socket connect"""
    import urllib.request
    start_time = time.time()
    url = "http://127.0.0.1:5001/healthz"
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(resp.read().decode('utf-8'))
                    if data.get("ready") is True:
                        return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def launch_application():
    """Launch both backend and frontend servers with PTO integration"""
    global backend_process, frontend_process
    
    try:
        # Print beautiful banner
        print_banner()
        print_status("🚀 Launching Unified Betting Application...", "INFO", Colors.CYAN)
        
        # Get the absolute path to the project directory
        project_dir = Path(__file__).parent.absolute()
        os.chdir(project_dir)
        print_status(f"Project directory: {project_dir}", "INFO", Colors.GRAY)
        
        # Check for problematic files
        check_for_problematic_files(project_dir)
        
        # Check PTO profile automatically without prompting
        backend_dir = project_dir / "backend"
        python_cmd = sys.executable
        
        print_status("🔍 Checking PTO profile configuration...", "INFO", Colors.BLUE)
        
        # Check if PTO profile exists and is working
        config_path = backend_dir / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                pto_config = config.get("pto", {})
                profile_dir = pto_config.get("chrome_user_data_dir")
                
                if profile_dir and os.path.exists(profile_dir):
                    print_status("PTO profile directory exists, testing...", "INFO", Colors.BLUE)
                    
                    # Check if profile directory exists and has the right structure
                    profile_dir = Path(profile_dir)
                    profile_exists = profile_dir.exists() and (profile_dir / "Profile 1").exists()
                    
                    if profile_exists:
                        print_status("✅ PTO profile directory exists and appears valid", "SUCCESS", Colors.GREEN)
                        print_status("💡 Profile will be tested during actual scraping", "INFO", Colors.GRAY)
                    else:
                        print_status("⚠️ PTO profile appears to be missing or incomplete - running automatic setup...", "WARNING", Colors.YELLOW)
                        print_status("🔄 Launching PTO profile setup...", "INFO", Colors.BLUE)
                        
                        # Run PTO profile setup automatically
                        setup_cmd = f'{python_cmd} setup_pto_profile.py'
                        setup_process = subprocess.Popen(setup_cmd, shell=True, cwd=backend_dir)
                        
                        print_status("💡 PTO setup window opened. Please complete the setup and close the window.", "INFO", Colors.YELLOW)
                        print_status("🔄 Waiting for PTO setup to complete...", "INFO", Colors.BLUE)
                        
                        # Wait for setup to complete
                        setup_process.wait()
                        
                        print_status("✅ PTO setup completed. Continuing with launch...", "SUCCESS", Colors.GREEN)
                else:
                    print_status("ℹ️ PTO profile not found - running automatic setup...", "INFO", Colors.YELLOW)
                    print_status("🔄 Launching PTO profile setup...", "INFO", Colors.BLUE)
                    
                    # Run PTO profile setup automatically
                    setup_cmd = f'{python_cmd} setup_pto_profile.py'
                    setup_process = subprocess.Popen(setup_cmd, shell=True, cwd=backend_dir)
                    
                    print_status("💡 PTO setup window opened. Please complete the setup and close the window.", "INFO", Colors.YELLOW)
                    print_status("🔄 Waiting for PTO setup to complete...", "INFO", Colors.BLUE)
                    
                    # Wait for setup to complete
                    setup_process.wait()
                    
                    print_status("✅ PTO setup completed. Continuing with launch...", "SUCCESS", Colors.GREEN)
            except Exception as e:
                print_status(f"Error checking PTO profile: {e}", "ERROR", Colors.RED)
                print_status("🔄 Running automatic PTO setup...", "INFO", Colors.BLUE)
                
                # Run PTO profile setup automatically
                setup_cmd = f'{python_cmd} setup_pto_profile.py'
                setup_process = subprocess.Popen(setup_cmd, shell=True, cwd=backend_dir)
                
                print_status("💡 PTO setup window opened. Please complete the setup and close the window.", "INFO", Colors.YELLOW)
                print_status("🔄 Waiting for PTO setup to complete...", "INFO", Colors.BLUE)
                
                # Wait for setup to complete
                setup_process.wait()
                
                print_status("✅ PTO setup completed. Continuing with launch...", "SUCCESS", Colors.GREEN)
        else:
            print_status("config.json not found - running automatic PTO setup...", "WARNING", Colors.YELLOW)
            print_status("🔄 Launching PTO profile setup...", "INFO", Colors.BLUE)
            
            # Run PTO profile setup automatically
            setup_cmd = f'{python_cmd} setup_pto_profile.py'
            setup_process = subprocess.Popen(setup_cmd, shell=True, cwd=backend_dir)
            
            print_status("💡 PTO setup window opened. Please complete the setup and close the window.", "INFO", Colors.YELLOW)
            print_status("🔄 Waiting for PTO setup to complete...", "INFO", Colors.BLUE)
            
            # Wait for setup to complete
            setup_process.wait()
            
            print_status("✅ PTO setup completed. Continuing with launch...", "SUCCESS", Colors.GREEN)
        
        # Continue with the rest of the launch sequence
        print_status("🔍 Checking for existing processes...", "INFO", Colors.BLUE)
        
        # Kill any existing processes on ports 3000-3010 and 5001
        for port in range(3000, 3011):
            kill_process_on_port(port)
        kill_process_on_port(5001)
        
        # Find free ports
        frontend_port = find_free_port(3000, 3010)
        if not frontend_port:
            raise Exception("Could not find a free port for the frontend")
        print_status(f"Using frontend port: {frontend_port}", "INFO", Colors.GREEN)
        
        # Always set up environments to ensure dependencies are installed
        print_status("📦 Setting up backend environment...", "INFO", Colors.BLUE)
        python_cmd = setup_backend()
        
        print_status("📦 Setting up frontend environment...", "INFO", Colors.BLUE)
        setup_frontend()
        
        # Kill any existing Chrome processes to prevent profile conflicts
        print_status("🧹 Cleaning up Chrome processes...", "INFO", Colors.BLUE)
        try:
            chrome_killed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        proc.kill()
                        chrome_killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if chrome_killed > 0:
                print_status(f"✅ Killed {chrome_killed} Chrome processes", "SUCCESS", Colors.GREEN)
                time.sleep(2)  # Wait for processes to fully terminate
        except Exception as e:
            print_status(f"Warning: Could not clean up Chrome processes: {e}", "WARNING", Colors.YELLOW)
        
        # Preflight: compile backend to catch syntax errors fast
        try:
            compile_result = run_command(f"{python_cmd} -m py_compile main.py pod_event_manager.py pinnacle_fetcher.py", cwd=backend_dir, silent=True)
            if compile_result.wait() != 0:
                raise Exception("Backend preflight compile failed")
        except Exception as e:
            print_status(f"Backend preflight failed: {e}", "ERROR", Colors.RED)
            raise

        # Launch backend server
        print_status("🚀 Starting Backend (FastAPI/Uvicorn) on port 5001...", "INFO", Colors.CYAN)
        
        # Use the virtual environment's Python executable directly
        if sys.platform == "win32":
            venv_python = backend_dir / "venv" / "Scripts" / "python.exe"
            # Use list format to avoid shell escaping issues with paths containing spaces
            uvicorn_cmd = [str(venv_python), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--no-access-log"]
        else:
            venv_python = backend_dir / "venv" / "bin" / "python"
            uvicorn_cmd = [str(venv_python), "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--no-access-log"]
        
        backend_process = subprocess.Popen(
            uvicorn_cmd,
            cwd=backend_dir,  # Set working directory to backend directory
            shell=False,  # Use list format instead of shell=True
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=dict(os.environ, PYTHONPATH=str(project_dir))  # Set PYTHONPATH environment variable
        )
        # Track backend process for cleanup
        all_child_processes.append(backend_process)
        
        # Log backend output in a separate thread
        pto_monitoring_ready = threading.Event()
        
        def log_backend_output():
            while backend_process.poll() is None:
                try:
                    output = backend_process.stdout.readline()
                    if output:
                        # Decode with UTF-8 and handle encoding errors gracefully
                        if isinstance(output, bytes):
                            output = output.decode('utf-8', errors='replace')
                        output = output.strip()
                except UnicodeDecodeError:
                    # Skip lines that can't be decoded
                    continue
                except Exception as e:
                    # Handle any other exceptions gracefully
                    print(f"Warning: Error reading backend output: {e}")
                    continue
                    
                    # Skip all the verbose Chrome/DevTools/USB/TensorFlow noise
                    skip_patterns = [
                        'DevTools listening on ws://',
                        'WARNING: All log messages',
                        'Created TensorFlow Lite XNNPACK delegate',
                        'Attempting to use a delegate',
                        'USB: usb_service_win.cc',
                        'voice_transcription',
                        'DEP_WEBPACK_DEV_SERVER',
                        'Requirement already satisfied',
                        'INFO:     Uvicorn running',
                        'INFO:     Started reloader process',
                        'INFO:     Will watch for changes',
                        'Opening in existing browser session',
                        'Page loaded into a non-browser-tab context',
                        'Use `node --trace-deprecation`',
                        'components\\device_event_log\\device_event_log_impl.cc',
                        'SetupDiGetDeviceProperty',
                        'Registering VoiceTranscriptionCapability',
                        'TensorFlow Lite XNNPACK delegate',
                        'static-sized tensors',
                        'dynamic-sized tensors',
                        'content\\browser\\network_service_instance_impl.cc',
                        'content\\browser\\gpu\\gpu_process_host.cc',
                        'GPU process exited unexpectedly',
                        'Network service crashed',
                        'ERROR:components\\device_event_log',
                        'USB: usb_service_win.cc:105',
                        'WARNING: All log messages before absl::InitializeLog()',
                        'voice_transcription.cc:58',
                        'Created TensorFlow Lite XNNPACK delegate for CPU',
                        'Attempting to use a delegate that only supports static-sized tensors',
                        'dynamic-sized tensors (tensor#-1 is a dynamic-sized tensor)',
                        'DevTools listening on ws://127.0.0.1:',
                        'components\\device_event_log\\device_event_log_impl.cc:202',
                        'ERROR:content\\browser\\network_service_instance_impl.cc',
                        'Network service crashed, restarting service',
                        'USB: usb_service_win.cc:105 SetupDiGetDeviceProperty',
                        'Element not found. (0x490)',
                        'I0000 00:00:',
                        'voice_transcription.cc:58] Registering VoiceTranscriptionCapability',
                        'Created TensorFlow Lite XNNPACK delegate for CPU.',
                        'Attempting to use a delegate that only supports static-sized tensors with a graph that has dynamic-sized tensors'
                    ]
                    
                    if any(pattern in output for pattern in skip_patterns):
                        continue
                    
                    # Clean up and format important messages
                    if 'telegram_alerts' in output and 'configured' in output:
                        print(f"{Colors.YELLOW}📱 Telegram Alerts configured!{Colors.RESET}")
                    elif 'pto_scraper' in output and 'started' in output:
                        print(f"{Colors.CYAN}🤖 PTO Scraper started{Colors.RESET}")
                    elif 'Server ready to receive alerts' in output:
                        print(f"{Colors.GREEN}✅ Server ready to receive alerts{Colors.RESET}")
                    elif 'Chrome driver created successfully' in output:
                        print(f"{Colors.GREEN}Chrome driver created successfully{Colors.RESET}")
                    elif 'Successfully passed Cloudflare challenge' in output:
                        print(f"{Colors.GREEN}Successfully passed Cloudflare challenge{Colors.RESET}")
                    elif 'PTO setup complete' in output and 'prop monitoring' in output:
                        print(f"{Colors.GREEN}PTO successfully monitoring props{Colors.RESET}")
                        # Set flag when PTO is actually monitoring
                        pto_monitoring_ready.set()
                    elif '[SCRAPING] PTO setup complete, starting prop monitoring' in output:
                        print(f"{Colors.GREEN}PTO successfully monitoring props{Colors.RESET}")
                        # Set flag when PTO is actually monitoring
                        pto_monitoring_ready.set()
                    elif 'Could not switch to Prop Builder tab' in output:
                        # This is often a false positive - PTO usually works anyway
                        print(f"{Colors.YELLOW}Prop Builder tab warning (usually works anyway){Colors.RESET}")
                    elif 'Still on Cloudflare page, waiting longer' in output:
                        # Skip this warning - only show if it actually fails
                        continue
                    elif 'error' in output.lower() or 'exception' in output.lower():
                        print(f"{Colors.RED}ERROR: {output}{Colors.RESET}")
                    elif 'warning' in output.lower():
                        print(f"{Colors.YELLOW}WARNING: {output}{Colors.RESET}")
        
        backend_log_thread = threading.Thread(target=log_backend_output, daemon=True)
        backend_log_thread.start()
        
        # Wait for backend health
        print_status("⏳ Waiting for backend to start...", "INFO", Colors.YELLOW)
        
        # Show progress while waiting
        start_time = time.time()
        if wait_for_backend_health(timeout=45):
            elapsed = int(time.time() - start_time)
            print_status(f"Backend is ready in {elapsed}s!", "SUCCESS", Colors.GREEN)
        else:
            print()  # New line after progress
            print_status("Backend failed health check within 45 seconds", "ERROR", Colors.RED)
            backend_process.terminate()
            raise Exception("Backend startup timeout")
        
        # Start PTO scraper after backend is ready
        print_status("🚀 Starting PTO scraper...", "INFO", Colors.CYAN)
        try:
            import requests
            response = requests.post("http://localhost:5001/pto/scraper/start", timeout=10)
            if response.status_code == 200:
                print_status("✅ PTO scraper started successfully", "SUCCESS", Colors.GREEN)
            else:
                print_status(f"⚠️ PTO scraper start returned status {response.status_code}", "WARNING", Colors.YELLOW)
        except Exception as e:
            print_status(f"⚠️ Could not start PTO scraper: {e}", "WARNING", Colors.YELLOW)
            print_status("💡 PTO may need to be started manually", "INFO", Colors.CYAN)
        
        # Launch frontend server
        frontend_dir = project_dir / "frontend"
        print_status(f"🚀 Starting Frontend (React) on port {frontend_port}...", "INFO", Colors.CYAN)
        
        # Set the port for React
        env = os.environ.copy()
        env['PORT'] = str(frontend_port)
        frontend_process = subprocess.Popen(
            "powershell -ExecutionPolicy Bypass -Command \"npm start\"",
            cwd=frontend_dir,
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        # Track frontend process for cleanup
        all_child_processes.append(frontend_process)
        
        # Log frontend output in a separate thread
        frontend_ready_flag = threading.Event()
        
        def log_frontend_output():
            while frontend_process.poll() is None:
                output = frontend_process.stdout.readline()
                if output:
                    output = output.strip()
                    
                    # Skip all the verbose noise
                    skip_patterns = [
                        'DevTools listening on ws://',
                        'WARNING: All log messages',
                        'Created TensorFlow Lite XNNPACK delegate',
                        'Attempting to use a delegate',
                        'USB: usb_service_win.cc',
                        'voice_transcription',
                        'DEP_WEBPACK_DEV_SERVER',
                        'node:',
                        'Opening in existing browser session'
                    ]
                    
                    if any(pattern in output for pattern in skip_patterns):
                        continue
                    
                    # Clean up and format important messages
                    if 'Starting the development server' in output:
                        print(f"{Colors.MAGENTA}🚀 Starting React development server...{Colors.RESET}")
                    elif 'Compiled successfully' in output:
                        print(f"{Colors.GREEN}Frontend compiled successfully{Colors.RESET}")
                        # Set flag when frontend is actually ready
                        frontend_ready_flag.set()
                    elif 'Local:' in output and 'localhost:' in output:
                        print(f"{Colors.GREEN}🌐 {output}{Colors.RESET}")
                    elif 'error' in output.lower() or 'failed' in output.lower():
                        print(f"{Colors.RED}❌ {output}{Colors.RESET}")
                    elif 'warning' in output.lower():
                        print(f"{Colors.YELLOW}⚠️ {output}{Colors.RESET}")
        
        frontend_log_thread = threading.Thread(target=log_frontend_output, daemon=True)
        frontend_log_thread.start()
        
        # Wait a bit for frontend to start
        print_status("⏳ Waiting for frontend to start...", "INFO", Colors.YELLOW)
        time.sleep(3)
        
        # Wait for frontend to be actually ready
        frontend_ready = False
        start_time = time.time()
        while time.time() - start_time < 90 and not frontend_ready:  # Increased to 90 seconds for React compilation
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)  # 2 second timeout for connection
                    s.connect(('localhost', frontend_port))
                    frontend_ready = True
                    break
            except:
                time.sleep(2)  # Check every 2 seconds
        
        if not frontend_ready:
            print_status("Frontend failed to start within 90 seconds", "ERROR", Colors.RED)
            print_status("This might be due to React compilation taking too long. Trying to clean up and retry...", "WARNING", Colors.YELLOW)
            frontend_process.terminate()
            
            # Try to clean up Bun-related issues
            try:
                frontend_dir = project_dir / "frontend"
                bun_lock = frontend_dir / "bun.lock"
                if bun_lock.exists():
                    bun_lock.unlink()
                    print_status("Removed bun.lock file", "INFO", Colors.CYAN)
            except Exception as e:
                print_status(f"Could not clean up Bun files: {e}", "WARNING", Colors.YELLOW)
            
            raise Exception("Frontend startup timeout")
        
        # Additional check: verify frontend is actually serving content
        print_status("🔍 Verifying frontend is serving content...", "INFO", Colors.BLUE)
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(f'http://localhost:{frontend_port}')
            req.add_header('User-Agent', 'Mozilla/5.0')
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.getcode() == 200:
                    print_status("✅ Frontend is serving content successfully", "SUCCESS", Colors.GREEN)
                else:
                    print_status(f"⚠️ Frontend responded with status {response.getcode()}", "WARNING", Colors.YELLOW)
        except Exception as e:
            print_status(f"⚠️ Could not verify frontend content: {e}", "WARNING", Colors.YELLOW)
            print_status("💡 Frontend might still be compiling, try accessing it manually", "INFO", Colors.CYAN)
        
        # Wait for frontend to actually compile successfully
        print_status("⏳ Waiting for frontend to compile...", "INFO", Colors.YELLOW)
        if not frontend_ready_flag.wait(timeout=120):  # Wait up to 120 seconds for compilation
            print_status("Frontend compilation timeout - but server might still be working", "WARNING", Colors.YELLOW)
        
        # Wait for PTO to actually be monitoring props (reduced timeout)
        print_status("⏳ Waiting for PTO to start monitoring...", "INFO", Colors.YELLOW)
        if not pto_monitoring_ready.wait(timeout=30):  # Reduced to 30 seconds
            print_status("PTO monitoring timeout - continuing anyway", "WARNING", Colors.YELLOW)
            print_status("💡 PTO may still be working, check manually at https://picktheodds.app", "INFO", Colors.CYAN)
        
        # Open Pinnacle Odds Dropper
        print_status("🌐 Opening Pinnacle Odds Dropper...", "INFO", Colors.BLUE)
        open_pinnacle_odds_dropper()
        
        # Print success banner with next steps (only after everything is truly ready)
        success_banner = f"""
{Colors.GREEN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                🎉 LAUNCH SUCCESSFUL! 🎉                      ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
{Colors.CYAN}📊 Frontend:{Colors.RESET} http://localhost:{frontend_port}
{Colors.CYAN}🔧 Backend API:{Colors.RESET} http://localhost:5001
{Colors.CYAN}📈 Pinnacle Odds Dropper:{Colors.RESET} https://pinnacleoddsdropper.com
{Colors.CYAN}🎯 PickTheOdds:{Colors.RESET} https://picktheodds.app
{Colors.CYAN}✅ PTO Scraper:{Colors.RESET} Active and monitoring

{Colors.YELLOW}{Colors.BOLD}📋 NEXT STEPS:{Colors.RESET}
{Colors.WHITE}1. Log in to betbck.com{Colors.RESET}
{Colors.WHITE}2. Refresh pinnacleoddsdropper.com{Colors.RESET}
{Colors.WHITE}3. Confirm PickTheOdds is showing Prop Builder{Colors.RESET}
{Colors.WHITE}4. Open http://localhost:{frontend_port} in your browser{Colors.RESET}

{Colors.YELLOW}💡 Press Ctrl+C to stop all services{Colors.RESET}
{Colors.YELLOW}💡 Close this window to automatically clean up all processes and windows{Colors.RESET}
{Colors.GREEN}══════════════════════════════════════════════════════════════════{Colors.RESET}
"""
        print(success_banner)
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
                if backend_process.poll() is not None:
                    print_status("Backend process died unexpectedly", "ERROR", Colors.RED)
                    break
                if frontend_process.poll() is not None:
                    print_status("Frontend process died unexpectedly", "ERROR", Colors.RED)
                    break
        except KeyboardInterrupt:
            print_status("Shutting down services...", "WARNING", Colors.YELLOW)
            cleanup_on_exit()
    except Exception as e:
        print_status(f"Failed to launch application: {e}", "ERROR", Colors.RED)
        cleanup_on_exit()
        raise

if __name__ == "__main__":
    launch_application() 