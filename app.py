from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import random
import time
import re

app = FastAPI()

MIN_DELAY = 2
MAX_DELAY = 9  # Reduced from 9 for better user experience


def human_delay():
    """Add a random delay to mimic human behavior"""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def clean_amazon_image(url):
    """Remove Amazon image size parameters to get higher quality image"""
    if url:
        # Remove the ._AC_.*?. pattern for cleaner URLs
        return re.sub(r'\._AC_[^.]*\.', '.', url)
    return url


class SearchInput(BaseModel):
    upc: str


@app.get("/")
def home():
    """Health check endpoint"""
    return {"status": "Amazon scraper API running", "version": "1.0"}


@app.post("/search")
def search_product(data: SearchInput):
    """
    Search for a product on Amazon by UPC
    Returns product details including ASIN, title, image, and URL
    """
    upc = data.upc.strip()
    
    if not upc:
        return {"error": "UPC cannot be empty", "SKU": upc}

    browser = None
    
    try:
        with sync_playwright() as p:
            # Launch browser with additional options for better stability
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # Set user agent to avoid detection
            context = browser.new_context(
                locale="en-US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()

            # Navigate to Amazon search
            print(f"Searching for UPC: {upc}")
            page.goto(
                f"https://www.amazon.com/s?k={upc}",
                wait_until="domcontentloaded",
                timeout=60000
            )

            # Wait for search results to load
            try:
                page.wait_for_selector(
                    "div[data-component-type='s-search-result']",
                    timeout=10000
                )
            except Exception as wait_error:
                print(f"Wait error: {wait_error}")
                # Take a screenshot for debugging
                page.screenshot(path="/home/claude/debug_screenshot.png")
                browser.close()
                return {
                    "error": "No search results found or page took too long to load",
                    "SKU": upc
                }

            human_delay()

            # Get the first search result
            item = page.query_selector(
                "div[data-component-type='s-search-result']"
            )

            if not item:
                browser.close()
                return {"error": "Product not found", "SKU": upc}

            # Extract ASIN
            asin = item.get_attribute("data-asin")
            if not asin:
                asin = ""

            # Extract title
            title_el = item.query_selector("h2 span")
            title = title_el.inner_text().strip() if title_el else ""

            # Extract image
            img_el = item.query_selector("img.s-image")
            image = ""
            if img_el:
                # Try src first, then data-image-latency-src
                image = img_el.get_attribute("src")
                if not image or "data:image" in image:
                    image = img_el.get_attribute("data-image-latency-src") or ""
                image = clean_amazon_image(image)

            # Extract product link
            link_el = item.query_selector("h2 a")
            link = ""
            if link_el:
                href = link_el.get_attribute("href")
                if href:
                    # Handle both relative and absolute URLs
                    if href.startswith("http"):
                        link = href
                    else:
                        link = "https://www.amazon.com" + href

            browser.close()

            return {
                "SKU": upc,
                "ASIN": asin,
                "Title": title,
                "Image": image,
                "AmazonURL": link
            }

    except Exception as e:
        if browser:
            try:
                browser.close()
            except:
                pass
        
        print(f"Error occurred: {str(e)}")
        return {
            "error": f"An error occurred: {str(e)}",
            "SKU": upc
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)