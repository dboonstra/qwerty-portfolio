import os
import pandas as pd

from .globals import Gl
from .assets import Asset
from .transaction import Transaction
from .utils import print_tabulate, warn


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
        self.show_columns = TransactionLogger.SHOW_COLUMNS
        self.log_columns = TransactionLogger.LOG_COLUMNS


    def __post_init__(self):
        """Initializes the transaction log."""
        if not self.transaction_log_file.endswith(".csv"):
            raise ValueError("Transaction log file must be a CSV file.")
        if not os.path.exists(self.transaction_log_file): 
            self._write_transaction_log_header() 

    def update_show_columns(self, cols: list[str]):
        self.show_columns = cols
    
    def update_log_columns(self, cols: list[str]):
        self.log_columns = cols

    def _write_transaction_log_header(self):
        df = pd.DataFrame(columns=self.log_columns)
        df.to_csv(self.transaction_log_file, index=False)

    def record_transaction(self, transaction: Transaction):
        """Appends a transaction to the CSV log file."""
        tx = pd.DataFrame(transaction.serialize())
        tx = tx.reindex(columns=self.log_columns)
        tx.to_csv(self.transaction_log_file, mode='a', header=False, index=False)

    def print_transactions(self, bychain: bool = False):
        """Prints the transaction history."""
        print("Transaction History:")
        df = self.load_transactions_from_log()
        if bychain:
            chainids: list = df[Gl.CHAINID].unique()
            for chainid in chainids:
                print_tabulate(title=f"Chain: {chainid}", df=df.loc[df[Gl.CHAINID] == chainid])
        else:
            print_tabulate(title="All Transactions", df=df)

    def load_transactions_from_log(self) -> pd.DataFrame:
        """Loads transactions from the transaction log file."""
        try:
            return pd.read_csv(self.transaction_log_file)
        except Exception as e:
            return warn(f"Error loading transactions from log file: {self.transaction_log_file} - {e}")

    def clear_log(self):
        """Clears the transaction log."""
        if os.path.exists(self.transaction_log_file):
            os.remove(self.transaction_log_file)
        self._write_transaction_log_header()
