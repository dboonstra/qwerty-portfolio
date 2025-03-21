import datetime
import pandas as pd # type: ignore
from typing import Optional, List, ClassVar

from .exceptions import InvalidSymbolError
from .globals import Gl
from .utils import (
    option_type, 
    option_expires_at, 
    option_underyling, 
    option_strike, 
    parse_timestamp, 
    option_symbol_format_valid
)



class Asset:
    """
    Represents a single leg of a transaction or an asset in a portfolio.

    This is not a strict dataclass to allow key names to be overriden 
    and fit various import formats.

    symbol, quantity, and price are required fields

    others are generated, a user may add new fields simply 
    by passing them into init
    """

    
    EXPECTED_COLUMNS: ClassVar[List[str]] = [
        Gl.SYMBOL,
        Gl.QUANTITY,
        Gl.PRICE,
        Gl.AVERAGE_OPEN_PRICE,
        Gl.ASSET_TYPE,
        Gl.UNDERLYING_SYMBOL,
        Gl.MULTIPLIER,
        Gl.DAYS_TO_EXPIRATION,
        Gl.EXPIRES_AT,
        Gl.STRIKE_PRICE,
        Gl.DELTA,
        Gl.GAMMA,
        Gl.THETA,
        Gl.QUOTE_DATE,
        Gl.ORDER_TYPE,
        Gl.CHAINID,
        Gl.ROLL_COUNT,
    ]
    # Asset representation will be a dataframe
    df: Optional[pd.DataFrame] = None



    def __init__(self, **fields):        
        for field_name in Asset.EXPECTED_COLUMNS:
            if field_name not in fields:
                fields[field_name] = None
        # prefer mark (market price) over price if present ( its personal )
        if 'mark' in fields and fields['mark'] is not None:
            fields[Gl.PRICE] = fields['mark']

        # symbol, quantity, and price are required fields
        if fields[Gl.SYMBOL] is None:
            raise ValueError(f"ASSET needs symobl reference key {Gl.SYMBOL}")
        if fields[Gl.QUANTITY] is None:
            raise ValueError(f"ASSET needs symobl reference key {Gl.QUANTITY}")
        if fields[Gl.PRICE] is None:
            raise ValueError(f"ASSET needs symobl reference key {Gl.PRICE}")



        # Initializes derived attributes based on the symbol.
        symbol = fields[Gl.SYMBOL]
        isoption = len(symbol) > 12

        if isoption and not option_symbol_format_valid(symbol):
          raise InvalidSymbolError("Invalid option symbol format")

        # setup defaults
        def default(key,val):
            if fields[key] is None: fields[key] = val

        default(Gl.AVERAGE_OPEN_PRICE, fields[Gl.PRICE])
        default(Gl.CHAINID, 0)
        default(Gl.ROLL_COUNT, 0)
        default(Gl.QUOTE_DATE, datetime.datetime.now())
        if fields[Gl.ORDER_TYPE] is None:
            fields[Gl.ORDER_TYPE] = Gl.SELL_TO_OPEN if fields[Gl.QUANTITY] < 0 else Gl.BUY_TO_OPEN

        if isoption:
            default(Gl.ASSET_TYPE, option_type(symbol))
            default(Gl.UNDERLYING_SYMBOL, option_underyling(symbol) )
            default(Gl.DAYS_TO_EXPIRATION, option_expires_at(symbol) )
            default(Gl.STRIKE_PRICE, option_strike(symbol) )
            default(Gl.EXPIRES_AT, option_expires_at(symbol) )
            default(Gl.MULTIPLIER, 100.0)
        else:
            if symbol == Gl.CASH_SYMBOL:
                default(Gl.ASSET_TYPE, Gl.MONEY)
            else:
                default(Gl.ASSET_TYPE, Gl.EQUITY)
            default(Gl.UNDERLYING_SYMBOL, symbol)
            default(Gl.MULTIPLIER, 1.0)

        # enforce datetime 
        if fields[Gl.QUOTE_DATE] is not None:
            fields[Gl.QUOTE_DATE] = parse_timestamp(fields[Gl.QUOTE_DATE])
        if fields[Gl.EXPIRES_AT] is not None:
            fields[Gl.EXPIRES_AT] = parse_timestamp(fields[Gl.EXPIRES_AT])
            if fields[Gl.DAYS_TO_EXPIRATION] is None:
                fields[Gl.DAYS_TO_EXPIRATION] = (fields[Gl.EXPIRES_AT] - fields[Gl.QUOTE_DATE]).days

        self.df = pd.DataFrame(fields, index=[0])

    def __repr__(self):
        return f"Asset({self.serialize(for_json=True)})"



    def get_attr(self, key: str):
        if key in self.df.columns:
            return self.df[key].iloc[0]
        return None
    
    def set_attr(self, key: str, val):
        self.df[key] = val

    def copy(self):
        return Asset(**self.serialize())



    def serialize(self, for_json: bool = False) -> dict:
        """Serializes a Holding object to a dictionary."""
        h = self.df.copy().to_dict(orient='records')[0]
        if for_json: # convert datetime to iso string
            for date_thing in [Gl.TIME_STAMP, Gl.EXPIRES_AT, Gl.QUOTE_DATE]:
                if date_thing in h:
                    if h[date_thing] is not None:
                        if hasattr(h[date_thing], 'isoformat'):
                            h[date_thing] = h[date_thing].isoformat()
        return h

