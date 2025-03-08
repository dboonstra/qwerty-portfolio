import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd  # type: ignore
from collections import defaultdict


DEBUG: bool = True

def debug(*a):
    if DEBUG:
        print(*a, file=sys.stderr)

def warn(*a):
    print(*a, file=sys.stderr)

def flatten_model(var):
    # export pydantic model to json-izable thingy
    vardump = getattr(var, 'model_dump', None)
    if callable(vardump):
        return vardump(mode='json')
    return var

def dump_model(var):
    # to dump a model to stdout 
    print(json.dumps(flatten_model(var), indent=4))

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

