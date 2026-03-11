"""
Talk example: Cart pricing with bulk discount and free shipping.

Same data and logic used in the presentation (seed=2, 16 items).
Run with: uv run talk/example.py
"""

from autopsy import log

class Item:
    def __init__(self, name: str, qty: int, price: float):
        self.name = name
        self.qty = qty
        self.price = price
        self.free_shipping = False

    def total(self):
        return self.qty * self.price

    def __repr__(self):
        return f"Item(name='{self.name}', qty={self.qty}, price={self.price:.2f})"


# Exact items from the presentation (seed=2, count=16)
cart = [
    Item("Widget", 12, 6.22),
    Item("Gadget", 5, 8.99),
    Item("Sprocket", 14, 10.20),
    Item("Bolt", 8, 6.64),
    Item("Washer", 12, 3.48),
    Item("Bracket", 12, 4.62),
    Item("Clip", 7, 12.85),
    Item("Pin", 9, 3.83),
    Item("Screw", 11, 6.77),
    Item("Nut", 15, 2.51),
    Item("Rivet", 14, 2.81),
    Item("Dowel", 2, 4.50),
    Item("Cap", 1, 14.22),
    Item("Plug", 7, 10.25),
    Item("Seal", 15, 5.03),
    Item("Ring", 8, 6.53),
]


def process_cart():
    for item in cart:
        if item.qty >= 10:
            item.price *= 0.9
            log("Bulk discount", item.price)
        if item.total() > 35:
            item.free_shipping = True
            log("Free shipping", item.free_shipping)
        log("item", item.name, item.qty, item.price)


if __name__ == "__main__":
    process_cart()
