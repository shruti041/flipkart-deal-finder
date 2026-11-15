import requests
import time
from fake_useragent import UserAgent

url = "https://www.flipkart.com/watches/~cs-cdf41ef7dfddd9403df42d3c63cde3b3/pr?sid=r18,f13&marketplace=FLIPKART&BU=Mixed"

session = requests.Session()

headers = {
    'User-Agent': UserAgent().random,
    'Accept-Language': 'en-US, en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Referer': 'https://www.google.com'
}

time.sleep(2)
r = session.get(url, headers=headers, timeout=15)
print("Status:", r.status_code)

with open("file.html", "w", encoding="utf-8") as f:
    f.write(r.text)

