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
class Holding:
    """
    Represents a single asset holding (stock or option).
    """
    symbol: str
    quantity: int
    price: float = field(default=0.0)
    underlying_symbol: str = field(default="")
    average_open_price: float = field(default=0.0)
    expires_at: Optional[datetime.datetime] = field(default=None)
    instrument_type: str = field(default="Equity")
    asset_type: str = field(default="S")  # S, C, or P
    multiplier: float = field(default=1.0)
    chainid: int = field(default=0)
    roll_count: int = field(default=0)
    _next_chainid: ClassVar[int] = 1

    # TODO would _next_chainid be better in Transaction class ?

    def __post_init__(self):
        """
        Initializes derived attributes based on the symbol.
        """
        isoption = len(self.symbol) > 12
        if self.chainid == 0:  # new chainid 
            self.chainid = self._next_chainid
            self.__class__._next_chainid += 1

        if isoption:
            self.asset_type = option_type(self.symbol)
            self.instrument_type = 'Equity Option'
            self.multiplier = 100.0
            self.expires_at = option_expires_at(self.symbol)
            self.underlying_symbol = option_underyling(self.symbol)
        else:
            self.underlying_symbol = self.symbol

        if self.average_open_price == 0.0:
            self.average_open_price = self.price
        if self.price == 0.0:
            self.price = self.average_open_price

    def serialize(self) -> dict:
        """Serializes a Holding object to a dictionary."""
        h = vars(self).copy()
        if h['expires_at'] is not None:
            h['expires_at'] = h['expires_at'].isoformat()
        return h

