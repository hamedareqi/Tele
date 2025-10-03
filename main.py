import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# مفاتيح API
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ضع هنا التوكن حق بوتFather إذا مش بتحطه في Secrets")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "ضع هنا مفتاح OpenRouter إذا مش بتحطه في Secrets")

# سيرفر Flask للبنج
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot is running! 🚀"

# دالة للرد من OpenRouter
def ask_openrouter(user_msg: str):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-3.5-turbo",  # تقدر تغيّر الموديل
            "messages": [{"role": "user", "content": user_msg}]
        }
        response = requests.post(url, headers=headers, json=data)
        res = response.json()
        return res["choices"][0]["message"]["content"]
    except Exception as e:
        print("❌ Error:", e)
        return "⚠️ حصل خطأ أثناء الاتصال بالذكاء الاصطناعي."

# دالة الرد على الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    reply = ask_openrouter(user_msg)
    await update.message.reply_text(reply)

# تشغيل بوت تيليجرام
def run_bot():
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app_telegram

if __name__ == "__main__":
    import threading

    # تشغيل السيرفر Flask في Thread منفصل للبنج
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=3000)).start()

    # تشغيل بوت تيليجرام
    application = run_bot()
    application.run_polling()￼Enter
