import telegram
import os
from dotenv import load_dotenv
import logging
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, InlineQueryHandler
import finnhub
import asyncio
from datetime import datetime, timezone, timedelta
from datetime import datetime
from fastapi import FastAPI
import uvicorn
import asyncio

load_dotenv()
token = os.getenv("TOKEN")
news_api_key = os.getenv("NEWS_API_KEY")

# Setup client
finnhub_client = finnhub.Client(news_api_key)
print('client set up')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# helpers
def get_general_news(limit=5):
    news = finnhub_client.general_news('general', min_id=0)
    news = sorted(news, key=lambda x: x['datetime'], reverse=True)
    return news[:limit]

def format_news_item(i):
    ts = datetime.fromtimestamp(
        i['datetime'],
        tz=timezone.utc
    ).astimezone(timezone(timedelta(hours=8)))

    return (
        f"📰 *{i['headline']}*\n\n"
        f"{i['summary']}\n\n"
        f"🔗 {i['url']}\n"
        f"🕒 {ts.strftime('%Y-%m-%d %H:%M:%S SGT')}\n"
        f"{'-'*30}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sup, I am created by Zach the chud\nHere are some commands:\n/news - get top 5 market headlines\n/search - Search news articles related to the input keyword!")

async def news_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Usage: /news <keyword>"
        )
        return

    keyword = ' '.join(context.args).lower()
    news = get_general_news(limit=20)  # search a bit wider

    matched = []
    for i in news:
        text_blob = f"{i['headline']} {i['summary']}".lower()
        if keyword in text_blob:
            matched.append(i)

    if not matched:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Sorry, can’t find news related to *{keyword}* 😕",
            parse_mode="Markdown"
        )
        return

    message = f"🔎 *News matching:* `{keyword}`\n\n"
    for i in matched[:5]:
        message += format_news_item(i) + "\n\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode="Markdown"
    )

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = get_general_news(limit=5)

    message = "🧠 *Top 5 Market Headlines*\n\n"
    for i in news:
        message += format_news_item(i) + "\n\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode="Markdown"
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="idk zro")


# app

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "bot running"}

async def start_bot():
    token = os.getenv("TOKEN")
    application = ApplicationBuilder().token(token).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("news", news))
    application.add_handler(CommandHandler("search", news_search))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Initialize/start bot without messing with the loop
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    print("Bot is polling...")

    try:
        await asyncio.Event().wait()  # keep alive
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

async def main():
    bot_task = asyncio.create_task(start_bot())

    # Setup uvicorn server
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
    server = uvicorn.Server(config)

    api_task = asyncio.create_task(server.serve())

    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    asyncio.run(main())