import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .transaction import Transaction, TransactionLeg, TransactionLogger
from .holding import Asset
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
        self.holdings: pd.DataFrame = ()
        self.cash_balance: float = 0.0
        self.transactions: List[Transaction] = []
        self.transactions_dict = defaultdict(list) # key by chain id
        self.transactions_log = TransactionLogger(self.transaction_log_file)
        self._load_portfolio()

    def _load_portfolio(self):
        """Loads portfolio data from the JSON file."""
        self.transactions = []
        self.transactions_dict = defaultdict(list)
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, "r") as f:
                data = json.load(f)
                self.cash_balance = data.get("cash_balance", 0.0)
                self.holdings = pd.DataFrame([self._load_holding(h) for h in data.get("holdings", [])])
        else:
            # default values for a new run
            self.cash_balance = 0.0
            self.holdings = pd.DataFrame()


    def _load_holding(self,holding_data) -> pd.DataFrame:
        """ load holding helper - loads from json obj """
        expires = None
        if holding_data['expires_at'] is not None:
            expires = datetime.datetime.fromisoformat(holding_data['expires_at'])
        return pd.DataFrame(
                    symbol=holding_data["symbol"],
                    quantity=holding_data["quantity"],
                    price=holding_data["price"],
                    underlying_symbol=holding_data["underlying_symbol"],
                    average_open_price=holding_data["average_open_price"],
                    expires_at=expires,
                    asset_type=holding_data["asset_type"],
                    multiplier=holding_data["multiplier"],
                    chainid=holding_data["chainid"],
                    roll_count=holding_data["roll_count"],
                )

    def _load_transaction(self, transaction_data) -> Transaction:
        """ load transaction helper """
        timestamp = datetime.datetime.fromisoformat(transaction_data["timestamp"])
        legs = [TransactionLeg(
            symbol=leg["symbol"],
            quantity=leg["quantity"],
            price=leg["price"],
            action=leg["action"],
            asset_type=leg["asset_type"],
            ) for leg in transaction_data.get("legs", [])] # handles missing legs key
        return Transaction(
            timestamp=timestamp, 
            legs=legs,
            chainid=transaction_data.get("chainid",0), 
            roll_count=transaction_data.get("roll_count",0)
            )

    def _save_portfolio(self):
        """Saves portfolio data to the JSON file."""
        # Ensure all transactions in dict are in the list
        for trans in [tran for translist in self.transactions_dict.values() for tran in translist]:
            if trans not in self.transactions: self.transactions.append(trans)
        """Saves portfolio data to the JSON file."""
        holdings_copy = self.holdings.copy()
        if 'expires_at' in holdings_copy.columns:
            holdings_copy['expire_at'] = datetime.datetime.fromisoformat(holdings_copy['expires_at'])
        with open(self.portfolio_file, "w") as f:
            json.dump(
                {
                    "holdings": holdings_copy.to_dict(),
                    "cash_balance": self.cash_balance,
                },
                f,
                indent=4,
            )

    def _record_transaction(self, transaction: Transaction): # TODO cut
        """
        Records a transaction with timestamp and details.
        """
        self.transactions_log.record_transaction(transaction)
        self.transactions_dict[transaction.chainid].append(transaction)
        self._save_portfolio()

    def deposit_cash(self, amount):
        """Adds cash to the portfolio."""
        if amount > 0:
            self.cash_balance += amount
            transaction = Transaction(legs=[TransactionLeg("CASH", amount, 1.0, "deposit", 'S','Equity')])
            self._record_transaction(transaction)

    def withdraw_cash(self, amount):
        """Removes cash from the portfolio."""
        if amount > 0 and amount <= self.cash_balance:
            self.cash_balance -= amount
            transaction = Transaction(legs=[TransactionLeg("CASH", -amount, 1.0, "withdraw", 'S','Equity')])
            self._record_transaction(transaction)
    
    def _find_holding(self, key, val) -> pd.DataFrame:
        if key in self.holdings.columns:
            return self.holdings.loc[self.holdings[key] == val]
        return pd.DataFrame()

    def _update_holding(self,transaction: Transaction):
        for index, leg in transaction.df.iterrows():
            holding = self._find_holding('symbol', leg['symbol'])
            if len(holding) > 0:
                holding_index = holding.index[0]
                total_qty = leg['quantity'] + self.holdings.loc[holding_index, 'quantity']
                if total_qty == 0:
                    # close - remove the holding
                    self.holdings.drop(holding_index, inplace=True)
                else:
                    oldsum = self.holdings.loc[holding_index, 'average_open_price'] * self.holdings.loc[holding_index, 'quantity']
                    cursum = leg['price'] * leg['quantity'] 
                    self.holdings.loc[holding_index, 'average_open_price'] = (oldsum + cursum) / total_qty
                    self.holdings.loc[holding_index, 'quantity'] = total_qty
                    self.holdings.loc[holding_index, 'roll_count'] = transaction.roll_count
            else:
                self.holdings = pd.concat([self.holdings, leg.to_frame().T], ignore_index=True)

    def execute_transaction(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs.

        Args:
            transaction : A list of transaction legs.
        """
        # Check for sufficient funds
        cost = transaction.df['cost'].sum() 
        chainid = 0

        if 'chainid' in transaction.df.columns:
            chainid = transaction.chainid if transaction.chainid > 0 else transaction.df['chainid'].iloc[0] 
        else:
            chainid = transaction.chainid

        if 'roll_count' in transaction.df.columns:
            roll_count = transaction.roll_count if transaction.roll_count > 0 else transaction.df['roll_count'].iloc[0] 
        else:
            roll_count = transaction.roll_count

        if self.cash_balance < cost and cost > 0:
                warn("Not enough cash to execute this order")
                return False

        # record chain id on trans and legs and holdings
        if chainid == 0 : # first chain of this sym
            transaction.chainid = Asset._next_chainid
            Asset._next_chainid +=1
        else:
            # this is a roll , and it needs a chain id.
            transaction.chainid = chainid
            transaction.roll_count = roll_count + 1 

        self._update_holding(transaction) 
        self.cash_balance -= cost
        self._record_transaction(transaction)
        return True

    def _get_chainid_from_symbol(self,symbol) -> tuple[int,int]:
        """ gets the chain id and roll count based on prior activity """
        sym_holdings = self._find_holding('symbol', symbol)
        if len(sym_holdings) > 0:
            return sym_holdings.iloc[0]['chainid'], sym_holdings.iloc[0]['roll_count']
        return 0, 0  

    def calculate_pnl(self, current_prices):
        """Calculates the Profit and Loss (PnL) of the portfolio."""
        pnl = 0.0
        for index, holding in self.holdings.iterrows():
            if holding['symbol'] in current_prices:
                current_value = holding['quantity'] * current_prices[holding['symbol']]
                if holding['quantity'] >= 0:  # Long position
                    initial_cost = holding['quantity'] * holding['average_open_price']
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
        for holding in self.holdings.iterrows():
            sym = holding[1]['symbol']
            if sym in current_prices:
                total_value += holding[1]['quantity'] * current_prices[sym]
        return total_value  
    
    def print_portfolio(self):
        """Prints the current portfolio holdings."""
        print("Current Portfolio:")
        print(f"Cash Balance: ${self.cash_balance:.2f}")
        for holding in self.holdings.iterrows():
            sign = "+" if holding[1]['quantity'] >= 0 else ""
            print(f"  {holding[1]['symbol']}: {sign}{holding[1]['quantity']}, avg cost ${holding[1]['average_open_price']:.2f},  asset:{holding[1]['asset_type']}, chain:{holding[1]['chainid']} rolls:{holding[1]['roll_count']}")
    
    def print_transactions(self):
        self.transactions_log.print_transactions()

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
                        print(f"      {leg.action}: {leg.symbol}, qty: {leg.quantity}, price: {leg.price:.2f},  asset:{leg.asset_type}")

