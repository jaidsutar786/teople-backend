"""
Console utilities for safe Unicode printing on Windows
"""
import sys
import os

def safe_print(*args, **kwargs):
    """
    Safe print function that handles Unicode characters on Windows
    """
    # Check if Unicode logging is disabled
    if os.environ.get('DISABLE_UNICODE_LOGS') == 'True':
        # Convert all args to ASCII-safe versions immediately
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                safe_arg = (str(arg)
                    .replace('✅', '[SUCCESS]')
                    .replace('❌', '[ERROR]')
                    .replace('⚠️', '[WARNING]')
                    .replace('📊', '[DATA]')
                    .replace('📄', '[PDF]')
                    .replace('💰', '[MONEY]')
                    .replace('🔄', '[REFRESH]')
                    .replace('🎫', '[TICKET]')
                    .replace('📅', '[CALENDAR]')
                    .replace('🟢', '[GREEN]')
                    .replace('🔴', '[RED]')
                    .replace('🟠', '[ORANGE]')
                    .replace('📈', '[CHART]')
                    .replace('📋', '[CLIPBOARD]')
                    .replace('👥', '[USERS]')
                    .replace('🔢', '[NUMBERS]')
                    .replace('📝', '[NOTE]')
                    .replace('🧮', '[CALC]')
                    .replace('🔍', '[SEARCH]')
                )
                safe_args.append(safe_arg)
            else:
                safe_args.append(str(arg))
        print(*safe_args, **kwargs)
        return
    
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: replace Unicode characters with ASCII equivalents
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Replace common emojis with text equivalents
                safe_arg = (arg
                    .replace('✅', '[SUCCESS]')
                    .replace('❌', '[ERROR]')
                    .replace('⚠️', '[WARNING]')
                    .replace('📊', '[DATA]')
                    .replace('📄', '[PDF]')
                    .replace('💰', '[MONEY]')
                    .replace('🔄', '[REFRESH]')
                    .replace('🎫', '[TICKET]')
                    .replace('📅', '[CALENDAR]')
                    .replace('🟢', '[GREEN]')
                    .replace('🔴', '[RED]')
                    .replace('🟠', '[ORANGE]')
                    .replace('📈', '[CHART]')
                    .replace('📋', '[CLIPBOARD]')
                    .replace('👥', '[USERS]')
                    .replace('🔢', '[NUMBERS]')
                    .replace('📝', '[NOTE]')
                    .replace('🧮', '[CALC]')
                    .replace('🔍', '[SEARCH]')
                )
                safe_args.append(safe_arg)
            else:
                safe_args.append(str(arg))
        
        print(*safe_args, **kwargs)
    except Exception as e:
        # Ultimate fallback
        print(f"[LOG] Print error: {str(e)}")