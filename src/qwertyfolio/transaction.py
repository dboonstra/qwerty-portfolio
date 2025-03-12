import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict
from .assets import Asset
from .util import warn, option_type, option_underyling
from tabulate import tabulate


@dataclass
class Transaction:
    """
    Represents a transaction with one or more legs.
    legs may be introduced as array of legs or DF of legs

    """
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    legs: List[Asset] = field(default_factory=list)
    chainid : int = 0
    roll_count: int = 0
    # incrementor for order chains
    df: Optional[pd.DataFrame] = None
    _next_chainid: ClassVar[int] = 1

    def __post_init__(self):
        # move dataframe into Asset legs if not already there
        if len(self.legs) == 0:
            if self.df is None:
                raise ValueError("A new Transaction must have at least one leg.")
            # convert DF to assets
            assets = self.df.to_dict(orient='records')
            self.legs = [Asset(**asset) for asset in assets]

        if self.chainid == 0:
                print("Init a chainid line:39")
                self.chainid = self.next_chainid()
        for leg in self.legs:
            leg.set_attr(Asset.CHAINID, self.chainid)
            if self.roll_count > 0: 
                leg.set_attr(Asset.ROLL_COUNT, self.roll_count)
            leg.set_attr(Asset.TIME_STAMP, self.timestamp)

    def calc_cost(self):
        # would be better to plug in a margin estimator 
        # this calculation is best for equities 
        # and falls short of cash/margin option consideration 
        # TODO : improve 
        cost: float = 0
        for leg in self.legs:
            cost += leg.get_attr(Asset.QUANTITY) * leg.get_attr(Asset.PRICE)
        return cost

    def serialize(self) -> dict:
        """Serializes a Transaction object to a dictionary."""
        pass

    def next_chainid(self) -> int:
        Transaction._next_chainid += 1
        return Transaction._next_chainid

    

class TransactionLogger:
    transaction_log_file: str 

    LOG_COLUMNS: list[str] = [
        *Asset.EXPECTED_COLUMNS
        ]

    SHOW_COLUMNS: list[str] = [
        *Asset.EXPECTED_COLUMNS
    ]

    def __init__(self, log_file) -> None:
        self.transaction_log_file = log_file

    def __post_init__(self):
        """Initializes the transaction log."""
        if not self.transaction_log_file.endswith(".csv"):
            raise ValueError("Transaction log file must be a CSV file.")
        if not os.path.exists(self.transaction_log_file): 
            self._write_transaction_log_header() 

    def _write_transaction_log_header(self):
        df = pd.DataFrame(columns=TransactionLogger.LOG_COLUMNS)
        df.to_csv(self.transaction_log_file, index=False)

    def record_transaction(self, transaction: Transaction, cols: list[str] = LOG_COLUMNS):
        """Appends a transaction to the CSV log file."""
        tx = pd.DataFrame(transaction.serialize())
        tx = tx.reindex(columns=cols)
        tx.to_csv(self.transaction_log_file, mode='a', header=False, index=False)

    def show_transactions(self, title: str, df: pd.DataFrame, cols: list[str] = SHOW_COLUMNS):
        print(f"# {title}")
        print(tabulate(df[cols], headers='keys', tablefmt='psql'))
        print()

    def print_transactions(self, bychain: bool = False):
        """Prints the transaction history."""
        print("Transaction History:")
        df = self.load_transactions_from_log()
        if bychain:
            chainids: list = df[Asset.CHAINID].unique()
            for chainid in chainids:
                self.show_transactions(f"Chain: {chainid}", df.loc[df[Asset.CHAINID] == chainid])
        else:
            self.show_transactions("Transactions")

    def load_transactions_from_log(self) -> pd.DataFrame:
        """Loads transactions from the transaction log file."""
        try:
            return pd.read_csv(self.transaction_log_file)
        except Exception as e:
            return warn(f"Error loading transactions from log file: {self.transaction_log_file} - {e}")
