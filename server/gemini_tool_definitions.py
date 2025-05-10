# Define the search_products tool
SEARCH_PRODUCTS_TOOL = {
    "name": "search_products",
    "description": "Search for products based on a query",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query for products"
            }
        },
        "required": ["query"]
    }
}
