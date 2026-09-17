
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Updating metadata boilerplate codes
def load_cached_news_metadata():
    cached_news_metadata = None
    with open('cache/news_metadata.json', 'r') as f:
        cached_news_metadata = json.load(f)
    return cached_news_metadata

def overwrite_news_metadata(metadata):
    # write to json
    with open('cache/news_metadata.json', 'w') as f:
        json.dump(metadata, f)

def date_days_ago(days, curr_date):
    return (curr_date - timedelta(days=days)).strftime("%Y-%m-%d")

def get_sixtyd_rolling_window(company_code, finnhub_client):
    # uese us market open date to avoid lookahead bias
    us_market_time_open = datetime.now(ZoneInfo("America/New_York")).replace(hour=9, minute=30, second=0, microsecond=0)
    us_market_time_open_date = us_market_time_open.strftime("%Y-%m-%d")
    sixtyd_ago_date = date_days_ago(60, us_market_time_open)
    us_market_time_open_ts = int(us_market_time_open.timestamp())
    sixtyd_window_news = finnhub_client.company_news(company_code, _from=sixtyd_ago_date, to=us_market_time_open_date)
    # filter
    filtered_sixtyd_window_news = [article for article in sixtyd_window_news if article['datetime'] < us_market_time_open_ts]
    return filtered_sixtyd_window_news


# getting the text from the urls

def load_cached_news_articles():
    cached_news_articles = None
    with open('cache/news_articles.json', 'r') as f:
        cached_news_articles = json.load(f)
    return cached_news_articles

def overwrite_news_articles(articles):
    # write to json
    with open('cache/news_articles.json', 'w') as f:
        json.dump(articles, f)

def load_url(url, timeout):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response.content

def get_text_from_html(data):
    soup = BeautifulSoup(data, 'html.parser')
    paragraphs = soup.find_all("p")
    article_text = "\n".join(p.get_text(" ", strip=True).lower() for p in paragraphs)
    return article_text







