"""
This is a stub module for a brokerage integration

"""
from .globals import Gl
from .assets import Asset
from .exceptions import BrokerError

from abc import ABC, abstractmethod

class BrokerAPI(ABC):

    @abstractmethod
    def get_holdings(self) -> list[Asset]:
        pass

    @abstractmethod
    def execute_transaction(self, trans_dict: dict[str:dict[str,any]]) -> bool:
        pass


class OurBroker(BrokerAPI):
    """
    empty shell of a brokerage integration
    """
    
    def __init__(self):
        pass

    def get_quotes(self, symbols):
        return {}

    def get_holdings(self) -> list[Asset]:
        """
        HOOK: called by qwertyfolio.core.init()
        This initiates holdings from the broker
        instead of portfolio.json

        Args:
            None
        Returns:
            list[Asset]
        """
        print("Getting positions from broker API")
        # add in chainids if you have them 
        # mutate return to Asset class
        position_list = [ {Gl.SYMBOL:'DELL', Gl.QUANTITY: 42, Gl.PRICE: 1.99}  ]

        for i,position in enumerate(position_list):
            position_list[i] = Asset(**position)
        return position_list

    def execute_transaction(self, transaction_list: list[Asset]) -> list[Asset]:
        """
        HOOK: called by qwertyfolio.core._update_holdings() 
        This forwards the transactions to the broker for execution
        Upon success, this will need to update Assets 
        with the transaction market prices and quantities of execution


        Args:
            transaction_list: list[Asset]
        Returns:
            bool

        trans_dict is updated in place for the result trade prices 
        """

        for leg in transaction_list:
            # for this stub, we will slip the price 0.04 for each leg
            leg.set_attr(Gl.PRICE, leg.get_attr(Gl.PRICE) - 0.04)
            # throw an error for testing
            if leg.get_attr(Gl.SYMBOL) == 'BREAK':
                raise BrokerError("BREAK symbol found - aborting") 
        return transaction_list



