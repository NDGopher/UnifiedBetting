from pydantic_settings import BaseSettings
from typing import Optional
import os
import logging
import logging.handlers
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def setup_logging():
    """Configure logging for the application"""
    from pathlib import Path
    import sys
    import tempfile

    # Create logs directory in temp folder to avoid OneDrive sync issues
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        # Test if we can actually write to the directory
        test_file = logs_dir / "test_write.tmp"
        test_file.write_text("test", encoding='utf-8')
        test_file.unlink()  # Clean up test file
    except (OSError, PermissionError):
        # Fallback to temp directory if OneDrive sync issues or permission problems
        logs_dir = Path(tempfile.gettempdir()) / "unified_betting_logs"
        logs_dir.mkdir(exist_ok=True)
        print(f"Using temporary log directory: {logs_dir}")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (INFO level) with Unicode-safe encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Set encoding for console handler to handle Unicode characters
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass  # Fallback if reconfigure not available
    
    root_logger.addHandler(console_handler)

    # File handler for all logs (DEBUG level)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Ensure UTF-8 encoding for log files
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        print(f"✅ Logging to: {logs_dir / 'app.log'}")
    except (OSError, PermissionError) as e:
        print(f"⚠️  Warning: Could not create file log handler: {e}")
        print("📝 Logging to console only")

    # SUPPRESS Selenium verbose logging that's causing HTML spam
    selenium_logger = logging.getLogger("selenium")
    selenium_logger.setLevel(logging.WARNING)  # Only show warnings and errors

    # Suppress urllib3 verbose logging
    urllib3_logger = logging.getLogger("urllib3")
    urllib3_logger.setLevel(logging.WARNING)

    # Suppress requests verbose logging
    requests_logger = logging.getLogger("requests")
    requests_logger.setLevel(logging.WARNING)

    # Suppress websocket verbose logging
    websocket_logger = logging.getLogger("websocket")
    websocket_logger.setLevel(logging.WARNING)

    # Suppress asyncio verbose logging
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.WARNING)

    # Special handler for matching logs
    try:
        matching_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "matching.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )
        matching_handler.setLevel(logging.INFO)
        matching_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        matching_handler.setFormatter(matching_formatter)

        # Create matching logger — INFO level prevents O(n*m) debug spam (~100K writes/run)
        matching_logger = logging.getLogger("matching")
        matching_logger.setLevel(logging.INFO)
        matching_logger.addHandler(matching_handler)
        matching_logger.propagate = False  # Don't propagate to root logger
    except (OSError, PermissionError):
        print("⚠️  Warning: Could not create matching log file")

    # Special handler for buckeye scraper logs
    try:
        buckeye_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "buckeye.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )
        buckeye_handler.setLevel(logging.DEBUG)
        buckeye_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        buckeye_handler.setFormatter(buckeye_formatter)

        # Create buckeye logger
        buckeye_logger = logging.getLogger("buckeye")
        buckeye_logger.setLevel(logging.DEBUG)
        buckeye_logger.addHandler(buckeye_handler)
        buckeye_logger.propagate = False  # Don't propagate to root logger
    except (OSError, PermissionError):
        print("⚠️  Warning: Could not create buckeye log file")

    logging.info("Logging configuration initialized")

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Unified Betting App"
    DEBUG: bool = True
    VERSION: str = "0.1.0"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # POD Service settings
    POD_REFRESH_INTERVAL: int = 1800  # 30 minutes
    POD_SESSION_TIMEOUT: int = 3600   # 1 hour
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./betting_app.db"
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # CORS settings
    CORS_ORIGINS: list = ["http://localhost:3000"]  # Frontend URL
    
    # Chrome profile settings for PTO scraper
    chrome_user_data_dir: str = os.getenv("CHROME_USER_DATA_DIR", "./pto_chrome_profile")
    chrome_profile_dir: str = os.getenv("CHROME_PROFILE_DIR", "Profile 1")
    
    class Config:
        env_file = ".env"

# Create settings instance
settings = Settings()

# Setup logging when config is imported
setup_logging() 