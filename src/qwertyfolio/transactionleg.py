import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .util import option_type, option_underyling


@dataclass
class TransactionLeg:
    """
    Represents a single leg of a transaction.
    """
    symbol: str
    quantity: int
    price: float
    action: str  # bto, sto, btc, stc, deposit
    asset_type: str = field(default="S")  # S, C, or P
    instrument_type: str = field(default="Equity") # # Equity or Option

    def __post_init__(self):
        """
        Initializes derived attributes based on the symbol.
        """
        if not self.action in ["bto", "sto", "btc", "stc", "deposit","withdraw"]:
            raise ValueError(f"Invalid action: {self.action}")  
        if self.action.endswith('c'):
            # ensure there is matching holding for close
            pass

        # ensure matching quantity
        if self.action.startswith('s') and self.quantity > 0:
            self.quantity = -self.quantity
        elif self.action.startswith('b') and self.quantity < 0:
            self.quantity = -self.quantity

        
        isoption = len(self.symbol) > 12
        if isoption:
            self.asset_type = option_type(self.symbol)
            self.instrument_type = 'Equity Option'
            self.underlying_symbol = option_underyling(self.symbol)
        else:
            self.asset_type = 'S'
            self.instrument_type = 'Equity'
            self.underlying_symbol = self.symbol

