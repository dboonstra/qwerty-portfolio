

class Gl:
    
    """Class of term strings"""
    # order actions
    BUY_TO_OPEN = "Buy to Open"
    BUY_TO_CLOSE = "Buy to Close"
    SELL_TO_OPEN = "Sell to Open"
    SELL_TO_CLOSE = "Sell to Close"

    # asset types
    CALL = "C"
    PUT = "P"
    EQUITY = "S"
    MONEY = "M"

    # symbol for cash in portfolio transactions
    CASH_SYMBOL = "_CASH"

    # Attribute names of Asset objects
    TIME_STAMP = 'timestamp'
    SYMBOL = 'symbol'
    QUANTITY = 'quantity'
    PRICE = 'price'
    AVERAGE_OPEN_PRICE = 'average_open_price'
    ASSET_TYPE = 'asset_type'
    UNDERLYING_SYMBOL = 'underlying_symbol'
    MULTIPLIER = 'multiplier'
    DAYS_TO_EXPIRATION = 'days_to_expiration'
    EXPIRES_AT = 'expires_at'
    STRIKE_PRICE = 'strike_price'
    DELTA = 'delta'
    GAMMA = 'gamma'
    THETA = 'theta'
    QUOTE_DATE = 'quote_date'
    ORDER_TYPE = 'order_type'
    CHAINID = 'chainid'
    ROLL_COUNT = 'roll_count'
