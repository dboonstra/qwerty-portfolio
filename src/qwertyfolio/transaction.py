import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .util import warn, option_type, option_underyling




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

@dataclass
class TransactionLog:
    transaction_log_file: str 

    def __post_init__(self):
        """Initializes the transaction log."""
        if not self.transaction_log_file.endswith(".csv"):
            raise ValueError("Transaction log file must be a CSV file.")
        if not os.path.exists(self.transaction_log_file): 
            self._write_transaction_log_header() 



    def _write_transaction_log_header(self):
        df = pd.DataFrame(columns=["timestamp", "chainid", "roll_count", "leg_symbol", "leg_quantity", "leg_price", "leg_action", "leg_asset_type", "leg_instrument_type"])
        df.to_csv(self.transaction_log_file, index=False)


    def _load_transactions_from_log(self) -> List[Transaction]:
        """Loads transactions from the transaction log file."""
        transactions: List[Transaction] = []
        try:
            df = pd.read_csv(self.transaction_log_file)
            for index, row in df.iterrows():
                transaction = self._load_transaction_from_row(row)
                transactions.append(transaction)
        except FileNotFoundError:
            warn(f"Transaction log file not found: {self.transaction_log_file}")
        return transactions

    def _load_transaction_from_row(self, row: pd.Series) -> Transaction:
        legs = [TransactionLeg(symbol=row["leg_symbol"], quantity=int(row["leg_quantity"]), price=float(row["leg_price"]),
                               action=row["leg_action"], asset_type=row["leg_asset_type"], instrument_type=row["leg_instrument_type"])]
        return Transaction(timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(), legs=legs, chainid=int(row["chainid"]), roll_count=int(row["roll_count"]))



    def record_transaction(self, transaction: Transaction):
        """Appends a transaction to the CSV log file."""
        data = [[transaction.timestamp.isoformat(), transaction.chainid, transaction.roll_count, leg.symbol, leg.quantity, leg.price, leg.action, leg.asset_type, leg.instrument_type] for leg in transaction.legs]
        df = pd.DataFrame(data, columns=["timestamp", "chainid", "roll_count", "leg_symbol", "leg_quantity", "leg_price", "leg_action", "leg_asset_type", "leg_instrument_type"])
        df.to_csv(self.transaction_log_file, mode='a', header=not os.path.exists(self.transaction_log_file), index=False)

    def print_transactions(self):
        """Prints the transaction history."""
        print("Transaction History:")
        for transaction in self._load_transactions_from_log():
            print(f"  Timestamp: {transaction.timestamp.isoformat()}, ChainID:{transaction.chainid}, Roll:{transaction.roll_count}")
            for leg in transaction.legs:
                print(f"    {leg.action}: {leg.symbol}, qty: {leg.quantity}, price: {leg.price:.2f}, type: {leg.instrument_type}, asset:{leg.asset_type}")

