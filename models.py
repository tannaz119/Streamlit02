class Asset:
    """
    Represents an asset in the portfolio.
    """
    def __init__(self, id=None, name="", asset_type="", quantity=0, 
                 avg_buy_price=0, current_price=0, last_updated=None):
        self.id = id
        self.name = name
        self.asset_type = asset_type
        self.quantity = quantity
        self.avg_buy_price = avg_buy_price
        self.current_price = current_price
        self.last_updated = last_updated
    
    @property
    def total_value(self):
        """Calculate the total value of the asset."""
        return self.quantity * self.current_price
    
    @property
    def profit_loss(self):
        """Calculate the profit or loss for the asset."""
        return self.quantity * (self.current_price - self.avg_buy_price)
    
    @property
    def profit_loss_percentage(self):
        """Calculate the profit or loss percentage for the asset."""
        if self.avg_buy_price > 0:
            return ((self.current_price - self.avg_buy_price) / self.avg_buy_price) * 100
        return 0


class Trade:
    """
    Represents a trade in the trading journal.
    """
    def __init__(self, id=None, trade_date=None, asset_name="", asset_type="",
                 trade_type="", quantity=0, price=0, total_amount=0, 
                 profit_loss=0, notes="", created_at=None):
        self.id = id
        self.trade_date = trade_date
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.trade_type = trade_type
        self.quantity = quantity
        self.price = price
        self.total_amount = total_amount
        self.profit_loss = profit_loss
        self.notes = notes
        self.created_at = created_at


class CashBalance:
    """
    Represents the cash balance in the portfolio.
    """
    def __init__(self, amount_irr=0, amount_usd=0, last_updated=None):
        self.amount_irr = amount_irr
        self.amount_usd = amount_usd
        self.last_updated = last_updated


class Strategy:
    """
    Represents a portfolio management strategy.
    """
    def __init__(self, id=None, name="", description="", asset_allocation="",
                 risk_level="", created_at=None, last_updated=None):
        self.id = id
        self.name = name
        self.description = description
        self.asset_allocation = asset_allocation
        self.risk_level = risk_level
        self.created_at = created_at
        self.last_updated = last_updated
