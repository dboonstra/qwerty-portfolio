import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from numpy import int64 


from .globals import Gl
from .assets import Asset
from .utils import warn, parse_timestamp



@dataclass
class Transaction:
    """
    Represents a transaction with one or more legs.
    legs may be introduced as array of legs or DF of legs

    """
    timestamp: Optional[int64|int|str|datetime.datetime] = field(default_factory=datetime.datetime.now)
    legs: List[Asset] = field(default_factory=list)
    chainid : int = 1
    roll_count: int = 0
    # incrementor for order chains
    df: Optional[pd.DataFrame] = None
    _next_chainid: ClassVar[int] = 1

    def __post_init__(self):
        if not isinstance(self.timestamp, datetime.datetime):
            self.timestamp = parse_timestamp(str(self.timestamp))

        # move dataframe into Asset legs if not already there
        if len(self.legs) == 0:
            if self.df is None:
                raise ValueError("A new Transaction must have at least one leg.")
            # convert DF to assets
            assets = self.df.to_dict(orient='records')
            self.legs = [Asset(**asset) for asset in assets]

        if self.legs[0].get_attr(Gl.SYMBOL) != Gl.CASH_SYMBOL:
            self.chainid = self.next_chainid()

        for leg in self.legs:
            leg.set_attr(Gl.CHAINID, self.chainid)
            if self.roll_count > 0: 
                leg.set_attr(Gl.ROLL_COUNT, self.roll_count)
            leg.set_attr(Gl.TIME_STAMP, self.timestamp)
        
    def __repr__(self) -> str:
        s = f"Transaction: {self.timestamp}\n"
        for leg in self.legs:
            s += f"{leg.serialize()}\n"
        return s

    def calc_cost(self):
        # would be better to plug in a margin estimator 
        # this calculation is best for equities 
        # and falls short of cash/margin option consideration 
        # TODO : improve 
        cost: float = 0
        for leg in self.legs:
            cost += leg.get_attr(Gl.QUANTITY) * leg.get_attr(Gl.PRICE) * leg.get_attr(Gl.MULTIPLIER)
        return cost

    def serialize(self) -> dict:
        """Serializes a Transaction object to a dictionary."""
        pass

    def next_chainid(self) -> int:
        Transaction._next_chainid += 1
        return Transaction._next_chainid

    
