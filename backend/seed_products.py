"""
Seed the products table with the 5 products from the mock API.
Run once before first sync.
"""
from app.db.database import get_connection

PRODUCTS = [
    {"id": 1, "name": "Washing Machine X200", "category": "Laundry"},
    {"id": 2, "name": "Refrigerator R-200", "category": "Cooling"},
    {"id": 3, "name": "Microwave M-50", "category": "Cooking"},
    {"id": 4, "name": "Air Conditioner AC-1000", "category": "Cooling"},
    {"id": 5, "name": "Water Heater WH-30", "category": "Heating"},
]

with get_connection() as conn:
    with conn.cursor() as cur:
        for p in PRODUCTS:
            cur.execute("""
                INSERT INTO products (id, name, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
            """, (p["id"], p["name"], p["category"]))
        conn.commit()
    print(f"Seeded {len(PRODUCTS)} products.")