from typing import Optional, List, ClassVar
import datetime
import pandas as pd # type: ignore

from .util import option_type, option_expires_at, option_underyling, parse_timestamp


class Asset:
    """
    Represents a single leg of a transaction or an asset in a portfolio.

    This is not a strict dataclass to allow key names to be overriden 
    and fit various import formats.

    symbol, quantity, and price are required fields

    others are generated, a user may add new fields simply 
    by passing them into init
    """
    TIME_STAMP: ClassVar[str|datetime.datetime] = 'time_stamp'
    SYMBOL: ClassVar[str] = 'symbol'
    QUANTITY: ClassVar[str] = 'quantity'
    PRICE: ClassVar[str] = 'price'
    AVERAGE_OPEN_PRICE: ClassVar[str] = 'average_open_price'
    ASSET_TYPE: ClassVar[str] = 'asset_type'
    UNDERLYING_SYMBOL: ClassVar[str] = 'underlying_symbol'
    MULTIPLIER: ClassVar[str] = 'multiplier'
    DAYS_TO_EXPIRATION: ClassVar[str] = 'days_to_expiration'
    EXPIRES_AT: ClassVar[str|datetime.datetime] = 'expires_at'
    DELTA: ClassVar[str] = 'delta'
    GAMMA: ClassVar[str] = 'gamma'
    THETA: ClassVar[str] = 'theta'
    QUOTE_DATE: ClassVar[str|datetime.datetime] = 'quote_date'
    ORDER_TYPE: ClassVar[str] = 'order_type'
    CHAINID: ClassVar[str] = 'chainid'
    ROLL_COUNT: ClassVar[str] = 'roll_count'

    CASH_SYMBOL: ClassVar[str] = '_CASH'
    
    EXPECTED_COLUMNS: ClassVar[List[str]] = [
        SYMBOL,
        QUANTITY,
        PRICE,
        AVERAGE_OPEN_PRICE,
        ASSET_TYPE,
        UNDERLYING_SYMBOL,
        MULTIPLIER,
        DAYS_TO_EXPIRATION,
        EXPIRES_AT,
        DELTA,
        GAMMA,
        THETA,
        QUOTE_DATE,
        ORDER_TYPE,
        CHAINID,
        ROLL_COUNT,
    ]
    # Asset representation will be a dataframe
    df: Optional[pd.DataFrame] = None

    def __init__(self, **fields):        
        for field_name in Asset.EXPECTED_COLUMNS:
            if field_name not in fields:
                fields[field_name] = None
        # symbol, quantity, and price are required fields
        if fields[Asset.SYMBOL] is None:
            raise ValueError(f"ASSET needs symobl reference key {Asset.SYMBOL}")
        if fields[Asset.QUANTITY] is None:
            raise ValueError(f"ASSET needs symobl reference key {Asset.QUANTITY}")
        if fields[Asset.PRICE] is None:
            raise ValueError(f"ASSET needs symobl reference key {Asset.PRICE}")



        # Initializes derived attributes based on the symbol.
        symbol = fields[Asset.SYMBOL]
        isoption = len(symbol) > 12

        # setup defaults
        def default(key,val):
            if fields[key] is None: fields[key] = val

        default(Asset.AVERAGE_OPEN_PRICE, fields[Asset.PRICE])
        default(Asset.CHAINID, 0)
        default(Asset.ROLL_COUNT, 0)
        default(Asset.QUOTE_DATE, datetime.datetime.now())
        if fields[Asset.ORDER_TYPE] is None:
            fields[Asset.ORDER_TYPE] = 'sto' if fields[Asset.QUANTITY] < 0 else 'bto'

        if isoption:
            default(Asset.ASSET_TYPE, option_type(symbol))
            default(Asset.UNDERLYING_SYMBOL, option_underyling(symbol) )
            default(Asset.DAYS_TO_EXPIRATION, option_expires_at(symbol) )
            default(Asset.EXPIRES_AT, option_expires_at(symbol) )
            default(Asset.MULTIPLIER, 100.0)
        else:
            if symbol == Asset.CASH_SYMBOL:
                default(Asset.ASSET_TYPE, 'M')
            else:
                default(Asset.ASSET_TYPE, 'S')
            default(Asset.UNDERLYING_SYMBOL, symbol)
            default(Asset.MULTIPLIER, 1.0)

        # enforce datetime 
        if fields[Asset.QUOTE_DATE] is not None:
            fields[Asset.QUOTE_DATE] = parse_timestamp(fields[Asset.QUOTE_DATE])
        if fields[Asset.EXPIRES_AT] is not None:
            fields[Asset.EXPIRES_AT] = parse_timestamp(fields[Asset.EXPIRES_AT])
            if fields[Asset.DAYS_TO_EXPIRATION] is None:
                fields[Asset.DAYS_TO_EXPIRATION] = (fields[Asset.EXPIRES_AT] - fields[Asset.QUOTE_DATE]).days

        self.df = pd.DataFrame(fields, index=[0])

    def get_attr(self, key):
        if key in self.df.columns:
            return self.df[key].iloc[0]
        return None

    def serialize(self, for_json: bool = False) -> dict:
        """Serializes a Holding object to a dictionary."""
        h = self.df.to_dict(orient='records')[0]
        if for_json: # convert datetime to iso string
            for date_thing in [Asset.TIME_STAMP, Asset.EXPIRES_AT, Asset.QUOTE_DATE]:
                if h[date_thing] is not None:
                    h[date_thing] = h[date_thing].isoformat()
        return h

    def update(self, key, value):
        if key in self.df.columns:
            self.df[key] = value
            return value
        return None
