#!/usr/bin/env python3
"""
Unified Betting App - Dependency Setup Script
Automatically sets up all required dependencies for both backend and frontend.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import time

def print_status(message, status="INFO"):
    """Print a formatted status message"""
    timestamp = time.strftime("%H:%M:%S")
    status_icons = {
        "INFO": "[INFO]",
        "SUCCESS": "[OK]", 
        "WARNING": "[WARN]",
        "ERROR": "[ERROR]",
        "PROGRESS": "[...]"
    }
    icon = status_icons.get(status, "[INFO]")
    print(f"[{timestamp}] {icon} {message}")

def run_command(command, cwd=None, check=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            timeout=300
        )
        if check and result.returncode != 0:
            print_status(f"Command failed: {command}", "ERROR")
            print_status(f"Error: {result.stderr}", "ERROR")
            return False
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print_status(f"Command timed out: {command}", "ERROR")
        return False
    except Exception as e:
        print_status(f"Command error: {e}", "ERROR")
        return False

def setup_backend():
    """Set up backend dependencies"""
    print_status("=== Setting up Backend ===", "INFO")
    backend_dir = Path("backend")
    
    if not backend_dir.exists():
        print_status("Backend directory not found!", "ERROR")
        return False
    
    # Remove and recreate virtual environment if it's missing or broken
    venv_path = backend_dir / "venv"
    recreate_venv = False
    python_exe = None
    if not venv_path.exists():
        recreate_venv = True
        print_status("Virtual environment does not exist. Will create a new one.", "INFO")
    else:
        # Check if venv is broken (missing python executable)
        if platform.system() == "Windows":
            python_exe = venv_path / "Scripts" / "python.exe"
        else:
            python_exe = venv_path / "bin" / "python"
        print_status(f"Checking venv Python executable: {python_exe}", "INFO")
        if not python_exe.exists():
            print_status(f"Virtual environment is broken or references missing Python: {python_exe}", "WARNING")
            recreate_venv = True
        else:
            # Try to run the venv python and check version
            try:
                result = subprocess.run([str(python_exe), "--version"], capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    print_status(f"Venv python failed to run: {result.stderr}", "WARNING")
                    recreate_venv = True
                else:
                    print_status(f"Venv python version: {result.stdout.strip()}", "INFO")
            except Exception as e:
                print_status(f"Error running venv python: {e}", "WARNING")
                recreate_venv = True
    if recreate_venv:
        print_status("Deleting and recreating virtual environment...", "INFO")
        if venv_path.exists():
            import shutil
            shutil.rmtree(venv_path)
        # Print system python path
        sys_python = sys.executable
        print_status(f"System Python being used to create venv: {sys_python}", "INFO")
        if not run_command("python -m venv venv", cwd=backend_dir):
            print_status("Failed to create virtual environment", "ERROR")
            return False
        print_status("Virtual environment created successfully", "SUCCESS")
    else:
        print_status("Virtual environment already exists and is valid", "SUCCESS")
    
    # Determine Python command based on platform
    if platform.system() == "Windows":
        python_cmd = "venv\\Scripts\\python"
        pip_cmd = "venv\\Scripts\\pip"
    else:
        python_cmd = "venv/bin/python"
        pip_cmd = "venv/bin/pip"
    print_status(f"Using venv python: {python_cmd}", "INFO")
    
    # Check if requirements.txt exists
    requirements_file = backend_dir / "requirements.txt"
    if not requirements_file.exists():
        print_status("requirements.txt not found in backend directory", "WARNING")
        return True
    
    # Always try to upgrade pip
    print_status("Upgrading pip...", "INFO")
    run_command(f"{python_cmd} -m pip install --upgrade pip", cwd=backend_dir, check=False)
    
    # Always force reinstall requirements
    print_status("Installing backend dependencies (force reinstall)...", "INFO")
    if not run_command(f"{python_cmd} -m pip install --upgrade --force-reinstall -r requirements.txt", cwd=backend_dir):
        print_status("Failed to install backend requirements", "ERROR")
        print_status("Try running: pip install -r requirements.txt --no-cache-dir", "INFO")
        return False
    print_status("Backend dependencies installed successfully", "SUCCESS")
    return True

def setup_frontend():
    """Set up frontend dependencies"""
    print_status("=== Setting up Frontend ===", "INFO")
    frontend_dir = Path("frontend")
    
    if not frontend_dir.exists():
        print_status("Frontend directory not found!", "ERROR")
        return False
    
    # Check if package.json exists
    if not (frontend_dir / "package.json").exists():
        print_status("package.json not found in frontend directory", "WARNING")
        return True
    
    # Always remove node_modules for a clean install
    node_modules_path = frontend_dir / "node_modules"
    if node_modules_path.exists():
        print_status("Cleaning existing node_modules for fresh install...", "INFO")
        import shutil
        try:
            shutil.rmtree(node_modules_path)
            print_status("Cleaned existing node_modules", "SUCCESS")
        except Exception as e:
            print_status(f"Warning: Could not clean node_modules: {e}", "WARNING")
    
    # Clean up any conflicting lock files
    bun_lock = frontend_dir / "bun.lock"
    if bun_lock.exists():
        print_status("Cleaning up conflicting Bun lock file...", "INFO")
        try:
            bun_lock.unlink()
            print_status("Removed bun.lock to prevent conflicts", "SUCCESS")
        except Exception as e:
            print_status(f"Warning: Could not remove bun.lock: {e}", "WARNING")
    
    # Check if npm is available - try multiple methods for Windows (especially after fresh install)
    npm_found = False
    npm_version = None
    npm_cmd = "npm"
    
    # First try standard check with shell=True for Windows PATH resolution
    try:
        npm_check = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=10, shell=True)
        if npm_check.returncode == 0:
            npm_found = True
            npm_version = npm_check.stdout.strip()
    except FileNotFoundError:
        pass
    
    # If not found, try common Node.js install paths on Windows (for fresh installs)
    if not npm_found and platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\nodejs\npm.cmd",
            r"C:\Program Files (x86)\nodejs\npm.cmd",
            os.path.expanduser(r"~\AppData\Roaming\npm\npm.cmd"),
        ]
        for npm_path in common_paths:
            if os.path.exists(npm_path):
                try:
                    npm_check = subprocess.run([npm_path, "--version"], capture_output=True, text=True, timeout=10)
                    if npm_check.returncode == 0:
                        npm_found = True
                        npm_version = npm_check.stdout.strip()
                        npm_cmd = npm_path
                        print_status(f"Found npm at: {npm_path}", "INFO")
                        break
                except Exception:
                    continue
    
    if not npm_found:
        print_status("npm not found! Please install Node.js from https://nodejs.org", "ERROR")
        print_status("After installing Node.js, close ALL terminal windows and open a new one, then run this script again", "INFO")
        print_status("You can manually install frontend deps later by running: cd frontend && npm install", "INFO")
        return False
    
    print_status(f"Found npm version: {npm_version}", "INFO")
    
    # Always run npm install using the found npm command
    # If we found npm via full path, ensure Node.js directory is in PATH for postinstall scripts
    env = None
    if os.path.exists(npm_cmd):
        nodejs_dir = os.path.dirname(npm_cmd)
        current_path = os.environ.get('PATH', '')
        if nodejs_dir not in current_path:
            env = os.environ.copy()
            env['PATH'] = f"{nodejs_dir};{current_path}"
            print_status(f"Adding Node.js directory to PATH: {nodejs_dir}", "INFO")
    
    print_status("Installing frontend dependencies (npm install)...", "INFO")
    npm_install_cmd = f'"{npm_cmd}" install' if '"' in npm_cmd or os.path.exists(npm_cmd) else f"{npm_cmd} install"
    
    # Override run_command to pass env if needed
    if env:
        try:
            result = subprocess.run(
                npm_install_cmd,
                shell=True,
                cwd=frontend_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode != 0:
                print_status(f"Command failed: {npm_install_cmd}", "ERROR")
                if result.stderr:
                    print(result.stderr[-1000:])  # Last 1000 chars of error
                install_success = False
            else:
                install_success = True
        except Exception as e:
            print_status(f"Command error: {e}", "ERROR")
            install_success = False
    else:
        install_success = run_command(npm_install_cmd, cwd=frontend_dir)
    
    if not install_success:
        print_status("Failed to install frontend dependencies with standard install", "WARNING")
        print_status("Trying with --legacy-peer-deps flag...", "INFO")
        npm_install_cmd_legacy = f'"{npm_cmd}" install --legacy-peer-deps' if '"' in npm_cmd or os.path.exists(npm_cmd) else f"{npm_cmd} install --legacy-peer-deps"
        
        # Try legacy install with env if needed
        if env:
            try:
                result = subprocess.run(
                    npm_install_cmd_legacy,
                    shell=True,
                    cwd=frontend_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                legacy_success = result.returncode == 0
                if not legacy_success and result.stderr:
                    print(result.stderr[-1000:])
            except Exception as e:
                print_status(f"Legacy install error: {e}", "ERROR")
                legacy_success = False
        else:
            legacy_success = run_command(npm_install_cmd_legacy, cwd=frontend_dir)
        
        if not legacy_success:
            print_status("Failed to install frontend dependencies", "ERROR")
            print_status("Try running manually: cd frontend && npm install --legacy-peer-deps", "INFO")
            return False
    print_status("Frontend dependencies installed successfully", "SUCCESS")
    return True

def main():
    """Main setup function"""
    print("Unified Betting App - Dependency Setup")
    print("=" * 50)
    
    # Get the project directory
    project_dir = Path(__file__).parent.absolute()
    os.chdir(project_dir)
    print_status(f"Project directory: {project_dir}", "INFO")
    
    # Set up backend
    backend_success = setup_backend()
    
    # Set up frontend
    frontend_success = setup_frontend()
    
    # Summary
    print("\n" + "=" * 50)
    if backend_success and frontend_success:
        print_status("Setup completed successfully!", "SUCCESS")
        print_status("You can now run 'python launch.py' to start the application", "INFO")
    else:
        print_status("Setup completed with warnings", "WARNING")
        if not backend_success:
            print_status("Backend setup failed - check the errors above", "ERROR")
        if not frontend_success:
            print_status("Frontend setup failed - check the errors above", "ERROR")
        print_status("Try running the setup again or check your system requirements", "INFO")
    
    return backend_success and frontend_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 