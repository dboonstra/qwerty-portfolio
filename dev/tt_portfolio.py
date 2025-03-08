#!/usr/bin/env python3
"""
TODO
- export positions with SimPortfolio
- find "Working" orders 

"""
import sys
sys.path.insert(0, '../')
import datetime
import json
from tabulate import tabulate
from datetime import timedelta

from tasty_algo.tasty_api import TastyApi
import tasty_algo.utils as tau
import tastytrade.utils as tu

def pjson(data, indent: int = 4):
    print(json.dumps(data, indent=indent))

def warn(*a):
    print(*a, file=sys.stderr)


from dataclasses import dataclass
from typing import Optional
from datetime import datetime


def get_positions(tasty_api: TastyApi):
    """
    Converts position data to a list of dictionaries, excluding specified columns.
    Sorts a list of position dictionaries by their 'symbol' key.
    Extracts set of unique underlying symbols from a list of processed positions.

    Args:
        positions (list): List of position data objects.
        columns_to_exclude (list): List of column names to exclude.

    Returns:
        list: A list of dictionaries representing positions, with excluded columns removed.
    """
    # Define columns to exclude from the output
    exclude: list = [
        'account_number',
        'instrument_type',
        'is_frozen',
        'is_suppressed',
        'fixing_price',
        'deliverable_type',
        'restricted_quantity',
        'mark',
        'mark_price',
        'cost_effect',
        'realized_day_gain',
        'realized_today',
        'created_at',
        'realized_day_gain_date',
        'realized_today_date',
        'average_yearly_market_close_price',
        'average_daily_market_close_price',
        'updated_at',
        'close_price',
    ]
    positions = tasty_api.positions()
    unique_underlying_symbols = set()

    processed_positions = [dict(position) for position in positions]
    for position in processed_positions:
        if "underlying_symbol" in position:
            unique_underlying_symbols.add(position["underlying_symbol"])
        for column in exclude:
            if column in position:
                del position[column]
        # give quantity a sign
        if position['quantity_direction'] == 'Short':
            position['quantity'] *= -1
        del position['quantity_direction']

    sorted_positions =  sorted(processed_positions, key=lambda x: x['symbol'])

    order_chains: list = []
    for symbol in unique_underlying_symbols:
        order_chains.extend(get_order_chains(tasty_api, symbol))

    # Merge order_chains with sorted_positions based on symbol and quantity
    # primary cause it to setup chainid for ROLL transactions
    merged_positions = []
    chainid: int = 1000
    chainidcache: dict = {}
    for position in sorted_positions:
        nomatch: bool = True

        # set asset type
        if len(position['symbol']) < 7:
            position['asset_type'] = 'S'
        else:
            s = position['symbol']
            position['asset_type'] = s[12] # P or C

        # merge order chains in 
        for order in order_chains:
            if 'quantity_numeric' in order:
                order['quantity'] = order['quantity_numeric']
                del order['quantity_numeric']
            if 'quantity_type' in order:
                del order['quantity_type']

            if order['symbol'] == position['symbol']:
                nomatch = False
                if float(order['quantity']) == float(position['quantity']):
                    position.update(order)
                    merged_positions.append(position)
                else:
                    # If symobol is split by orders, we can have multiple
                    # order chainids for the full lot 
                    # but here we go down to one 
                    warn(f"get_positions: Merge portfolio Qty != Qty : {position['symbol']}")
                    position.update(order)
                    break
        # # missing from order chain : (  must fudge some things
        if nomatch:
            warn(f"get_positions: Missing from order chain : {position['symbol']}")
            chainid += 1 
            chainidstr = position['underlying_symbol'] + str(position['expires_at'])
            if chainidstr in chainidcache:
                chainidx = chainidcache[chainidstr]
            else:
                chainidcache[chainidstr] = chainid
                chainidx = chainid

            myorder: dict = {"roll_count":0, "chainid":chainidx}
            myorder['instrument_type'] = 'Equity Option' if len(position['symbol']) > 6 else 'Equity'
            position.update(myorder)

    return sorted_positions




def get_order_chains(tapi, underlying_symbol: str) -> list:
    end = tu.today_in_new_york()
    beg = end - timedelta(days=360)

    order_chains = tapi.account.get_order_chains(tapi.session, underlying_symbol, beg, end)
    ret: list = []
    for order_chain in order_chains:
        chainid = order_chain.id
        data = order_chain.computed_data
        rolls = data.roll_count
        entry_models = data.open_entries
        for entry_model in entry_models:
            entry = tau.flatten_model(entry_model)
            entry['chainid'] = chainid
            entry['roll_count'] = rolls
            entry['underlying_symbol'] = underlying_symbol
            ret.append(entry)
    return ret






def main():
    # Initialize Tasty API
    tasty_api = TastyApi()

    # Fetch positions from the API
    sorted_positions = get_positions(tasty_api)


    # Print the table of positions
    print("All Positions:")
    print(tabulate(sorted_positions, headers='keys', tablefmt='fancy_grid'))



if __name__ == "__main__":
    main()
