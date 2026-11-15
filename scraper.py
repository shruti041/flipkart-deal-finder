"""
Flipkart scraper: Women's Ethnic Sets with 70%+ discount.

Run this on your own computer (not on Streamlit Cloud) to refresh the data:
    python scraper.py

It saves the results to products.csv, which app.py reads.

How it works:
Flipkart pages embed all product data as JSON inside a <script> tag
(window.__INITIAL_STATE__ = {...}). Reading that JSON is far more reliable
than reading HTML class names, which Flipkart changes often.
"""

import json
import random
import re
import time
from datetime import datetime

import pandas as pd
import requests

URL = (
    "https://www.flipkart.com/womens-ethnic-sets/~cs-0tdstnnhbs/pr?sid=clo%2Ccfv%2Citg%2Ctys"
    "&collection-tab-name=ETHNIC+SETS"
    "&p%5B%5D=facets.discount_range_v1%255B%255D%3D70%2525%2Bor%2Bmore"
    "&ctx=eyJjYXJkQ29udGV4dCI6eyJhdHRyaWJ1dGVzIjp7InNvdXJjZUNvbnRlbnRUeXBlIjp7InNpbmdsZVZhbHVlQXR0cmlidXRlIjp7ImtleSI6InNvdXJjZUNvbnRlbnRUeXBlIiwiaW5mZXJlbmNlVHlwZSI6IlNDVCIsInZhbHVlIjoiSUFEIiwidmFsdWVUeXBlIjoiU0lOR0xFX1ZBTFVFRCJ9fX19fQ%3D%3D"
    "&nnc=142647NAN2V1_IAD&BU=Mixed"
)

PAGES_TO_SCRAPE = 5          # Flipkart shows 40 products per page
OUTPUT_FILE = "products.csv"

# A fixed *desktop* User-Agent matters here: with a mobile one, Flipkart sends
# its mobile site, which only shows ~10 products and ignores &page=N.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.google.com",
}


def fetch_page(session, page_number):
    """Download one results page and return its HTML."""
    response = session.get(f"{URL}&page={page_number}", headers=HEADERS, timeout=20)
    response.raise_for_status()   # stop with a clear error on 403/429/500
    return response.text


def extract_state_json(html):
    """Pull the window.__INITIAL_STATE__ JSON object out of the page."""
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if not match:
        raise ValueError("Could not find product data on the page (layout changed or blocked?)")
    data, _ = json.JSONDecoder().raw_decode(html, match.end())
    return data


def find_products(node):
    """Recursively find every product in the JSON (they sit under 'productInfo')."""
    if isinstance(node, dict):
        info = node.get("productInfo")
        if isinstance(info, dict) and isinstance(info.get("value"), dict):
            yield info["value"]
        for value in node.values():
            yield from find_products(value)
    elif isinstance(node, list):
        for item in node:
            yield from find_products(item)


def image_url(product):
    """Turn Flipkart's image URL template into a real 400x400 image link."""
    images = (product.get("media") or {}).get("images") or []
    if not images:
        return None
    url = images[0]["url"]
    url = url.replace("{@width}", "400").replace("{@height}", "400").replace("{@quality}", "70")
    return url.replace("http://", "https://")


def get_prices(pricing):
    """
    Return (selling_price, mrp).

    Flipkart sends two different JSON layouts at random:
      - full:  pricing.finalPrice.value and pricing.mrp.value
      - slim:  only a pricing.prices list, where the struck-off entry is the
               MRP and the other one is the price you actually pay
    """
    price = (pricing.get("finalPrice") or {}).get("value")
    mrp = (pricing.get("mrp") or {}).get("value")
    for entry in pricing.get("prices") or []:
        if entry.get("strikeOff"):
            mrp = mrp or entry.get("value")
        else:
            price = price or entry.get("value")
    return price, mrp


def parse_product(p):
    """Keep only the fields we need, in a flat dictionary (one CSV row)."""
    titles = p.get("titles") or {}
    pricing = p.get("pricing") or {}
    rating = p.get("rating") or {}          # missing in the slim layout
    price, mrp = get_prices(pricing)
    return {
        "product_id": p.get("id"),
        "brand": p.get("productBrand") or titles.get("superTitle"),
        "title": titles.get("newTitle") or titles.get("title"),
        "price": price,
        "mrp": mrp,
        "discount_pct": pricing.get("totalDiscount"),
        "rating": rating.get("average") or None,     # 0 means "no ratings yet"
        "rating_count": rating.get("count"),
        "review_count": rating.get("reviewCount"),
        "image_url": image_url(p),
        "product_url": "https://www.flipkart.com" + p["baseUrl"] if p.get("baseUrl") else None,
    }


def main():
    session = requests.Session()
    all_products = {}   # keyed by product_id, so duplicates are dropped

    for page in range(1, PAGES_TO_SCRAPE + 1):
        print(f"Scraping page {page}...", end=" ")
        html = fetch_page(session, page)
        state = extract_state_json(html)

        new = 0
        for raw in find_products(state):
            row = parse_product(raw)
            if row["product_id"] and row["price"] and row["product_id"] not in all_products:
                all_products[row["product_id"]] = row
                new += 1
        print(f"{new} new products (total {len(all_products)})")

        if new == 0:
            print("No new products found, stopping early.")
            break
        time.sleep(random.uniform(2, 4))   # be polite: pause between requests

    df = pd.DataFrame(all_products.values())
    df["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\nSaved {len(df)} products to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
