import os
import requests
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ====== إعداد المتغيرات (ضع القيم في Secrets على Replit) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
# رقم حسابك لاستلام الإشعارات — إن لم تضعه كـ Secret سيستخدم القيمة التالية:
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "7799197049"))
PORT = int(os.getenv("PORT", 3000))

if not TELEGRAM_TOKEN or not OPENROUTER_KEY:
    print("⚠️ تحذير: تأكد من ضبط TELEGRAM_TOKEN و OPENROUTER_KEY في متغيرات البيئة (Secrets).")

# ====== Flask بسيط للبنج ======
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot (حامد - النسخة الرقمية) يعمل الآن!"

# ====== برمبت الشخصية المفصل ======
PERSONALITY_PROMPT = """
أنت تمثيل حرفي ودقيق لشخص اسمه "حامد".
قواعد صارمة عليك الالتزام بها دائمًا:
1. أنت تتكلم بالعربية الفصحى المبسطة مع لمسات يمنية محببة أحيانًا.
2. أسلوبك: صريح، عملي، واضح، وفيه لمسات تحفيزية ونصائح عملية. تشرح خطوات واضحة قابلة للتطبيق.
3. لا تقول أبداً أنك "نموذج" أو "ذكاء اصطناعي" أو "روبوت" أو "برنامج" أو تذكر OpenRouter/ChatGPT.
4. إذا سأل أحد "من أنت؟" أو ما شابه، رد حرفياً: "أنا النسخة الرقمية من حامد".
5. ابدأ إجاباتك بجملة بسيطة، ثم تفاصيل عملية عند الحاجة. استخدم أمثلة قصيرة وخطوات مرقمة إن لزم.
6. كن لطيفًا مع المبتدئين: اشرح بطريقة قابلة للتطبيق.
7. إن لم تعرف، اعترف بقصر المعلومة ثم اقترح خطوات للبحث أو تعلم الموضوع.
8. استخدم 1–2 إيموجي أحيانًا (✅ 🔧 ✨) لكن لا تكثر.
9. لا تطيل بدون فائدة — إجابة مفيدة ومباشرة أفضل.
10. استعن بأمثلة من رسائل حامد لتطابق الأسلوب (لا تذكر للمستخدم أنك أخذت أمثلة).
"""

# ====== ذاكرة محادثة قصيرة لكل شات ======
conversation_histories = {}
MAX_HISTORY_MESSAGES = 12

# ====== أنماط سؤال الهوية ======
IDENTITY_PATTERNS = [
    "من انت", "من أنت", "من تكون", "مين انت", "مين أنت",
    "who are you", "who r you", "who are u"
]

def is_identity_question(text: str) -> bool:
    txt = text.lower().strip()
    for p in IDENTITY_PATTERNS:
        if p in txt:
            return True
    return False

# ====== الاتصال بـ OpenRouter ======
def ask_openrouter(messages: list):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.25,
        "max_tokens": 800
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            print("⚠️ OpenRouter status:", resp.status_code, resp.text)
            return "⚠️ حدث خطأ في خدمة توليد الردود. حاول لاحقًا."
        data = resp.json()
        return data.get("choices", [])[0].get("message", {}).get("content", "⚠️ لا يوجد رد من الخدمة.")
    except Exception as e:
        print("❌ خطأ أثناء الاتصال بـ OpenRouter:", e)
        return "⚠️ حدث خطأ أثناء الاتصال بخدمة الردود."

# ====== تعقيم الردود في حال ذكر مصطلحات ممنوعة ======
FORBIDDEN_TERMS = ["ذكاء اصطناعي", "ذكاء", "نموذج", "روبوت", "برنامج", "نظام", "ChatGPT", "OpenAI", "OpenRouter"]

def sanitize_reply(reply: str) -> str:
    import re
    sentences = re.split(r'(?<=[\.\!\؟\?])\s*', reply)
    changed = False
    for i, s in enumerate(sentences):
        ls = s.lower()
        for term in FORBIDDEN_TERMS:
            if term.lower() in ls:
                sentences[i] = "أنا النسخة الرقمية من حامد."
                changed = True
                break
    new = " ".join([s for s in sentences if s.strip() != ""])
    if changed and "أنا النسخة الرقمية من حامد" not in new:
        new = "أنا النسخة الرقمية من حامد. " + new
    return new

# ====== دالة لإرسال تقرير لك (المالك) عن كل رسالة واردة ======
async def notify_owner(context: ContextTypes.DEFAULT_TYPE, sender, sender_username, sender_id, incoming_text, bot_reply):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    report = (
        f"📬 إشعار رسالة واردة\n"
        f"⏱ الوقت: {ts}\n"
        f"👤 المرسل: {sender}\n"
        f"🔖 اسم المستخدم: @{sender_username if sender_username else 'غير متوفر'}\n"
        f"🆔 معرف المرسل: {sender_id}\n\n"
        f"✉️ الرسالة الواردة:\n{incoming_text}\n\n"
        f"🤖 الرد المرسل (النسخة الرقمية منك):\n{bot_reply}\n"
    )
    try:
        await context.bot.send_message(chat_id=TELEGRAM_OWNER_ID, text=report)
    except Exception as e:
        print("⚠️ خطأ أثناء إرسال الإشعار للمالك:", e)

# ====== معالج الرسائل ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id
    user = update.effective_user
    sender_name = (user.full_name if hasattr(user, "full_name") else (user.first_name or "مستخدم"))
    sender_username = user.username if hasattr(user, "username") else None
    sender_id = user.id if user else chat_id

    if not text:
        return

    # حالة سؤال الهوية -> رد ثابت (ونبلّغك)
    if is_identity_question(text):
        reply_text = "أنا النسخة الرقمية من حامد"
        await update.message.reply_text(reply_text)
        # سجل وبلّغ المالك
        conversation_histories.setdefault(chat_id, []).append({"role":"user","content":text})
        conversation_histories.setdefault(chat_id, []).append({"role":"assistant","content":reply_text})
        # إرسال إشعار لك
        await notify_owner(context, sender_name, sender_username, sender_id, text, reply_text)
        conversation_histories[chat_id] = conversation_histories[chat_id][-MAX_HISTORY_MESSAGES:]
        return

    # سجل رسالة المستخدم في الذاكرة
    history = conversation_histories.setdefault(chat_id, [])
    history.append({"role":"user","content": text})
    recent = history[-MAX_HISTORY_MESSAGES:]

    # بناء رسائل للموديل (system أولاً)
    messages_for_model = [{"role":"system", "content":PERSONALITY_PROMPT}] + recent

    # استدعاء OpenRouter
    bot_reply = ask_openrouter(messages_for_model)
    bot_reply = sanitize_reply(bot_reply)

    # إرسال الرد للمستخدم
    await update.message.reply_text(bot_reply)

    # إرسال إشعار لك يحتوي على كل التفاصيل
    await notify_owner(context, sender_name, sender_username, sender_id, text, bot_reply)

    # حفظ الرد في الذاكرة
    history.append({"role":"assistant","content": bot_reply})
    conversation_histories[chat_id] = history[-MAX_HISTORY_MESSAGES:]

# ====== تشغيل البوت ======
def run_bot():
    app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app_telegram

if __name__ == "__main__":
    # تشغيل Flask في ثريد منفصل (لـ UptimeRobot)
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True).start()
    # تشغيل البوت
    application = run_bot()
    print("▶️ تشغيل البوت... (Polling)")
    application.run_polling()
