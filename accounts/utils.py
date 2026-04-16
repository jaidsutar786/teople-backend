from datetime import datetime
import pytz

def get_ist_time():
    """Get current time in IST format"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime('%d-%m-%Y %I:%M %p IST')

def convert_to_ist(utc_datetime):
    """Convert UTC datetime to IST string"""
    if not utc_datetime:
        return None
    ist = pytz.timezone('Asia/Kolkata')
    if utc_datetime.tzinfo is None:
        utc_datetime = pytz.utc.localize(utc_datetime)
    ist_time = utc_datetime.astimezone(ist)
    return ist_time.strftime('%d-%m-%Y %I:%M %p IST')
