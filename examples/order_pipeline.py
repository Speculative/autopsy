"""
Order Fulfillment Pipeline

Bug: Shallow copy of shipping profiles causes nested 'options' dict to be
shared between the profile template and computed shipping configs. When
handling rules modify options, they permanently contaminate the profile.
"""

import random
from autopsy import report
from autopsy.report import generate_html, ReportConfiguration

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
            report.count("refrigerated")
            base += 12.0
        if shipping["options"].get("insurance"):
            report.count("insured")
            base += 3.0
        if shipping["options"].get("careful_handling"):
            report.count("careful_handling")
            base += 2.0
        return base


def generate_orders(n: int) -> list[dict]:
    """Generate a batch of orders with realistic distribution of flags."""
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
    errors = []
    
    for order in orders:
        # report.log("Processing order",
        #   order["id"],
        #   order.get("tier", "standard"),
        #   order.get("fragile", False),
        #   order.get("perishable", False))
        result = processor.process(order)
        report.hist(result['cost'])
        results.append(result)
        report.log("Processed",
          order["id"],
          order.get("tier", "standard"),
          order.get("fragile", False),
          order.get("perishable", False),
          result["cost"])

        expected = expected_cost(order)
        if abs(result["cost"] - expected) > 0.01:
            errors.append({
                "order": order,
                "result": result,
                "expected_cost": expected,
                "actual_cost": result["cost"],
                "overcharge": result["cost"] - expected
            })
    
    # Summary
    print(f"Processed {len(orders)} orders")
    print(f"Errors: {len(errors)} orders with incorrect pricing")
    print()
    
    if errors:
        total_overcharge = sum(e["overcharge"] for e in errors)
        print(f"Total overcharge: ${total_overcharge:.2f}")
        print()
        
        # Show first few errors
        print("First 10 pricing errors:")
        print("-" * 60)
        for e in errors[:10]:
            order = e["order"]
            flags = []
            if order.get("tier") == "premium":
                flags.append("premium")
            if order.get("fragile"):
                flags.append("fragile")
            if order.get("perishable"):
                flags.append("perishable")
            flag_str = ", ".join(flags) if flags else "standard, no flags"
            
            print(f"{order['id']}: {flag_str}")
            print(f"  Expected: ${e['expected_cost']:.2f}, "
                  f"Actual: ${e['actual_cost']:.2f}, "
                  f"Overcharge: ${e['overcharge']:.2f}")
            print(f"  Shipping options: {e['result']['shipping']['options']}")
            print()


if __name__ == "__main__":
    # trace["frames"][0]["local_variables"]["order"]["id"]
    # report.init(ReportConfiguration(
    #     auto_stack_trace=True,
    #     live_mode=True,
    #     live_mode_host="localhost",
    #     live_mode_port=8765
    # ))
    report.init()
      # report.init(ReportConfiguration(
    #     auto_stack_trace=True,
    #     live_mode=True,
    #     live_mode_host="localhost",
    #     live_mode_port=8765
    # ))  main()
    main()
    generate_html(report, output_path="order_pipeline_report.html")