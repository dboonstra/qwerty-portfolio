import json
import os
from dataclasses import dataclass, field
from typing import Optional, List, ClassVar
import pandas as pd # type: ignore
from collections import defaultdict

from .transaction import Transaction
from .logger import TransactionLogger
from .globals import Gl
from .assets import Asset
from .utils import (
    print_tabulate,
    warn
)



class PortfolioManager:
    """
    Manages a simulated stock and options portfolio, including buying, selling,
    cash management, PnL calculation, and transaction history.
    """

    def __init__(self, 
                 portfolio_file="simulated_portfolio.json", 
                 transaction_log_file="transaction_log.csv",
                 new_portfolio: bool = False):
        """
        Initializes the PortfolioManager.

        Args:
            portfolio_file (str): Path to the JSON file for portfolio data.
            transaction_log_file (str): Path to the CSV file for transaction history.
            new_portfolio (bool): If True, creates a new empty portfolio.
        """
        self.portfolio_file = portfolio_file
        self.transaction_log_file = transaction_log_file
        self.holdings: list[Asset] = []
        self.order_chains: dict[str:list[Asset]] = {}
        self.cash_balance: float = 0.0
        self.transactions: List[Asset] = []
        self.transactions_dict = defaultdict(list) # key by chain id
        self.transactions_log = TransactionLogger(self.transaction_log_file)
        if new_portfolio:
            # remove current portfolio for new
            if os.path.exists(self.portfolio_file):
                os.remove(self.portfolio_file)
        self._load_portfolio()
        self._setup_order_chainid()

    def _setup_order_chainid(self):
        """ Load transaction log to find the max chainid
        Then setup the next_chainid to match
        """
        df: pd.DataFrame= self.transactions_log.load_transactions_from_log()
        if df is None or df.empty:
            return
        if Gl.CHAINID not in df.columns:
            return
        
        # Safely handle the case where CHAINID column exists and find its max
        chain_ids = df[Gl.CHAINID].dropna()  # Extract the column, drop NaNs
        if not chain_ids.empty:
            max_chainid = chain_ids.astype(int).max()
            Transaction._next_chainid = max_chainid + 1

    def _load_portfolio(self):
        """Loads portfolio data from the JSON file."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    data = json.load(f)
                    self.cash_balance = data.get("cash_balance", 0.0)
                    self.holdings: list[Asset] = [Asset(**h) for h in data.get("holdings", [])]
                self.order_chains = self._build_order_chains()
            except Exception as e:
                warn(f"Error loading portfolio: {e}")

    def _build_order_chains(self) -> dict[str:list[Asset]]:
        """ create dict of holdings that is keyed by order chain id """
        chaindict: dict[str:list[Asset]] = {}
        for holding in self.holdings:
            chainid = holding.get_attr(Gl.CHAINID)
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
        transaction = Transaction(legs=[Asset(symbol=Gl.CASH_SYMBOL, chainid=1, quantity=amount, price=1.0)])
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
            sym = h.get_attr(Gl.SYMBOL)
            if sym not in ret:
                ret[h.get_attr(Gl.SYMBOL)] = h
            else:
                warn(f"Portfolio Holding has duplicate symbol - {sym}")
        return ret
 

    def _update_holding(self,transaction: Transaction) -> bool:
        hd = self.holding_by_dict()
        # merge legs to holdings

            
        def _sync_ids(transaction, hold_asset):
            # match the chainid and roll_count to found asset
            transaction.chainid = hold_asset.get_attr(Gl.CHAINID)
            transaction.roll_count = hold_asset.get_attr(Gl.ROLL_COUNT) + 1
            for leg in transaction.legs:
                leg.set_attr(Gl.CHAINID, transaction.chainid)
                leg.set_attr(Gl.ROLL_COUNT, transaction.roll_count)

        for orig_leg in transaction.legs:
            # make a copy so that original is logged in transaction logs
            leg = orig_leg.copy()
            symbol = leg.get_attr(Gl.SYMBOL)            

            # if this is in portfolio we add or subtract
            if symbol in hd:
                _sync_ids(transaction, hd[symbol])
                # merge current holding data to new leg data 
                hol_qty = hd[symbol].get_attr(Gl.QUANTITY)
                leg_qty = leg.get_attr(Gl.QUANTITY)
                total_qty = hol_qty + leg_qty
                hol_avg = hd[symbol].get_attr(Gl.AVERAGE_OPEN_PRICE)
                leg_price = leg.get_attr(Gl.PRICE)
                # carry over average price with new calc
                if total_qty == 0:
                    leg.set_attr(Gl.AVERAGE_OPEN_PRICE, leg_price)
                else:
                    leg.set_attr(Gl.AVERAGE_OPEN_PRICE, (hol_qty * hol_avg + leg_qty * leg_price) / (hol_qty + leg_qty))
                # carry over new calculated quantity
                leg.set_attr(Gl.QUANTITY, total_qty)
                # set held asset for removal with Qty 0 
                hd[symbol].set_attr(Gl.QUANTITY, 0)
                self.holdings.append(leg)
            elif leg.get_attr(Gl.ORDER_TYPE) == Gl.BUY_TO_CLOSE or leg.get_attr(Gl.ORDER_TYPE) == Gl.SELL_TO_CLOSE:
                warn(f"Port Holding update found close for {symbol} with no assets")
                return False
            else:
                self.holdings.append(leg)

        # remove 0 qty items
        self.holdings = [ h for h in self.holdings if h.get_attr(Gl.QUANTITY) != 0]
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
            order_type = buy_type if leg.get_attr(Gl.QUANTITY) > 0 else sell_type
            leg.set_attr(Gl.ORDER_TYPE, order_type)

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
        * find the assets that are rolling 
        * carry over the chainid for order_chain and +1 roll_count
        Args:
            transaction : A transaction object containing a list of transaction legs.
        """
        noclose: bool = True
        for leg in transaction.legs:

            leg_found_in_holding: bool = False
            for holding in self.holdings:
                if holding.get_attr(Gl.SYMBOL) == leg.get_attr(Gl.SYMBOL):
                    leg_found_in_holding = True
                    if holding.get_attr(Gl.QUANTITY) < 0:
                        if leg.get_attr(Gl.QUANTITY) > 0:
                            leg.set_attr(Gl.ORDER_TYPE, Gl.BUY_TO_CLOSE)
                            noclose = False
                        else:
                            leg.set_attr(Gl.ORDER_TYPE, Gl.SELL_TO_OPEN)
                    else:
                        if leg.get_attr(Gl.QUANTITY) < 0:
                            leg.set_attr(Gl.ORDER_TYPE, Gl.SELL_TO_CLOSE)
                            noclose = False
                        else:
                            leg.set_attr(Gl.ORDER_TYPE, Gl.BUY_TO_OPEN)
            if leg_found_in_holding:
                continue
            if leg.get_attr(Gl.QUANTITY) > 0:
                leg.set_attr(Gl.ORDER_TYPE, Gl.BUY_TO_OPEN)
            else:
                leg.set_attr(Gl.ORDER_TYPE, Gl.SELL_TO_OPEN)


        if noclose:
            warn(f"Roll of transaction chain missing closure order")
            return False

        return self.execute_transaction(transaction)


    def calculate_pnl(self, current_prices):
        """Calculates the Profit and Loss (PnL) of the portfolio."""
        pnl = 0.0
        for holding in self.holdings:
            symbol = holding.get_attr(Gl.SYMBOL)
            if symbol in current_prices:
                qty = holding.get_attr(Gl.QUANTITY)
                current_value = qty * current_prices[symbol]
                initial_value = qty * holding.get_attr(Gl.AVERAGE_OPEN_PRICE)
                pnl += current_value - initial_value
            else: 
                print(f"Warning: No current price found for {symbol}.")
        return pnl

    def get_portfolio_value(self, current_prices: dict) -> float:
        """Calculates the total value of the portfolio, including cash."""
        total_value = self.cash_balance
        for holding in self.holdings:
            symbol = holding.get_attr(Gl.SYMBOL)
            if symbol in current_prices:
                qty = holding.get_attr(Gl.QUANTITY)
                total_value += qty * current_prices[symbol]
            else: 
                print(f"Warning: No current price found for {holding.symbol}.")

        return total_value  
    
    def clear_log(self):
        """Clears the transaction log."""
        self.transactions_log.clear_log()


    def print_portfolio(self):
        """Prints the current portfolio holdings."""
        print("____ Current Portfolio ____")
        print(f"Cash Balance: ${self.cash_balance:.2f}")
        df = pd.DataFrame([h.serialize(for_json=True) for h in self.holdings], index=None)
        # borrow show_columns from the logger
        if df.empty:
            print("No holdings")
        else:
            print_tabulate(df=df, cols=self.transactions_log.show_columns)

    
    def print_transactions(self):
        self.transactions_log.print_transactions()

    def print_order_chains(self):
        """ prints order chains. """
        chainids = list(self.transactions_dict.keys())
        chainids.sort()
        print("____ Order Chains ____")
        for chainid in chainids:
            print(f"\tOrder chain: {chainid}")
            txlegs = self.transactions_dict[chainid]
            if chainid in self.order_chains:
                txlegs.extend(self.order_chains[chainid])
            df = pd.DataFrame([h.serialize(for_json=True) for h in txlegs], index=None)
            # borrow show_columns from the logger
            print_tabulate(df=df, cols=self.transactions_log.show_columns)



