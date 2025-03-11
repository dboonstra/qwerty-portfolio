import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .util import option_type, option_expires_at, option_underyling


@dataclass
class Asset:
    """
    Represents a single leg of a transaction.
    """
    symbol: str
    quantity: int
    price: float 
    chainid: int = field(default=0)
    asset_type: str = field(default=None)  # S, C, or P
    multiplier: float = field(default=None)
    action: str = field(default=None)
    roll_count: int = field(default=0)
    average_open_price: float = field(default=0.0)
    # option specific
    underlying_symbol: str = field(default=None)
    days_to_expiration: int = field(default=None)
    expires_at: Optional[datetime.datetime] = field(default=None)
    delta: float = field(default=0.0)
    gamma: float = field(default=0.0)
    theta: float = field(default=0.0)
    quote_date: datetime.datetime = field(default=None)

    EXPECTED_COLUMNS = [
        "symbol",
        "asset_type",
        "quantity",
        "price",
        "underlying_symbol",
        "action",
        "multiplier",
        "timestamp",
        "days_to_expiration",
        "expires_at",
        "delta",
        "gamma",
        "theta",
        "quote_date",
        "chainid",
        "roll_count",
        "average_open_price",
    ]
    df: Optional[pd.DataFrame] = None
    # incrementor for order chains
    _next_chainid: ClassVar[int] = 1

    def __init__(self, **kwargs): 
        # Initialize with known fields only        
        valid_kwargs = {}
        # for field_name in self.__dataclass_fields__:
        for field_name in Asset.EXPECTED_COLUMNS:
            if field_name in kwargs:
                valid_kwargs[field_name] = kwargs[field_name]
        super().__init__(**valid_kwargs)
   
    def __post_init__(self):
        """
        Initializes derived attributes based on the symbol.
        """
      
        isoption = len(self.symbol) > 12

        # setup defaults
        if isoption:
            if self.asset_type is None: self.asset_type = option_type(self.symbol)
            if self.expires_at is None: self.expires_at = option_expires_at(self.symbol)
            if self.underlying_symbol is None: self.underlying_symbol = option_underyling(self.symbol)
            if self.multiplier is None: self.multiplier = 100.0
        else:
            if self.asset_type is None: self.asset_type = 'S'
            if self.underlying_symbol is None: self.underlying_symbol = self.symbol
            if self.multiplier is None: self.multiplier = 1.0

        if self.chainid == 0:  # new chainid 
            self.chainid = self._next_chainid
            self.__class__._next_chainid += 1

        df = pd.DataFrame(vars(self), index=[0])
        # ensure all columns are here
        df = df.reindex(columns = Asset.EXPECTED_COLUMNS)
        df = df[Asset.EXPECTED_COLUMNS] # correct order
        # df_legs.fillna({'action':'bto', 'asset_type':'S'}, inplace=True) # defaults
        self.df = df


    def serialize(self, for_json: bool = False) -> dict:
        """Serializes a Holding object to a dictionary."""
        h = self.df.to_dict()
        if for_json: # convert datetime to iso string
            if h['expires_at'] is not None:
                h['expires_at'] = h['expires_at'].isoformat()
        return h



@dataclass
class Holding(Asset):
    """
    Represents a single asset holding (stock or option).
    """
