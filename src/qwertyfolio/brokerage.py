"""
This is a stub module for a brokerage integration

"""
from .globals import Gl
from .assets import Asset

class OurBrokerAPI:
    """
    empty shell of a brokerage API handler
    """
    def __init__(self):
        pass

    def submit_order(self, brokerdata: dict) -> dict[str:float]:
        # our API to the broker to make an order
        transary: list = brokerdata['LEGS']
        ret: dict[str:float] = {}

        ## in this mock, we will reduce the price by 2% for everything
        for leg in transary:
            print(f"BROKER_API: {leg['symbol']} {leg['order_type']} {leg['price']} {leg['quantity']}")
            ret[leg['symbol']] = leg['price'] * 0.98
        
        # if broker fails - return None
        print("BROKER_API: says OK")
        return ret

    def get_positions(self) -> list:
        print("BROKER_API: getting positions")
        return []
        

class MyBroker:    
    """
    empty shell of a brokerage integration
    """
    
    def __init__(self):
        self.brokerapi = OurBrokerAPI()


    def get_positions(self) -> list[Asset]:
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
        position_list = self.brokerapi.get_positions()
        for i,position in enumerate(position_list):
            position_list[i] = Asset(**position)
        return position_list

    def get_quotes(self, symbols):
        return {}

    def execute_transaction(self, trans_dict: dict[str:dict[str,any]]) -> bool:
        """
        HOOK: called by qwertyfolio.core.update_holdings()
        This forwards the transactions to the broker for execution
        the broker needs to update with the market prices of execution

        trans_dict needs to be modified with the broker meta data response

        Args:
            trans_dict : dictionary of [ symbol : [ price ]]
        Returns:
            bool

        trans_dict is updated in place for the result trade prices 
        """
        mytransaction : list[dict[str,any]] = []
        net_price: float = 0.0
        for symbol in trans_dict.keys(): 
            net_price += trans_dict[symbol][Gl.PRICE] * trans_dict[symbol][Gl.QUANTITY]
            record = { 
                'symbol':symbol,
                'order_type': trans_dict[Gl.ORDER_TYPE],
                'price': trans_dict[symbol][Gl.PRICE],
                'quantity': trans_dict[symbol][Gl.QUANTITY] 
            }
            mytransaction.append(record)
        # mutate our transaction to fit our broker API
        result = self.brokerapi.submit_order({'LIMIT': net_price, 'LEGS': mytransaction})
        if not result:
            trans_dict[Gl.ERROR] = "__ This is Broker Error String __"
            return False
        # update the market prices from result
        for symbol in result.keys():
            trans_dict[symbol][Gl.PRICE] = result[symbol]   
        return True




