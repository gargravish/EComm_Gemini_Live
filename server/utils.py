import random

def normalize_product(product, query=None):
    """Ensure product dict has all required fields with defaults."""
    return {
        'id': product.get('id') or product.get('productid', ''),
        'image_url': product.get('image_url', ''),
        'name': product.get('name', f"Product {product.get('id', product.get('productid', ''))}"),
        'description': product.get('description', f"This product matches your {query if query else 'image'} search"),
        'price': product.get('price', f"${random.randint(999, 9999)/100:.2f}"),
        'aisle': product.get('aisle', 'Unknown')
    } 