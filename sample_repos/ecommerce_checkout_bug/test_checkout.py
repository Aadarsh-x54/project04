from checkout import Item, CheckoutProcessor


def test_basic_checkout_no_discount():
    processor = CheckoutProcessor(tax_rate=0.10)
    items = [Item(sku="LAPTOP-1", name="Pro Laptop", price=100.0, quantity=2, discount_pct=0.0)]
    summary = processor.process_checkout(items)
    assert summary["subtotal"] == 200.0
    assert summary["tax"] == 20.0
    assert summary["total"] == 220.0

