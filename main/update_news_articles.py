import utils
import concurrent.futures

cached_news_metadata = utils.load_cached_news_metadata()
cached_news_articles = utils.load_cached_news_articles()

# articles that have not been processed and insdie the metadata
urls = list(set([news['url'] for news in cached_news_metadata if news['url'] not in cached_news_articles]))

print(f"processing {len(urls)} urls")
completed = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
    # Start the load operations and mark each future with its URL
    future_to_url = {executor.submit(utils.load_url, url, 30): url for url in urls}
    for future in concurrent.futures.as_completed(future_to_url):
        url = future_to_url[future]
        try:
            data = future.result()

            # convert to text
            article_text = utils.get_text_from_html(data)

            # append to list
            if article_text:
                cached_news_articles[url] = article_text
                print(f"{url} successfully processed!")

        except Exception as exc:
            print('%r generated an exception: %s' % (url, exc))

        completed += 1
        if completed % 25 == 0:
            print(f"{completed}/{len(urls)} completed")

# remove articles not present in the metadata
metadata_urls = [news['url'] for news in cached_news_metadata]
filtered_cached_news_articles = {url: text for url, text in cached_news_articles.items() if url in metadata_urls}

utils.overwrite_news_articles(filtered_cached_news_articles)

print(f"news_articles successfully updated with a total of {len(filtered_cached_news_articles)} unique news articles")