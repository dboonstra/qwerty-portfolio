import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .transaction import Transaction
from .transactionleg import TransactionLeg
from .holding import Holding
from .util import (
    option_underyling, 
    option_expires_at, 
    option_strike, 
    option_type, 
    debug, 
    warn
)





class PortfolioManager:
    """
    Manages a simulated stock and options portfolio, including buying, selling,
    cash management, PnL calculation, and transaction history.
    """

    def __init__(self, portfolio_file="simulated_portfolio.json", transaction_log_file="transaction_log.csv"):
        """
        Initializes the PortfolioManager.

        Args:
            portfolio_file (str): Path to the JSON file for portfolio data.
        """
        self.portfolio_file = portfolio_file
        self.transaction_log_file = transaction_log_file
        self.holdings: List[Holding] = []
        self.cash_balance: float = 0.0
        self.transactions: List[Transaction] = []
        self.transactions_dict = defaultdict(list) # key by chain id
        self._load_portfolio()
       # Ensure transaction log file exists and has headers
        if not os.path.exists(self.transaction_log_file): 
            self._write_transaction_log_header() 

    def _load_portfolio(self):
        """Loads portfolio data from the JSON file."""
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, "r") as f:
                data = json.load(f)
                self.cash_balance = data.get("cash_balance", 0.0)
                # check that key exists. 
                if "transactions" in data :
                    self.transactions = [self._load_transaction(t) for t in data.get("transactions", [])]
                else:
                    self.transactions = []
                self.holdings = [self._load_holding(h) for h in data.get("holdings", [])]
            #  reload transactions into the dict for easy recall
            self.transactions_dict = defaultdict(list)
            for trans in self.transactions:
                self.transactions_dict[trans.chainid].append(trans)
        else:
            # default values for a new run
            self.cash_balance = 0.0
            self.holdings = []
            self.transactions = []
            self.transactions_dict = defaultdict(list)

    def _get_chainid_from_symbol(self,symbol) -> tuple[int,int]:
        """ gets the chain id and roll count based on prior activity """
        for holding in self.holdings:
            if holding.symbol == symbol:
                return holding.chainid, holding.roll_count
        return 0, 0  

    def _load_holding(self,holding_data) -> Holding:
        """ load holding helper"""
        expires = None
        if holding_data['expires_at'] is not None:
            expires = datetime.datetime.fromisoformat(holding_data['expires_at'])
        return Holding(
                    symbol=holding_data["symbol"],
                    quantity=holding_data["quantity"],
                    price=holding_data["price"],
                    underlying_symbol=holding_data["underlying_symbol"],
                    average_open_price=holding_data["average_open_price"],
                    expires_at=expires,
                    instrument_type=holding_data["instrument_type"],
                    asset_type=holding_data["asset_type"],
                    multiplier=holding_data["multiplier"],
                    chainid=holding_data["chainid"],
                    roll_count=holding_data["roll_count"],
                )

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


    def _load_transaction(self, transaction_data) -> Transaction:
        """ load transaction helper """
        timestamp = datetime.datetime.fromisoformat(transaction_data["timestamp"])
        legs = [TransactionLeg(
            symbol=leg["symbol"],
            quantity=leg["quantity"],
            price=leg["price"],
            action=leg["action"],
            asset_type=leg["asset_type"],
            instrument_type=leg["instrument_type"],
            ) for leg in transaction_data.get("legs", [])] # handles missing legs key
        return Transaction(
            timestamp=timestamp, 
            legs=legs,
            chainid=transaction_data.get("chainid",0), 
            roll_count=transaction_data.get("roll_count",0)
            )

    def _write_transaction_log_header(self):
        df = pd.DataFrame(columns=["timestamp", "chainid", "roll_count", "leg_symbol", "leg_quantity", "leg_price", "leg_action", "leg_asset_type", "leg_instrument_type"])
        df.to_csv(self.transaction_log_file, index=False)

    def _append_transaction_to_log(self, transaction: Transaction):
        """Appends a transaction to the CSV log file."""
        data = [[transaction.timestamp.isoformat(), transaction.chainid, transaction.roll_count, leg.symbol, leg.quantity, leg.price, leg.action, leg.asset_type, leg.instrument_type] for leg in transaction.legs]
        df = pd.DataFrame(data, columns=["timestamp", "chainid", "roll_count", "leg_symbol", "leg_quantity", "leg_price", "leg_action", "leg_asset_type", "leg_instrument_type"])
        df.to_csv(self.transaction_log_file, mode='a', header=not os.path.exists(self.transaction_log_file), index=False)


    def _save_portfolio(self):
        """Saves portfolio data to the JSON file."""
        # Ensure all transactions in dict are in the list
        for trans in [tran for translist in self.transactions_dict.values() for tran in translist]:
            if trans not in self.transactions: self.transactions.append(trans)
        """Saves portfolio data to the JSON file."""
        with open(self.portfolio_file, "w") as f:
            json.dump(
                {
                    "holdings": [h.serialize() for h in self.holdings],
                    "cash_balance": self.cash_balance,
                },
                f,
                indent=4,
            )

    def _record_transaction(self, transaction: Transaction):
        """
        Records a transaction with timestamp and details.
        """
        self._append_transaction_to_log(transaction)
        self.transactions_dict[transaction.chainid].append(transaction)
        self._save_portfolio()

    def deposit_cash(self, amount):
        """Adds cash to the portfolio."""
        if amount > 0:
            self.cash_balance += amount
            transaction = Transaction(legs=[TransactionLeg("cash", amount, 1.0, "deposit", 'S','Equity')])
            self._record_transaction(transaction)

    def withdraw_cash(self, amount):
        """Removes cash from the portfolio."""
        if amount > 0 and amount <= self.cash_balance:
            self.cash_balance -= amount
            transaction = Transaction(legs=[TransactionLeg("cash", -amount, 1.0, "withdraw", 'S','Equity')])
            self._record_transaction(transaction)
    
    def _find_holding(self, symbol) -> Optional[Holding]:
        for h in self.holdings:
            if h.symbol == symbol:
                return h
        return None

    def _update_holding(self, leg: TransactionLeg, transaction: Transaction):

        holding = self._find_holding(leg.symbol)
        if holding is None:
            
            # for opening a transaction , we know the price is the same as leg price.
            holding = Holding(symbol=leg.symbol, quantity=0, price=leg.price, chainid=transaction.chainid)
            if len(leg.symbol)>6:
                holding.asset_type = leg.asset_type
                holding.instrument_type = leg.instrument_type
                holding.underlying_symbol = option_underyling(leg.symbol)
                holding.expires_at = option_expires_at(leg.symbol)
                holding.multiplier = 100

            self.holdings.append(holding)

        holding.average_open_price = (holding.average_open_price * holding.quantity + leg.price*leg.quantity) / (holding.quantity + leg.quantity) if holding.quantity > 0 else leg.price
        holding.quantity += leg.quantity
        holding.price = leg.price            
        holding.roll_count = transaction.roll_count            
        if holding.quantity == 0:
            self.holdings.remove(holding)

    def execute_transaction(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs.

        Args:
            transaction : A list of transaction legs.
        """
        # Check for sufficient funds
        cost = 0
        chainid = 0
        roll_count = 0

        for leg in transaction.legs:
            debug(f"Executing transaction LEG: {leg.action} / {leg.quantity} / {leg.price} ")
            # for bto , btc, sto, stc
            cost += leg.quantity * leg.price # pos quantity cost money

            if leg.action.endswith("c"):
                chainid, roll_count = self._get_chainid_from_symbol(leg.symbol)
                if chainid == 0:
                    warn(f"Cannot Exec {leg.action} with {leg.symbol} - no chainid found")
                    return False

        if self.cash_balance < cost and cost > 0:
                warn("Not enough cash to execute this order")
                return False

        # record chain id on trans and legs and holdings
        if chainid == 0 : # first chain of this sym
            transaction.chainid = Holding._next_chainid
            Holding._next_chainid+=1
        else:
            # this is a roll , and it needs a chain id.
            transaction.chainid = chainid
            transaction.roll_count = roll_count + 1 

        for leg in transaction.legs:
            self._update_holding(leg, transaction)
        self.cash_balance -= cost
        self._record_transaction(transaction)
        return True


    def calculate_pnl(self, current_prices):
        """Calculates the Profit and Loss (PnL) of the portfolio."""
        pnl = 0.0
        for holding in self.holdings:
            if holding.symbol in current_prices:
                current_value = holding.quantity * current_prices[holding.symbol]
                if holding.quantity >= 0:  # Long position
                    initial_cost = holding.quantity * holding.average_open_price
                    pnl += current_value - initial_cost
                else:  # Short position
                    initial_value = 0.0
                    pnl += initial_value - current_value
            else:
                print(f"Warning: No current price found for {holding.symbol}.")
        return pnl

    def get_portfolio_value(self, current_prices: dict) -> float:
        """Calculates the total value of the portfolio, including cash."""
        total_value = self.cash_balance
        for holding in self.holdings:
            if holding.symbol in current_prices:
                total_value += holding.quantity * current_prices[holding.symbol]
        return total_value

    def print_portfolio(self):
        """Prints the current portfolio holdings."""
        print("Current Portfolio:")
        print(f"Cash Balance: ${self.cash_balance:.2f}")
        for holding in self.holdings:
            sign = "+" if holding.quantity >= 0 else ""
            print(f"  {holding.symbol}: {sign}{holding.quantity}, avg cost ${holding.average_open_price:.2f}, type: {holding.instrument_type}, asset:{holding.asset_type}, chain:{holding.chainid} rolls:{holding.roll_count}")

    def print_transactions(self):
        """Prints the transaction history."""
        print("Transaction History:")
        for transaction in self._load_transactions_from_log():
            print(f"  Timestamp: {transaction.timestamp.isoformat()}, ChainID:{transaction.chainid}, Roll:{transaction.roll_count}")
            for leg in transaction.legs:
                print(f"    {leg.action}: {leg.symbol}, qty: {leg.quantity}, price: {leg.price:.2f}, type: {leg.instrument_type}, asset:{leg.asset_type}")
    def print_order_chains(self):
        """ prints order chains. """
        chainids = set()
        for transaction in self.transactions:
            chainids.add(transaction.chainid)
        print("Order Chains :")
        for chainid in chainids:
            print(f"  chain: {chainid}")
            for transaction in self.transactions_dict[chainid]:
                    print(f"    Timestamp: {transaction.timestamp.isoformat()}, Roll:{transaction.roll_count}")
                    for leg in transaction.legs:
                        print(f"      {leg.action}: {leg.symbol}, qty: {leg.quantity}, price: {leg.price:.2f}, type: {leg.instrument_type}, asset:{leg.asset_type}")

