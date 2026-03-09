"""
Project Cleanup Script
Removes development clutter and prepares for production release.
Run this once before packaging the project.
"""

import os
import shutil
from pathlib import Path

# Directories to clean
ROOT_DIR = Path(__file__).parent
PROD_SCANNER_DIR = ROOT_DIR / "prod_scanner"

# Files to preserve
PRESERVE_FILES = {
    "main.py",
    "config.py",
    "connectors.py",
    "analyzer.py",
    "utils.py",
    "requirements.txt",
    ".env",
    ".env.example",
    "env_example.txt",
    "README.md",
    "PRODUCTION_SCANNER_GUIDE.md",
    "PRODUCTION_GUIDE.md",
    "COMMERCIAL_GRADE_FEATURES.md",
    "FINAL_UX_POLISH.md",
    "UI_UPGRADE_SUMMARY.md",
    "Start_Scanner.bat",
    "build_exe.py",
    "cleanup_project.py",
}

# Directories to preserve
PRESERVE_DIRS = {
    "logs",
    ".venv",
    "venv",
    "__pycache__",  # Will be deleted, but we'll recreate if needed
}


def delete_file(file_path: Path):
    """Safely delete a file."""
    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            print(f"  ✓ Deleted: {file_path}")
            return True
    except Exception as e:
        print(f"  ✗ Error deleting {file_path}: {e}")
    return False


def delete_directory(dir_path: Path):
    """Safely delete a directory."""
    try:
        if dir_path.exists() and dir_path.is_dir():
            shutil.rmtree(dir_path)
            print(f"  ✓ Deleted directory: {dir_path}")
            return True
    except Exception as e:
        print(f"  ✗ Error deleting {dir_path}: {e}")
    return False


def cleanup_directory(directory: Path, is_root: bool = False):
    """Clean up a directory."""
    deleted_count = 0
    
    print(f"\n📁 Cleaning: {directory}")
    
    if not directory.exists():
        print(f"  ⚠ Directory does not exist: {directory}")
        return deleted_count
    
    # Delete test files
    for pattern in ["test_*.py", "mock_*.py", "*_test.py", "*_mock.py"]:
        for file_path in directory.glob(pattern):
            if file_path.name not in PRESERVE_FILES:
                if delete_file(file_path):
                    deleted_count += 1
    
    # Delete __pycache__ directories
    for pycache in directory.rglob("__pycache__"):
        if pycache.is_dir():
            if delete_directory(pycache):
                deleted_count += 1
    
    # Delete .pyc files
    for pyc_file in directory.rglob("*.pyc"):
        if delete_file(pyc_file):
            deleted_count += 1
    
    # Delete .pyo files
    for pyo_file in directory.rglob("*.pyo"):
        if delete_file(pyo_file):
            deleted_count += 1
    
    # Delete .md files (except preserved ones)
    if is_root:
        for md_file in directory.glob("*.md"):
            if md_file.name not in PRESERVE_FILES:
                if delete_file(md_file):
                    deleted_count += 1
    
    # Delete old CSV logs in root (keep logs/ directory)
    if is_root:
        for csv_file in directory.glob("*.csv"):
            if delete_file(csv_file):
                deleted_count += 1
    
    # Delete temporary Python files
    for temp_file in directory.glob("*.py~"):
        if delete_file(temp_file):
            deleted_count += 1
    
    # Delete .DS_Store (macOS)
    for ds_store in directory.rglob(".DS_Store"):
        if delete_file(ds_store):
            deleted_count += 1
    
    # Delete Thumbs.db (Windows)
    for thumbs in directory.rglob("Thumbs.db"):
        if delete_file(thumbs):
            deleted_count += 1
    
    return deleted_count


def main():
    """Main cleanup function."""
    print("=" * 60)
    print("🧹 PROJECT CLEANUP SCRIPT")
    print("=" * 60)
    print("\nThis script will remove:")
    print("  - Test files (test_*.py, mock_*.py)")
    print("  - __pycache__ directories")
    print("  - Old .md files (except README.md and guides)")
    print("  - Temporary files (.pyc, .pyo, .py~)")
    print("  - Old CSV logs in root")
    print("\nPreserving:")
    print("  - Production code (main.py, config.py, etc.)")
    print("  - requirements.txt")
    print("  - .env files")
    print("  - README.md and production guides")
    print("  - logs/ directory")
    
    response = input("\n⚠️  Continue? (yes/no): ").strip().lower()
    if response not in ["yes", "y"]:
        print("❌ Cleanup cancelled.")
        return
    
    total_deleted = 0
    
    # Clean root directory
    total_deleted += cleanup_directory(ROOT_DIR, is_root=True)
    
    # Clean prod_scanner directory
    total_deleted += cleanup_directory(PROD_SCANNER_DIR, is_root=False)
    
    print("\n" + "=" * 60)
    print(f"✅ CLEANUP COMPLETE")
    print(f"   Deleted {total_deleted} items")
    print("=" * 60)
    print("\n📝 Next steps:")
    print("  1. Review the remaining files")
    print("  2. Test the scanner: python prod_scanner/main.py")
    print("  3. Use Start_Scanner.bat for one-click launch")


if __name__ == "__main__":
    main()

