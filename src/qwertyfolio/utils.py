import sys
import datetime
import yfinance as yf
from typing import Optional
import pandas as pd  # type: ignore
from typing import Union
from tabulate import tabulate


def warn(*a):
    print(*a, file=sys.stderr)
    return None

def print_tabulate(df: pd.DataFrame, cols: list[str] = [], title: str = None):
    """ """
    if title is not None: print(f"# {title}")
    if df.empty:
        print("__ No data found in frame __")
    elif len(cols) == 0:
        print(tabulate(df, headers='keys', tablefmt='psql'))
    else:
        print(tabulate(df[cols], headers='keys', tablefmt='psql'))
    print()


def get_quotes(symbols: list[str]) -> dict[str:float]:
    """
    Args:
        symbols (list): list of symbols
    Returns:
        dict: {symbol: price}
    """
    ret: dict = {}
    for sym in symbols:
        if len(sym) > 12:
            # yfinance likes option symbols trimmed
            # e.g. 'SPY   250331C00375000' == 'SPY250331C00375000'
            sym = sym.replace(' ', '')
            sym = sym.replace('-', '')
        tick = yf.Ticker(sym)
        try:
            ret[sym] = tick.info['currentPrice']
        except:
            try:
                b,a = tick.info['bid'], tick.info['ask']
                ret[sym] = (b+a)/2
            except:
                warn(f"get_quotes: fetch failed {sym}")
                continue
    return ret

def option_strike(symbol: str) -> float:
    """
    Extract the strike_price from option symbol.
    """
    if len(symbol) > 20:
        numbers = symbol[13:21]
        return int(numbers)/1000
    return None

def option_type(symbol: str) -> str:
    """
    Extract the C/P type from option symbol.
    """
    if len(symbol) > 12:
        return symbol[12]
    return None

def option_underyling(symbol: str) -> str:
    """
    Extract the underlying symbol from option symbol.
    """
    return symbol[0:6].replace(' ', '')

def option_expires_at(symbol: str) -> Optional[datetime.datetime]:
    """
    Extracts the expiration date from an option symbol.

    Args:
        symbol: The option symbol (e.g., "SPY   250404C00450000").
        Format: {6}{2}{2}{2}[P|C]{8} (underlying{yy}{mm}{dd}[P|C]{strike})

    Returns:
        The expiration date as a datetime object, or None if the symbol is not an option.
    """
    if len(symbol) < 13:  # Minimum length for an option symbol
        return None

    try:
        date_str = symbol[6:12]  # Extract the date part (yymmdd)
        # Optimized date parsing with pd.to_datetime with format specifier
        expiration_date = pd.to_datetime(f"20{date_str} 20:15:00+00:00", format="%Y%m%d %H:%M:%S%z")
        return expiration_date.to_pydatetime()
    except ValueError:
        # Handle cases where the date part is malformed.
        warn(f"Invalid date format in symbol: {symbol}")
        return None

def option_symbol_format_valid(symbol: str) -> bool:
    """ensure option symbol fits standard format"""
    # SPY---250131C00635000
    if len(symbol) != 21:
        return False
    dt = symbol[6:12]
    pt = symbol[12:13]
    at = symbol[13:21]
    if at.isnumeric() and dt.isnumeric() and pt in ['C', 'P']:
        return True 
    return False


def parse_timestamp(timestamp_input: Union[int, str, datetime.date, datetime.datetime]) -> datetime.datetime:
    """
    Parses a timestamp from a string, date, or datetime object and returns a datetime object.

    Args:
        timestamp_input: The timestamp to parse. Can be a string in various formats,
                         a datetime.date object, or a datetime.datetime object.

    Returns:
        A datetime.datetime object representing the parsed timestamp.

    Raises:
        ValueError: If the input string cannot be parsed as a timestamp.
        TypeError: If the input is not a string, datetime.date, or datetime.datetime object.
    """
    if isinstance(timestamp_input, datetime.datetime):
        return timestamp_input
    elif isinstance(timestamp_input, datetime.date):
        return datetime.datetime(timestamp_input.year, timestamp_input.month, timestamp_input.day)
    elif isinstance(timestamp_input, int):
        timestamp_input = str(timestamp_input)

    if isinstance(timestamp_input, str):
        try:
            # Try parsing as an integer (Unix timestamp)
            if timestamp_input.isdigit():
                if len(timestamp_input) == 10:
                    # Seconds
                    return datetime.datetime.fromtimestamp(int(timestamp_input), tz=datetime.timezone.utc)
                elif len(timestamp_input) == 13:
                    # Milliseconds
                    return datetime.datetime.fromtimestamp(int(timestamp_input) / 1000, tz=datetime.timezone.utc)
                else:
                    raise ValueError("Invalid unix timestamp length")

            # Try parsing with dateutil.parser
            # from dateutil.parser import parse # type: ignore
            # return parse(timestamp_input)

            # Try ISO 8601 format
            return datetime.datetime.fromisoformat(timestamp_input)


        except (ValueError, OverflowError):
            try:
                # try some common string formats
                # YYYY/MM/DD or MM/DD/YYYY
                for fmt in ["%Y/%m/%d", "%m/%d/%Y"]:
                    try:
                        return datetime.datetime.strptime(timestamp_input, fmt)
                    except ValueError:
                         pass
                # YYYYMMDD or YYYY-MM-DD
                for fmt in ["%Y%m%d", "%Y-%m-%d"]:
                    try:
                         return datetime.datetime.strptime(timestamp_input, fmt)
                    except ValueError:
                         pass
                
                # Try with HH:MM:SS
                for fmt in ["%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y%m%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        return datetime.datetime.strptime(timestamp_input, fmt)
                    except ValueError:
                         pass

                return warn(f"Could not parse timestamp string: {timestamp_input}")
            except Exception as e:
                return warn(f"Could not parse timestamp string: {timestamp_input}, Error: {e}")
    else:
        return warn(f"Invalid timestamp input type: {type(timestamp_input)}")

