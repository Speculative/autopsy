"""
Order Fulfillment Pipeline

Bug: Shallow copy of shipping profiles causes nested 'options' dict to be
shared between the profile template and computed shipping configs. When
handling rules modify options, they permanently contaminate the profile.
"""

import random
import autopsy

SHIPPING_PROFILES = {
    "standard": {
        "carrier": "usps",
        "method": "ground",
        "options": {"tracking": True, "signature": False, "insurance": False}
    },
    "premium": {
        "carrier": "fedex",
        "method": "air",
        "options": {"tracking": True, "signature": True, "insurance": True}
    }
}


class ShippingCalculator:
    def __init__(self):
        self.profiles = SHIPPING_PROFILES
    
    def calculate(self, order: dict) -> dict:
        tier = order.get("tier", "standard")
        shipping = self.profiles[tier].copy()
        self._apply_handling_rules(shipping, order)
        return shipping
    
    def _apply_handling_rules(self, shipping: dict, order: dict) -> None:
        if order.get("fragile"):
            shipping["options"]["insurance"] = True
            shipping["options"]["careful_handling"] = True
        if order.get("perishable"):
            shipping["options"]["refrigerated"] = True
            shipping["method"] = "air"


class OrderProcessor:
    def __init__(self):
        self.calculator = ShippingCalculator()
    
    def process(self, order: dict) -> dict:
        shipping = self.calculator.calculate(order)
        cost = self._compute_cost(shipping)
        autopsy.log(cost)
        return {
            "order_id": order["id"],
            "tier": order.get("tier", "standard"),
            "fragile": order.get("fragile", False),
            "perishable": order.get("perishable", False),
            "shipping": shipping,
            "cost": cost
        }
    
    def _compute_cost(self, shipping: dict) -> float:
        base = 5.0
        if shipping["method"] == "air":
            base = 15.0

        if shipping["options"].get("refrigerated"):
            base += 12.0
        if shipping["options"].get("insurance"):
            base += 3.0
        if shipping["options"].get("careful_handling"):
            base += 2.0
        return base


def generate_orders(n: int) -> list[dict]:
    """Generate a batch of orders with realistic distribution of flags."""
    random.seed(7)  # for reproducibility
    orders = []
    for i in range(n):
        order = {"id": f"ORD-{i:04d}"}
        
        # 20% are premium tier
        if random.random() < 0.2:
            order["tier"] = "premium"
        
        # 5% are fragile
        if random.random() < 0.05:
            order["fragile"] = True
        
        # 3% are perishable
        if random.random() < 0.03:
            order["perishable"] = True
        
        orders.append(order)
    
    return orders


def expected_cost(order: dict) -> float:
    """Calculate what the cost SHOULD be for an order."""
    tier = order.get("tier", "standard")
    
    # Base cost
    if tier == "premium":
        base = 15.0  # premium is always air
    elif order.get("perishable"):
        base = 15.0  # perishable forces air
    else:
        base = 5.0   # standard ground
    
    # Refrigerated (only if actually perishable)
    if order.get("perishable"):
        base += 12.0
    
    # Insurance (premium always has it, or if fragile)
    if tier == "premium" or order.get("fragile"):
        base += 3.0
    
    # Careful handling (only if fragile)
    if order.get("fragile"):
        base += 2.0
    
    return base


def main():
    processor = OrderProcessor()
    orders = generate_orders(50)
    
    results = []
    for order in orders:
        result = processor.process(order)
        results.append(result)
        autopsy.log("Processed:", 0, order, result)
        # autopsy.hist(result['cost'])


if __name__ == "__main__":
    autopsy.init()
    main()