from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import random, time, re

app = FastAPI()

MIN_DELAY = 2
MAX_DELAY = 9

def human_delay():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

def clean_amazon_image(url):
    if url:
        return re.sub(r'\._AC_.*?\.', '.', url)
    return url

class SearchInput(BaseModel):
    upcs: list[str]

@app.post("/search")
def search_products(data: SearchInput):
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US")
        page = context.new_page()

       # for upc in data.upcs:
        try:
            page.goto(f"https://www.amazon.com/s?k={upc}", timeout=60000)
            human_delay()
            
            item = page.query_selector("div[data-component-type='s-search-result']")
            if not item:
                continue

            asin = item.get_attribute("data-asin")

                title_el = item.query_selector("h2 span")
                title = title_el.inner_text().strip() if title_el else ""

                img_el = item.query_selector("img.s-image")
                image = img_el.get_attribute("src") if img_el else ""
                image = clean_amazon_image(image)

                link_el = item.query_selector("h2 a")
                link = (
                    "https://www.amazon.com" + link_el.get_attribute("href")
                    if link_el else ""
                )

                # results.append({
                #     "SKU": upc,
                #     "ASIN": asin,
                #     "Title": title,
                #     "Image": image,
                #     "AmazonURL": link
                # })

            except Exception as e:
                print("Error:", upc, e)

        browser.close()

    return {"results": results}