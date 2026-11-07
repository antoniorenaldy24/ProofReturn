"""Demo catalog and synthetic fixture seeder (Section 11.2 DS-01, MG-05)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "catalog" / "demo_products.json"

DEMO_PRODUCTS = [
    {"sku": "PR-HP-XM5", "name": "Studio Wireless ANC Headphones XM5", "category": "headphones", "msrp_minor": 40000, "serialized": True},
    {"sku": "PR-HP-MAX", "name": "Reference Over-Ear Monitor Pro", "category": "headphones", "msrp_minor": 55000, "serialized": True},
    {"sku": "PR-HP-BUDS", "name": "Compact ANC Earbuds Lite", "category": "headphones", "msrp_minor": 10000, "serialized": True},
    {"sku": "PR-CAM-35MM", "name": "Prime 35mm f/1.4 GM Lens", "category": "camera_lens", "msrp_minor": 140000, "serialized": True},
    {"sku": "PR-CAM-2470", "name": "Standard Zoom 24-70mm f/2.8 Lens", "category": "camera_lens", "msrp_minor": 200000, "serialized": True},
    {"sku": "PR-CAM-50MM", "name": "Portrait 50mm f/1.8 Lens", "category": "camera_lens", "msrp_minor": 30000, "serialized": True},
    {"sku": "PR-SNK-R1", "name": "Heritage Runner High-Top Edition", "category": "sneakers", "msrp_minor": 22000, "serialized": False},
    {"sku": "PR-SNK-TRL", "name": "Carbon Trail Pro Sneaker", "category": "sneakers", "msrp_minor": 18000, "serialized": False},
]


def main() -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(DEMO_PRODUCTS, indent=2), encoding="utf-8")
    print(f"Seeded {len(DEMO_PRODUCTS)} demo products into {CATALOG_PATH.relative_to(ROOT)} (DS-01).")


if __name__ == "__main__":
    main()
