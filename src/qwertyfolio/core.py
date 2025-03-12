import json
import os
import sys
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict
from tabulate import tabulate

from .transaction import Transaction, TransactionLogger
from .assets import Asset
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
        self.holdings: list[Asset] = []
        self.cash_balance: float = 0.0
        self.transactions: List[Asset] = []
        self.transactions_dict = defaultdict(list) # key by chain id
        self.transactions_log = TransactionLogger(self.transaction_log_file)
        self._load_portfolio()

    def _load_portfolio(self):
        """Loads portfolio data from the JSON file."""
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, "r") as f:
                data = json.load(f)
                self.cash_balance = data.get("cash_balance", 0.0)
                self.holdings: list[Asset] = [Asset(h) for h in data.get("holdings", [])]

    def _save_portfolio(self):
        """Saves portfolio data to the JSON file."""
        with open(self.portfolio_file, "w") as f:
            json.dump(
                {
                    "holdings": [h.serialize(for_json=True) for h in self.holdings],
                    "cash_balance": self.cash_balance,
                },
                f,
                indent=4,
            )

    def _record_transaction(self, transaction: Transaction): # TODO cut
        """
        Records a transaction with timestamp and details.
        """
        tx_legs: list = [leg.copy() for leg in transaction.legs]
        if transaction.chainid not in self.transactions_dict:
            self.transactions_dict[transaction.chainid] = []    
        self.transactions_dict[transaction.chainid].extend(tx_legs)
        self.transactions.extend(tx_legs)
        self.transactions_log.record_transaction(transaction)
        self._save_portfolio()

    def update_cash_balance(self, amount:float):
        """Adds cash to the portfolio."""
        self.cash_balance += amount
        transaction = Transaction(legs=[Asset(symbol=Asset.CASH_SYMBOL, quantity=amount, price=1.0)])
        self._record_transaction(transaction)
    
    def find_holding(self, key, val, filter:list[Asset] = [], not_in: bool = False) -> list[Asset]:
        ret: list[Asset] = []
        review = filter if len(filter) > 0 else self.holdings
        if not_in:
            for asset in review:
                found = asset.df.loc[asset.df[key] != val]
                if len(found) > 0:
                    ret.append(asset)
        else:
            for asset in review:
                found = asset.df.loc[asset.df[key] == val]
                if len(found) > 0:
                    ret.append(asset)
        return ret
    
    def _update_holding(self,transaction: Transaction):
        for leg in transaction.legs:
            holdings = self.find_holding(Asset.SYMBOL, leg.get_attr(Asset.SYMBOL))
            if len(holdings) > 0:
                total_qty = leg.get_attr(Asset.QUANTITY) + holdings[0].get_attr(Asset.QUANTITY)
                if total_qty == 0:
                    # close - remove the holding
                    self.holdings = self.find_holding(Asset.SYMBOL, leg.get_attr(Asset.SYMBOL), not_in=True)
                else:
                    oldsum = holdings[0].get_attr(Asset.PRICE) * holdings[0].get_attr(Asset.QUANTITY)
                    cursum = leg.get_attr(Asset.PRICE) * leg.get_attr(Asset.QUANTITY)
                    holdings[0].df[Asset.AVERAGE_OPEN_PRICE] = (oldsum + cursum) / total_qty
                    holdings[0].df[Asset.QUANTITY] = total_qty
                    holdings[0].df[Asset.ROLL_COUNT] = transaction.roll_count
            else:
                self.holdings.append(leg)

    def execute_transaction(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs.

        Args:
            transaction : A list of transaction legs.
        """
        # Check for sufficient funds
        cost = transaction.calc_cost() 
        if self.cash_balance < cost and cost > 0:
            warn("Not enough cash to execute this order")
            return False

        # if a transaction asset matches an existing holding
        # then we inherit the chainid 
        for leg in transaction.legs:
            symbol = leg.get_attr(Asset.SYMBOL)
            holding = self.find_holding(Asset.SYMBOL, symbol)
            if len(holding) > 0:
                transaction.chainid = holding[0].get_attr(Asset.CHAINID)
                transaction.roll_count = holding[0].get_attr(Asset.ROLL_COUNT) + 1
                # update legs with found chain info
                for leg in transaction.legs:
                    leg.set_attr(Asset.CHAINID, transaction.chainid)
                    leg.set_attr(Asset.ROLL_COUNT, transaction.roll_count) 
                break

        self._update_holding(transaction) 
        self.cash_balance -= cost
        self._record_transaction(transaction)
        return True


    def calculate_pnl(self, current_prices):
        """Calculates the Profit and Loss (PnL) of the portfolio."""
        pnl = 0.0
        for holding in self.holdings:
            symbol = holding.get_attr(Asset.SYMBOL)
            if symbol in current_prices:
                qty = holding.get_attr(Asset.QUANTITY)
                current_value = qty * current_prices[symbol]
                initial_value = qty * holding.get_attr(Asset.AVERAGE_OPEN_PRICE)
                pnl += current_value - initial_value
            else: 
                print(f"Warning: No current price found for {symbol}.")
        return pnl

    def get_portfolio_value(self, current_prices: dict) -> float:
        """Calculates the total value of the portfolio, including cash."""
        total_value = self.cash_balance
        for holding in self.holdings:
            symbol = holding.get_attr(Asset.SYMBOL)
            if symbol in current_prices:
                qty = holding.get_attr(Asset.QUANTITY)
                total_value += qty * current_prices[symbol]
            else: 
                print(f"Warning: No current price found for {holding.symbol}.")

        return total_value  
    
    def print_portfolio(self):
        """Prints the current portfolio holdings."""
        print("Current Portfolio:")
        print(f"Cash Balance: ${self.cash_balance:.2f}")
        df = pd.DataFrame([h.serialize(for_json=True) for h in self.holdings], index=None)
        tabl = tabulate(df, headers='keys', tablefmt='psql')
        print(tabl)
    
    def print_transactions(self, cols: list[str] = TransactionLogger.SHOW_COLUMNS):
        self.transactions_log.print_transactions(cols)

    def print_order_chains(self, cols: list[str] = TransactionLogger.SHOW_COLUMNS):
        """ prints order chains. """
        chainids = list(self.transactions_dict.keys())
        chainids.sort()
        print("Order Chains :")
        for chainid in chainids:
            print(f"  chain: {chainid}")
            txlegs = self.transactions_dict[chainid]
            df = pd.DataFrame([h.serialize(for_json=True) for h in txlegs], index=None)
            tabl = tabulate(df[cols], headers='keys', tablefmt='psql')
            print(tabl)

