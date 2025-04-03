import jdatetime
from datetime import datetime
import locale

def convert_to_jalali(gregorian_date):
    """
    Convert a Gregorian date to Jalali (Shamsi) date.
    
    Args:
        gregorian_date (datetime.datetime): Gregorian date to convert
        
    Returns:
        jdatetime.datetime: Jalali (Shamsi) date
    """
    if isinstance(gregorian_date, str):
        try:
            gregorian_date = datetime.strptime(gregorian_date, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            try:
                gregorian_date = datetime.strptime(gregorian_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                gregorian_date = datetime.now()
    
    return jdatetime.datetime.fromgregorian(datetime=gregorian_date)

def convert_to_gregorian(jalali_date):
    """
    Convert a Jalali (Shamsi) date to Gregorian date.
    
    Args:
        jalali_date (jdatetime.datetime): Jalali date to convert
        
    Returns:
        datetime.datetime: Gregorian date
    """
    return jalali_date.togregorian()

def format_number(number):
    """
    Format a number with thousands separator.
    
    Args:
        number (float): Number to format
        
    Returns:
        str: Formatted number
    """
    if number is None:
        return "0"
        
    try:
        # Format with commas as thousands separator
        return f"{int(number):,}"
    except (ValueError, TypeError):
        return str(number)

def get_persian_month_name(month_number):
    """
    Get Persian month name from month number.
    
    Args:
        month_number (int): Month number (1-12)
        
    Returns:
        str: Persian month name
    """
    persian_months = {
        1: "فروردین",
        2: "اردیبهشت",
        3: "خرداد",
        4: "تیر",
        5: "مرداد",
        6: "شهریور",
        7: "مهر",
        8: "آبان",
        9: "آذر",
        10: "دی",
        11: "بهمن",
        12: "اسفند"
    }
    
    return persian_months.get(month_number, "")

def format_jalali_date(jalali_date):
    """
    Format a Jalali date as a string.
    
    Args:
        jalali_date (jdatetime.datetime): Jalali date to format
        
    Returns:
        str: Formatted date string
    """
    month_name = get_persian_month_name(jalali_date.month)
    return f"{jalali_date.day} {month_name} {jalali_date.year}"
