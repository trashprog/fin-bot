"""
This script updates the text articles from finnhub in a rolling 60 day window
"""

import os
from dotenv import load_dotenv
import finnhub
import utils

# constants

load_dotenv()
FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
print("finnhub client successfully connected!")

us_company_codes = [
    # cloud
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "CRM", "ORCL", 
    # chips
    "NVDA", "AMD", "AVGO", "INTC", "CSCO", "IBM",
    # retail
    "TSLA", "WMT", "TGT", "COST", "MCD", "SBUX", "GM", "HD",
    # banking
    "JPM", "GS", "MS", "BAC", "WFC", "AXP", "V", "MA", "BRK.B",
    # sector anchor
    "PG", "KO", "PEP", "JNJ", "PFE", "LLY", "UNH", "GE", "CAT", "BA", "XOM", "CVX"

]

# Update the metadata
print("beginning news metadata refresh...")
news_metadata = []

for code in us_company_codes:
    try:
        news = utils.get_sixtyd_rolling_window(code, finnhub_client)
        news_metadata  += news
        print(f"company {code} processed! Total of {len(news)} news")
    except Exception as e:
        print('error processing: '+ code + f"\n{e}")

dedup_news_metadata = list({article['id']: article for article in news_metadata}.values())
utils.overwrite_news_metadata(dedup_news_metadata)
print(f"news_metadata successfully updated with a total of {len(dedup_news_metadata)} uniuqe news articles")





