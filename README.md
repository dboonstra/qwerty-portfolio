# qwertyfolio: A Simulated Portfolio Management Tool

`qwertyfolio` is a Python module designed for simulating and managing a stock and options portfolio. It provides a framework for tracking holdings, executing transactions, calculating profit and loss (PnL), and maintaining a detailed transaction history. `qwertyfolio` can be used for educational purposes, algorithmic trading development, or testing investment strategies without real-world financial risk.  Brokerage integration is provided to smooth transition from back-testing, to forward-testing, to live transactions.

## Features

-   **Portfolio Management:** Track stock and option holdings, including quantity, average open price, and current value.
-   **Transaction Execution:** Execute buy/sell transactions (open, close, and roll) with support for multiple legs per transaction.
-   **Cash Management:** Simulate cash balances and update them through transactions.
-   **PnL Calculation:** Calculate the Profit and Loss of the portfolio based on current market prices.
-   **Transaction Logging:** Maintain a detailed log of all transactions, including timestamps, symbols, order types, prices, and quantities.
-   **Order Chains:** Group transactions into chains to provide a history of related trades.
-   **Brokerage Integration (Mock):**  Includes a basic framework for integration with a brokerage API, allowing for the simulation of real-world order execution.
-   **Persistence:** Save and load portfolio data from JSON files and transaction history from CSV files.
-   **Flexibility:** Customize the columns displayed in portfolio and transaction outputs.
- **Asset Class:**  Use Asset class to manage details of each holding
- **Transaction Class:** Use Transaction class to manage each transaction (buy/sell/roll) and the legs involved

## Installation

To use `qwertyfolio`, you will need Python 3.8+ installed.

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd qwerty-portfolio
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```
    The `requirements.txt` contains `pandas`, `numpy` and `tabulate`

## Usage

### Core Components

-   **`PortfolioManager`:** The main class for managing the portfolio.
-   **`Transaction`:** Represents a transaction, which can include multiple legs (assets).
-   **`Asset`:** Represents an asset within the portfolio, including stocks, options, or cash.
-   **`TransactionLogger`:** Handles the logging of transactions to a CSV file.
-   **`MyBroker` (Optional):** A mock brokerage integration for simulating real-world order execution.
- **`Gl` (globals)** : Global constants for assets, order types, and attributes
- **`utils`** : Helper functions

### Basic Example

Here's a simple example demonstrating how to create a portfolio, execute a transaction, and view the portfolio:

```python
from qwertyfolio.core import PortfolioManager
from qwertyfolio.transaction import Transaction
from qwertyfolio.assets import Asset
from qwertyfolio.globals import Gl
from qwertyfolio.brokerage import MyBroker

# Initialize the portfolio manager with a new portfolio
# use a broker API
port_file = 'portfolio.json'
transaction_file = 'transaction_log.csv' 
pm = PortfolioManager(port_file, transaction_file, new_portfolio=True)
# ... or with broker integration
mybroker = ourBroker()
pm = PortfolioManager(port_file, transaction_file, new_portfolio=True, 
    brokerage=broker, use_brokerage_holdings=False, use_brokerage_transactions=True)

# Add cash to the portfolio
pm.update_cash_balance(10000)

# Create a transaction to buy 10 shares of AAPL at $150 each
transaction = Transaction(legs=[Asset(symbol="AAPL", quantity=10, price=150)])

# Execute the transaction as an opening trade
pm.execute_open(transaction)

# Create a transaction to sell 5 shares of AAPL at $160 each
transaction2 = Transaction(legs=[Asset(symbol="AAPL", quantity=-5, price=160)])

# Execute the transaction as an opening trade
pm.execute_open(transaction2)

# Print the current portfolio
pm.print_portfolio()

# Print the transaction history
pm.print_transactions()

# Print the order chains
pm.print_order_chains()

# Get Portfolio Value
current_prices = {"AAPL": 165.0}
print(f"Portfolio Value: {pm.get_portfolio_value(current_prices)}")

# Get the calculated PNL
print(f"PNL: {pm.calculate_pnl(current_prices)}")

