import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict
from .holding import Asset
from .util import warn, option_type, option_underyling



@dataclass
class TransactionLeg(Asset):
    """
    Represents a single asset in a transaction (stock or option).
    """

@dataclass
class Transaction:
    """
    Represents a transaction with one or more legs.
    legs may be introduced as array of legs or DF of legs

    """
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    legs: List[TransactionLeg] = field(default_factory=list)
    chainid : int = 0
    roll_count: int = 0
    df: Optional[pd.DataFrame] = None

    def __post_init__(self):
        if len(self.legs) == 0:
            if self.df is None:
                raise ValueError("Transaction must have at least one leg.")
        else:
            df = pd.DataFrame()
            for leg in self.legs:
                df = pd.concat([df, leg.df])
            self.df = df
        if self.chainid > 0:
            self.df['chainid'] = self.chainid
        if self.roll_count > 0:
            self.df['roll_count'] = self.roll_count       
        # TODO update cost calculations for margin impact
        self.df['cost'] = self.df['quantity'] * self.df['price']

    def serialize(self) -> dict:
        """Serializes a Transaction object to a dictionary."""
        t = vars(self).copy()
        if isinstance(t['timestamp'], datetime.datetime):
            t['timestamp'] = t['timestamp'].isoformat()  # json format
        t['legs'] = [vars(leg) for leg in self.legs]
        return t

@dataclass
class TransactionLogger:
    transaction_log_file: str 


    LOG_COLUMNS = [
        "timestamp", 
        "chainid", 
        "roll_count", 
        "symbol", 
        "quantity", 
        "price", 
        "cost",
        "action", 
        "asset_type",
        "underlying_symbol",
        "days_to_expiration",
        "delta",
        "gamma",
        "theta",
        "quote_date",
        ]

    def __post_init__(self):
        """Initializes the transaction log."""
        if not self.transaction_log_file.endswith(".csv"):
            raise ValueError("Transaction log file must be a CSV file.")
        if not os.path.exists(self.transaction_log_file): 
            self._write_transaction_log_header() 


    def _write_transaction_log_header(self):
        df = pd.DataFrame(columns=TransactionLogger.LOG_COLUMNS)
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
        legs = [TransactionLeg(symbol=row["symbol"], quantity=int(row["quantity"]), price=float(row["price"]),
                               action=row["action"], asset_type=row["asset_type"])]
        return Transaction(timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(), legs=legs, chainid=int(row["chainid"]), roll_count=int(row["roll_count"]))



    def record_transaction(self, transaction: Transaction):
        """Appends a transaction to the CSV log file."""
        tx = transaction.df.copy()
        print('-')
        print(tx.columns)
        print('-')
        print(TransactionLogger.LOG_COLUMNS)
        print('-')

        tx = tx[TransactionLogger.LOG_COLUMNS]
        # tx = transaction.df[TransactionLogger.LOG_COLUMNS].copy()
        if 'expires_at' in tx.columns:
            tx['expires_at'] = tx['expires_at'].isoformat()
               
        tx['timestamp'] = transaction.timestamp.isoformat()
        if transaction.chainid > 0:
            tx['chainid'] = transaction.chainid
        if transaction.roll_count > 0:
            tx['roll_count'] = transaction.roll_count
        tx.to_csv(self.transaction_log_file, mode='a', header=not os.path.exists(self.transaction_log_file), index=False)

    def print_transactions(self):
        """Prints the transaction history."""
        print("Transaction History:")
        for transaction in self._load_transactions_from_log():
            print(f"  Timestamp: {transaction.timestamp.isoformat()}, ChainID:{transaction.chainid}, Roll:{transaction.roll_count}")
            for leg in transaction.legs:
                print(f"    {leg.action}: {leg.symbol}, qty: {leg.quantity}, price: {leg.price:.2f},  asset:{leg.asset_type}")

