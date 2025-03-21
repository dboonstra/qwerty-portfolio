import pandas as pd
from typing import Dict, List
from .assets import Asset
from .globals import Gl
from .core import PortfolioManager
from .utils import warn


class MarginCalculator:
    """
    Calculates the buying power reduction (margin requirements) for a portfolio of assets.
    """

    def __init__(self, portfolio_manager: PortfolioManager):
        """
        Initializes the MarginCalculator with a PortfolioManager instance.

        Args:
            portfolio_manager: The PortfolioManager instance containing the portfolio holdings.
        """
        self.portfolio_manager = portfolio_manager
        self.holdings: List[Asset] = portfolio_manager.holdings
        self.margin_requirements: Dict[str, float] = {}

    def calculate_margin_requirements(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        Calculates the margin requirements for each asset in the portfolio.

        Args:
            current_prices: A dictionary mapping asset symbols to their current prices.

        Returns:
            A dictionary mapping asset symbols to their margin requirements.
        """
        self.margin_requirements = {}
        for holding in self.holdings:
            symbol = holding.get_attr(Gl.SYMBOL)
            asset_type = holding.get_attr(Gl.ASSET_TYPE)
            quantity = holding.get_attr(Gl.QUANTITY)
            price = current_prices.get(symbol)
            if price is None:
                warn(f"Warning: No current price found for {symbol}. Skipping margin calculation.")
                continue

            if asset_type == Gl.EQUITY:
                self.margin_requirements[symbol] = self._calculate_equity_margin(quantity, price)
            elif asset_type in [Gl.CALL, Gl.PUT]:
                self.margin_requirements[symbol] = self._calculate_option_margin(holding, quantity, price)
            elif asset_type == Gl.MONEY:
                self.margin_requirements[symbol] = 0.0
            else:
                warn(f"Warning: Unknown asset type {asset_type} for {symbol}. Skipping margin calculation.")

        return self.margin_requirements

    def _calculate_equity_margin(self, quantity: float, price: float) -> float:
        """
        Calculates the margin requirement for an equity position.

        For long positions, it's typically 50% of the total value.
        For short positions, it's typically 50% of the total value.

        Args:
            quantity: The quantity of the equity held.
            price: The current price of the equity.

        Returns:
            The margin requirement for the equity position.
        """
        total_value = abs(quantity) * price
        margin_requirement = total_value * 0.5  # 50% margin requirement
        return margin_requirement

    def _calculate_option_margin(self, holding: Asset, quantity: float, price: float) -> float:
        """
        Calculates the margin requirement for an option position.

        This is a simplified model and may not reflect all real-world scenarios.
        Covered calls and cash-secured puts are handled differently.

        Args:
            holding: The Asset object representing the option.
            quantity: The quantity of the option contracts held.
            price: The current price of the option.

        Returns:
            The margin requirement for the option position.
        """
        option_type = holding.get_attr(Gl.ASSET_TYPE)
        underlying_symbol = holding.get_attr(Gl.UNDERLYING_SYMBOL)
        strike_price = holding.get_attr(Gl.STRIKE_PRICE)
        multiplier = holding.get_attr(Gl.MULTIPLIER)

        # Check if underlying is held in portfolio
        underlying_holding = self.portfolio_manager.find_holding(Gl.SYMBOL, underlying_symbol)
        underlying_quantity = 0
        if len(underlying_holding) > 0:
            underlying_quantity = underlying_holding[0].get_attr(Gl.QUANTITY)

        if quantity > 0:  # Long option
            # Long options typically don't have margin requirements, only the premium paid.
            return 0.0
        elif quantity < 0:  # Short option
            if option_type == Gl.CALL:
                # Short call
                if underlying_quantity >= abs(quantity) * multiplier:
                    # Covered call: No margin required beyond the underlying stock's margin
                    return 0.0
                else:
                    # Naked call: Margin is typically 20% of the underlying value + option out of the money amount - premium
                    underlying_price = self.portfolio_manager.broker.get_quotes([underlying_symbol]).get(underlying_symbol, 0)
                    if underlying_price == 0:
                        warn(f"Warning: No current price found for underlying {underlying_symbol}. Using 0 for margin calculation.")
                    out_of_money = max(0, strike_price - underlying_price)
                    margin = (0.2 * underlying_price * multiplier * abs(quantity)) + (out_of_money * multiplier * abs(quantity)) - (price * multiplier * abs(quantity))
                    return margin
            elif option_type == Gl.PUT:
                # Short put
                if self.portfolio_manager.cash_balance >= strike_price * multiplier * abs(quantity):
                    # Cash-secured put: No margin required beyond the cash set aside
                    return 0.0
                else:
                    # Naked put: Margin is typically 20% of the underlying value - option out of the money amount - premium
                    underlying_price = self.portfolio_manager.broker.get_quotes([underlying_symbol]).get(underlying_symbol, 0)
                    if underlying_price == 0:
                        warn(f"Warning: No current price found for underlying {underlying_symbol}. Using 0 for margin calculation.")
                    out_of_money = max(0, underlying_price - strike_price)
                    margin = (0.2 * underlying_price * multiplier * abs(quantity)) + (out_of_money * multiplier * abs(quantity)) - (price * multiplier * abs(quantity))
                    return margin
        return 0.0

    def calculate_total_margin_requirement(self, current_prices: Dict[str, float]) -> float:
        """
        Calculates the total margin requirement for the entire portfolio.

        Args:
            current_prices: A dictionary mapping asset symbols to their current prices.

        Returns:
            The total margin requirement for the portfolio.
        """
        self.calculate_margin_requirements(current_prices)
        return sum(self.margin_requirements.values())

    def print_margin_details(self, current_prices: Dict[str, float]):
        """
        Prints a detailed breakdown of the margin requirements for each asset.

        Args:
            current_prices: A dictionary mapping asset symbols to their current prices.
        """
        self.calculate_margin_requirements(current_prices)
        print("____ Margin Requirements ____")
        if not self.margin_requirements:
            print("No margin requirements found.")
            return

        margin_data = []
        for holding in self.holdings:
            symbol = holding.get_attr(Gl.SYMBOL)
            margin = self.margin_requirements.get(symbol, 0.0)
            margin_data.append({
                Gl.SYMBOL: symbol,
                Gl.QUANTITY: holding.get_attr(Gl.QUANTITY),
                "Price": current_prices.get(symbol, "N/A"),
                "Margin Requirement": margin
            })

        df = pd.DataFrame(margin_data)
        from .utils import print_tabulate
        print_tabulate(df, title="Margin Details")
        print(f"Total Margin Requirement: {self.calculate_total_margin_requirement(current_prices):.2f}")
