import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .transactionleg import TransactionLeg


@dataclass
class Transaction:
    """
    Represents a transaction with one or more legs.
    """
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    legs: List[TransactionLeg] = field(default_factory=list)
    chainid : int = 0
    roll_count: int = 0

    def serialize(self) -> dict:
        """Serializes a Transaction object to a dictionary."""
        t = vars(self).copy()
        if isinstance(t['timestamp'], datetime.datetime):
            t['timestamp'] = t['timestamp'].isoformat()  # json format
        t['legs'] = [vars(leg) for leg in self.legs]
        return t

