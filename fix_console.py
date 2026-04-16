"""
Fix Windows console encoding for Unicode characters
Run this before starting Django server on Windows
"""
import sys
import os

def fix_windows_console():
    """Fix Windows console encoding issues"""
    if sys.platform == 'win32':
        try:
            # Set console code page to UTF-8
            os.system('chcp 65001 > nul')
            
            # Set environment variables
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            os.environ['PYTHONUTF8'] = '1'
            
            print("[SUCCESS] Windows console encoding fixed for Unicode")
            return True
        except Exception as e:
            print(f"[WARNING] Could not fix console encoding: {e}")
            os.environ['DISABLE_UNICODE_LOGS'] = 'True'
            print("[INFO] Unicode logging disabled as fallback")
            return False
    return True

if __name__ == "__main__":
    fix_windows_console()