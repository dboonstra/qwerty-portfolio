#!/bin/env python3 
import json
import os
import sys
import datetime
from typing import Optional, List, ClassVar
import pandas as pd
from collections import defaultdict

sys.path.insert(0,'src')
sys.path.insert(0,'../src')

from qwertyfolio import TransactionLeg
from qwertyfolio import Transaction
from qwertyfolio import PortfolioManager
from qwertyfolio import DEBUG

DEBUG = True
port_file = 'portfolio.json'
transaction_file = 'transaction_log.csv' 

def main():
    # Example Usage
    clear_files()
    portfolio = PortfolioManager(port_file, transaction_file)
    portfolio.deposit_cash(10000)
    test_roll(portfolio)
    test_close(portfolio)
    
def clear_files():
    if os.path.exists(port_file):
        os.remove(port_file)
    if os.path.exists(transaction_file):
        os.remove(transaction_file)


def test_roll(portfolio):

    # # buy option test case
    # transaction0 = Transaction(legs=[TransactionLeg("SPY   250411C00450000", 1, 2, "sto")])
    # portfolio.execute_transaction(transaction0)

    transaction1 = Transaction(legs=[TransactionLeg("SPY   250411C00440000", 1, 3, "sto")])
    portfolio.execute_transaction(transaction1)


    # roll
    transaction10 = Transaction(legs=[
        TransactionLeg("SPY   250411C00440000", 1, 2, "btc"),
        TransactionLeg("SPY   250411C00430000", 1, 1, "sto"),
        ])
    portfolio.execute_transaction(transaction10)

    # roll
    transaction10 = Transaction(legs=[
        TransactionLeg("SPY   250411C00430000", 1, 2, "btc"),
        TransactionLeg("SPY   250411C00420000", 1, 1, "sto"),
        ])
    portfolio.execute_transaction(transaction10)

def test_misc(portfolio):
    # buy option test case
    transaction0 = Transaction(legs=[TransactionLeg("SPY   250411C00450000", 1, 450, "bto",'C','Equity Option')])
    portfolio.execute_transaction(transaction0)

    # Buy 10 shares of AAPL at $150
    # transaction1 = Transaction(legs=[TransactionLeg("AAPL", 10, 150, "bto",'S','Equity')])
    transaction1 = Transaction(legs=[TransactionLeg("AAPL", 10, 150, "bto")])
    portfolio.execute_transaction(transaction1)

    if True:

        # Buy 5 shares of MSFT at $300
        transaction2 = Transaction(legs=[TransactionLeg("MSFT", 5, 300, "bto",'S','Equity')])
        portfolio.execute_transaction(transaction2)

        # Sell 5 shares of AAPL at $160
        transaction3 = Transaction(legs=[TransactionLeg("AAPL", -5, 160, "stc", 'S', 'Equity')])
        portfolio.execute_transaction(transaction3)

        # Short sell 2 shares of TSLA at $800 (sell to open)
        transaction4 = Transaction(legs=[TransactionLeg("TSLA", -2, 800, "sto", 'S', 'Equity')])
        portfolio.execute_transaction(transaction4)

        # Buy to close 1 share of the short at $750
        transaction5 = Transaction(legs=[TransactionLeg("TSLA", 1, 750, "btc",'S','Equity')])
        portfolio.execute_transaction(transaction5)

        # Short sell 3 GME at 200
        transaction6 = Transaction(legs=[TransactionLeg("GME", -3, 200, "sto", 'S','Equity')])
        portfolio.execute_transaction(transaction6)

        # Buy to close 3 GME at 150
        transaction7 = Transaction(legs=[TransactionLeg("GME", 3, 150, "btc", 'S','Equity')])
        portfolio.execute_transaction(transaction7)


        # buy option
        transaction8 = Transaction(legs=[TransactionLeg("SPY   250404C00450000", 1, 450, "bto",'C','Equity Option')])
        portfolio.execute_transaction(transaction8)


        # open another option
        transaction9 = Transaction(legs=[TransactionLeg("GOOG  250404P00564000", 1, 200, "bto",'P','Equity Option')])
        portfolio.execute_transaction(transaction9)
        

        # roll
        transaction10 = Transaction(legs=[
            TransactionLeg("GOOG  250404P00564000", -1, 200, "stc",'P','Equity Option'),
            TransactionLeg("GOOG  250504P00561000", 1, 100, "bto",'P','Equity Option'),
            ])
        portfolio.execute_transaction(transaction10)

def test_close(portfolio):
    portfolio.withdraw_cash(1000) # withdraw cash
    current_prices = {"AAPL": 165, "MSFT": 310, "TSLA": 700, "GME": 140, 'SPY  250404C00450000': 470, "GOOG  250504P00564000": 110}

    print(f"Portfolio Value: {portfolio.get_portfolio_value(current_prices)}")
    print(f"Portfolio PnL: {portfolio.calculate_pnl(current_prices)}")
    print()
    portfolio.print_portfolio()
    print()
    portfolio.print_transactions()
    print()
    portfolio.print_order_chains()

if __name__ == "__main__":
    main()
