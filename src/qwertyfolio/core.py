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
from .globals import Gl
from .assets import Asset
from .util import (
    option_underyling, 
    option_expires_at, 
    option_strike, 
    option_type, 
    debug, 
    warn
)

def print_tabulate(df: pd.DataFrame, cols: list[str] = TransactionLogger.SHOW_COLUMNS):
        tabl = tabulate(df[cols], headers='keys', tablefmt='psql')
        print(tabl)


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
        self.order_chains: dict[str:list[Asset]] = {}
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
            self.order_chains = self._build_order_chains()

    def _build_order_chains(self) -> dict[str:list[Asset]]:
        """ create dict of holdings that is keyed by order chain id """
        chaindict: dict[str:list[Asset]] = {}
        for holding in self.holdings:
            chainid = holding.get_attr(Asset.CHAINID)
            if chainid not in chaindict:
                chaindict[chainid] = []
            chaindict[chainid].append(holding)
        return chaindict

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
        # maintain order_chain history
        if transaction.chainid not in self.transactions_dict:
            self.transactions_dict[transaction.chainid] = []    
        self.transactions_dict[transaction.chainid].extend(tx_legs)
        self.transactions.extend(tx_legs)
        # record to file with logger
        self.transactions_log.record_transaction(transaction)

        # save portfolio file
        self._save_portfolio()

    def update_cash_balance(self, amount:float):
        """Adds cash to the portfolio."""
        self.cash_balance += amount
        transaction = Transaction(legs=[Asset(symbol=Asset.CASH_SYMBOL, chainid=1, quantity=amount, price=1.0)])
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
    
    def holding_by_dict(self) -> dict[str:Asset]:
        ret: dict[str:Asset] = {}
        for h in self.holdings:
            sym = h.get_attr(Asset.SYMBOL)
            if sym not in ret:
                ret[h.get_attr(Asset.SYMBOL)] = h
            else:
                warn(f"Portfolio Holding has duplicate symbol - {sym}")
        return ret
 

    def _update_holding(self,transaction: Transaction) -> bool:
        hd = self.holding_by_dict()
        # merge legs to holdings

            
        def _sync_ids(transaction, hold_asset):
            # match the chainid and roll_count to found asset
            transaction.chainid = hold_asset.get_attr(Asset.CHAINID)
            transaction.roll_count = hold_asset.get_attr(Asset.ROLL_COUNT) + 1
            for leg in transaction.legs:
                leg.set_attr(Asset.CHAINID, transaction.chainid)
                leg.set_attr(Asset.ROLL_COUNT, transaction.roll_count)

        for orig_leg in transaction.legs:
            # make a copy so that original is logged in transaction logs
            leg = orig_leg.copy()
            symbol = leg.get_attr(Asset.SYMBOL)            

            # cut
            quantity = leg.get_attr(Asset.QUANTITY)
            print(f"\nLEG in update_holding: {symbol} ({quantity}) \n" )

            # if this is in portfolio we add or subtract
            if symbol in hd:
                _sync_ids(transaction, hd[symbol])
                # merge current holding data to new leg data 
                hol_qty = hd[symbol].get_attr(Asset.QUANTITY)
                leg_qty = leg.get_attr(Asset.QUANTITY)
                total_qty = hol_qty + leg_qty
                hol_avg = hd[symbol].get_attr(Asset.AVERAGE_OPEN_PRICE)
                leg_price = leg.get_attr(Asset.PRICE)
                # carry over average price with new calc
                if total_qty == 0:
                    leg.set_attr(Asset.AVERAGE_OPEN_PRICE, leg_price)
                else:
                    leg.set_attr(Asset.AVERAGE_OPEN_PRICE, (hol_qty * hol_avg + leg_qty * leg_price) / (hol_qty + leg_qty))
                # carry over new calculated quantity
                leg.set_attr(Asset.QUANTITY, total_qty)
                # set held asset for removal with Qty 0 
                hd[symbol].set_attr(Asset.QUANTITY, 0)
                self.holdings.append(leg)
            elif leg.get_attr(Asset.ORDER_TYPE) == Gl.BUY_TO_CLOSE or leg.get_attr(Asset.ORDER_TYPE) == Gl.SELL_TO_CLOSE:
                warn(f"Port Holding update found close for {symbol} with no assets")
                return False
            else:
                self.holdings.append(leg)

        # remove 0 qty items
        self.holdings = [ h for h in self.holdings if h.get_attr(Asset.QUANTITY) != 0]
        # save as file
        self._save_portfolio()
        # reset order chains
        self.order_chains = self._build_order_chains()
        return True




    def execute_transaction(self, transaction : Transaction) -> bool:
        # Check for sufficient funds
        cost = transaction.calc_cost() 
        if self.cash_balance < cost and cost > 0:
            warn("Not enough cash to execute this order")
            return False
        # update holdings without error
        if self._update_holding(transaction):
            # update cash 
            self.cash_balance -= cost
            # log activity
            self._record_transaction(transaction)
            return True
        else:
            return False

    def _reset_order_type(self, legs : list[Asset], buy_type: str, sell_type: str):
        """ set order_type of leg assets """
        for leg in legs:
            order_type = buy_type if leg.get_attr(Asset.QUANTITY) > 0 else sell_type
            leg.set_attr(Asset.ORDER_TYPE, order_type)

    def execute_close(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs.  All orders are Close orders
        Args:
            transaction : A transaction object containing a list of transaction legs.
        """
        self._reset_order_type(transaction.legs, Gl.BUY_TO_CLOSE, Gl.SELL_TO_CLOSE)        
        return self.execute_transaction(transaction)

    def execute_open(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs. All orders are Open orders
        Args:
            transaction : A transaction object containing a list of transaction legs.
        """
        self._reset_order_type(transaction.legs, Gl.BUY_TO_OPEN, Gl.SELL_TO_OPEN)
        return self.execute_transaction(transaction)
        

    def execute_roll(self, transaction : Transaction) -> bool:
        """
        Executes a transaction with multiple legs. Mix of Open and Close
        # find the assets that are rolling 
        # carry over the chainid for order_chain and +1 roll_count
        Args:
            transaction : A transaction object containing a list of transaction legs.
        """
        noclose: bool = True
        for leg in transaction.legs:

            leg_found_in_holding: bool = False
            for holding in self.holdings:
                if holding.get_attr(Asset.SYMBOL) == leg.get_attr(Asset.SYMBOL):
                    leg_found_in_holding = True
                    if holding.get_attr(Asset.QUANTITY) < 0:
                        if leg.get_attr(Asset.QUANTITY) > 0:
                            leg.set_attr(Asset.ORDER_TYPE, Gl.BUY_TO_CLOSE)
                            noclose = False
                        else:
                            leg.set_attr(Asset.ORDER_TYPE, Gl.SELL_TO_OPEN)
                    else:
                        if leg.get_attr(Asset.QUANTITY) < 0:
                            leg.set_attr(Asset.ORDER_TYPE, Gl.SELL_TO_CLOSE)
                            noclose = False
                        else:
                            leg.set_attr(Asset.ORDER_TYPE, Gl.BUY_TO_OPEN)
            if leg_found_in_holding:
                continue
            if leg.get_attr(Asset.QUANTITY) > 0:
                leg.set_attr(Asset.ORDER_TYPE, Gl.BUY_TO_OPEN)
            else:
                leg.set_attr(Asset.ORDER_TYPE, Gl.SELL_TO_OPEN)


        if noclose:
            warn(f"Roll of transaction chain missing closure order")
            return False

        return self.execute_transaction(transaction)


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
    
    def print_portfolio(self, cols: list[str] = TransactionLogger.SHOW_COLUMNS):
        """Prints the current portfolio holdings."""
        print("Current Portfolio:")
        print(f"Cash Balance: ${self.cash_balance:.2f}")
        df = pd.DataFrame([h.serialize(for_json=True) for h in self.holdings], index=None)
        print_tabulate(df, cols)
    
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
            if chainid in self.order_chains:
                txlegs.extend(self.order_chains[chainid])
            df = pd.DataFrame([h.serialize(for_json=True) for h in txlegs], index=None)
            print_tabulate(df, cols)