```

### Explanation
1. Initialization:

    - PortfolioManager(new_portfolio=True) creates a new empty portfolio.
    - broker = MyBroker() create a mock broker API
    - brokerage=broker, use_brokerage_transactions=True tells the portfolio manager to use a broker and to simulate broker calls to execute transactions.
    - portfolio_file and transaction_log_file are used to load/save portfolio and log data. Default files are simulated_portfolio.json and transaction_log.csv.
    - use_brokerage_holdings=True will use the Broker API to load holdings at initialization.

2. Cash Management:

    - pm.update_cash_balance(10000) adds $10,000 to the cash balance.
    - pm.update_cash_balance(-5000) removes $5,000 from the cash balance.

3. Creating Transactions:


    - Transaction(legs=[Asset(symbol="AAPL", quantity=10, price=150)]) creates a transaction object to buy 10 shares of AAPL at $150.
    - Transaction(legs=[Asset(symbol="AAPL", quantity=-5, price=160)]) creates a transaction object to sell 5 shares of AAPL at $160.

legs are a list of Asset objects. Asset contains symbol, quantity, price, order_type and other attributes.
The Asset class has utility to get/set other attributes

4. Executing Transactions:

    - pm.execute_open(transaction) executes the transaction as an "open" trade (either BUY_TO_OPEN or SELL_TO_OPEN).
    - pm.execute_close(transaction) executes the transaction as a "close" trade (either BUY_TO_CLOSE or SELL_TO_CLOSE).
    - pm.execute_roll(transaction) executes the transaction as a "roll" trade (mix of close and open).
    - pm.execute_transaction(transaction) will detect the order_type of each leg and then execute. The broker will be called, for each transaction if use_brokerage_transactions=True.

5. Viewing the Portfolio:

    - pm.print_portfolio() displays the current holdings.
    - pm.print_transactions() displays the transaction log.
    - pm.print_order_chains() displays the transactions grouped by order chains.
    - pm.get_portfolio_value(current_prices) shows the total value of the portfolio
    - pm.calculate_pnl(current_prices) shows the PNL of the portfolio

### Other Usage Considerations
* _Loading an Existing Portfolio:_ Omit new_portfolio=True when initializing PortfolioManager to load an existing portfolio from portfolio_file. If no file exists, it will start fresh.

* _Brokerage Integration:_ The MyBroker class provides a template for integrating with a real brokerage API. You can extend this class to add functionality.

    - Implement get_holdings to load holdings from the broker
    -  Implement execute_transaction to simulate market execution of orders.

* _Holdings from Broker:_ When use_brokerage_holdings=True is passed to the PortfolioManager, it will use the get_holdings() method of the broker to load the current assets. If the get_holdings() method does not exist in your broker implementation an error is thrown.

* _Transactions from Broker:_ When use_brokerage_transactions=True is passed to the PortfolioManager, it will use the execute_transaction() method of the broker to simulate execution. If the execute_transaction() method does not exist in your broker implementation an error is thrown.

* _Customization:_ You can customize the columns shown in the portfolio and transaction logs by using the transactions_log object and the update_show_columns and update_log_columns functions.

    - pm.transactions_log.update_show_columns(["symbol", "quantity", "price"]) to change the columns in print_portfolio and print_order_chains
    - pm.transactions_log.update_log_columns(["symbol", "quantity", "order_type", "chainid"]) to change the columns in the saved transaction_log_file

* _Finding Holdings:_ The method pm.find_holding("symbol", "AAPL") can be used to filter holdings to search. The returned result is a list[Asset].


    - pm.find_holding("symbol", "AAPL", not_in=True) will find everything NOT AAPL.
    - pm.find_holding("chainid", 2) will find all assets in chainid 2.
    - pm.find_holding("chainid", 2, filter=pm.find_holding("symbol", "AAPL")) will search for chainid 2 but only within the AAPL assets.

* _Clearing Transaction Log:_ pm.clear_log() will clear the transaction log, which will be empty next time it is accessed.

### Advanced Features
* _Multiple Legs:_ Create transactions with multiple legs for complex options strategies.

``` python 
# Example of a multi-leg transaction (e.g., a covered call)
covered_call = Transaction(legs=[
  Asset(symbol="AAPL", quantity=100, price=165.0),   # Buy 100 shares of AAPL
  Asset(symbol="AAPL240119C00180000", quantity=-1, price=5.0, order_type=Gl.SELL_TO_OPEN, multiplier=100) # Sell 1 AAPL call option
])

pm.execute_open(covered_call)
```

* _Order Chains:_ Track related transactions using the chainid to organize complex trades.

The transaction class has a chainid which is auto-incremented. print_order_chains() will display all the chains.

* _Roll Transactions:_ Roll existing positions using the execute_roll method.
execute_roll assumes at least one leg of the transaction is in the existing holdings.
if no asset is found in the holdings, the transaction will fail.

execute_roll will attempt to set the proper order type, between BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE.

example:
``` python 
# continue from covered_call above
# create a new transaction to close the current covered call and roll to a new call
roll_covered_call = Transaction(legs=[
    Asset(symbol="AAPL", quantity=-100, price=170),   # Sell 100 shares of AAPL
    Asset(symbol="AAPL240119C00180000", quantity=1, price=10.0, multiplier=100), # Buy back 1 AAPL call option
    Asset(symbol="AAPL240216C00190000", quantity=-1, price=6.0, multiplier=100) # Sell 1 new AAPL call option
  ])
pm.execute_roll(roll_covered_call)
```

* _Transaction Object:_ If you need to debug a transaction, you can examine the legs individually by looking at transaction.legs. The Transaction class also contains a timestamp, chainid, and roll_count.

* _Error Handling:_ The Portfolio Manager will return True or False when running execute_open, execute_close, or execute_roll. If there was an error with the transaction, it will return False.

* _Brokerage Errors:_ If the Broker API fails, it will also return False and leave a message in the trans_dict of the broker's execute_transaction() call with the key Gl.ERROR.

* _Globals:_ Transaction meta data requires a number of string keyed fields such as 'order_type' or 'symbol'. qwertyfoio.globals.y details these and may be overridden to fit different incoming data sources.

## Contributing
Contributions to qwertyfolio are welcome! Please feel free to submit pull requests or open issues to discuss new features or bug fixes.

## License
This project is licensed under the GNU GENERAL PUBLIC LICENSE.


