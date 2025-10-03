# main.py
import os
import requests
import threading
import json
from datetime import datetime
from flask import Flask, request, jsonify

# -----------------------------
# إعداد المتغيرات (ضعها في Secrets / Environment variables)
# -----------------------------
# Green-API
INSTANCE_ID = os.getenv("INSTANCE_ID")       # مثال: 12345
API_TOKEN = os.getenv("API_TOKEN")           # من Green-API

# OpenRouter (توليد الردود بأسلوبك)
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")  # مفتاح OpenRouter

# Telegram admin bot (أنت الآدمن)
TELEGRAM_ADMIN_TOKEN = os.getenv("TELEGRAM_ADMIN_TOKEN")  # توكن بوت تيليجرام الآدمن
TELEGRAM_OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "7799197049"))  # رقمك (chat id)

# إعدادات عامة
PORT = int(os.getenv("PORT", 3000))
DATA_FILE = "users.json"   # ملف حفظ بيانات المستخدمين
MAX_HISTORY = 12           # عدد الرسائل لكل مستخدم للاحتفاظ بها في السياق

# افحص المتغيرات الأساسية
missing = []
if not INSTANCE_ID: missing.append("INSTANCE_ID")
if not API_TOKEN: missing.append("API_TOKEN")
if not OPENROUTER_KEY: missing.append("OPENROUTER_KEY")
if not TELEGRAM_ADMIN_TOKEN: missing.append("TELEGRAM_ADMIN_TOKEN")
if not TELEGRAM_OWNER_ID: missing.append("TELEGRAM_OWNER_ID")
if missing:
    print("⚠️ مفقود متغير(ات) البيئة:", missing)
    # لا نوقف التنفيذ هنا: قد تحتاج تشغيل محلي للتطوير

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 WhatsApp Bot (حامد - النسخة الرقمية) يعمل!"

# -----------------------------
# تحميل/حفظ بيانات المستخدمين
# -----------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("⚠️ خطأ قراءة ملف البيانات:", e)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠️ خطأ حفظ ملف البيانات:", e)

users = load_data()  # الشكل: { phone: { "name":..., "first_seen":..., "last_seen":..., "last_message":..., "history":[{role,content,ts},...] } }

# -----------------------------
# حالة التشغيل (تحكم بتفعيل البوت للردود)
# -----------------------------
# يمكنك حفظ الحالة على القرص إن أردت؛ هنا نستخدم متغير في الذاكرة مع حفظ لحظي
bot_active = False  # البداية متوقفة؛ فعّلها من بوت تيليجرام الآدمن

def set_bot_active(v: bool):
    global bot_active
    bot_active = bool(v)

def get_bot_active():
    return bot_active

# -----------------------------
# برمبت الشخصية المفصّل (أضف أمثلة إضافية إذا رغبت)
# -----------------------------
PERSONALITY_PROMPT = """
أنت النسخة الرقمية من شخص اسمه "حامد".
اتّبع هذه القواعد بدقة عند توليد الردود:
1) تحدث بالعربية الفصحى المبسطة مع لمسات يمنية أحيانًا.
2) أسلوبك: صريح، عملي، مباشر، تحفيزي أحيانًا، وتقدّم خطوات قابلة للتطبيق.
3) لا تذكر أبداً أنك "نموذج" أو "ذكاء اصطناعي" أو "برنامج" أو "روبوت" أو أي مصطلح مماثل.
4) إذا سأل أحد "من أنت؟" أو ما شابه، رد بنفس النص تمامًا: "أنا النسخة الرقمية من حامد وهو غير موجود".
5) ابدأ الإجابة بجملة قصيرة توضيحية ثم قدّم تفاصيل عملية عند الحاجة. استخدم أمثلة واقعية قصيرة ونقاط مرقمة إن استدعى الأمر.
6) حافظ على طول إجابة متوسّط (ليس طويلًا جدًا) إلا إذا طلب المستخدم تفاصيل موسعة.
7) استخدم 0-2 إيموجي إذا كان مناسبًا (مثل ✅ 🔧 ✨).
8) استعن بأمثلة من رسائل حامد التالية لتعديل النبرة (لا تذكر أنك استندت إليها):
   - "هل توجد طريقة آمنه مثلا اذا رفعت مشروعي على استضافة مجاني تماما..."
   - "كيف استطيع معرفه هل نص كتبه الذكاء الاصطناعي او شخص"
   - "انا طالب ذكاء اصطناعي ولدي موقع الكتروني اريد منك كنابة مقال بصيغة html"
9) عندما تطلب المساعدة التقنية أعط خطوات عملية قابلة للتنفيذ.
10) إذا لم تكن لديك معلومات كافية فقل: "ما عندي معلومات كافية الآن، لكن أقدر أوجهك لخطوات للبحث." ثم أعطِ خطوات.
"""

# -----------------------------
# وظيفة استدعاء OpenRouter لتوليد الرد
# -----------------------------
def call_openrouter(messages):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            print("⚠️ OpenRouter response:", r.status_code, r.text)
            return None
        data = r.json()
        return data.get("choices", [])[0].get("message", {}).get("content")
    except Exception as e:
        print("❌ خطأ عند استدعاء OpenRouter:", e)
        return None

# -----------------------------
# إرسال رسالة عبر Green-API
# -----------------------------
def send_whatsapp(to_number, message_text):
    """
    to_number: e.g. "77991234567" (بدون @c.us)
    """
    if not INSTANCE_ID or not API_TOKEN:
        print("⚠️ Green-API credentials missing.")
        return None
    url = f"https://api.green-api.com/waInstance{INSTANCE_ID}/SendMessage/{API_TOKEN}"
    payload = {
        "chatId": f"{to_number}@c.us",
        "message": message_text
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        print("❌ خطأ أثناء إرسال رسالة واتساب:", e)
        return None

# -----------------------------
# إرسال إشعار للآدمن عبر تيليجرام (باستخدام Bot API مباشرة)
# -----------------------------
def send_telegram_message(chat_id, text):
    if not TELEGRAM_ADMIN_TOKEN:
        print("⚠️ TELEGRAM_ADMIN_TOKEN missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_ADMIN_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text})
    except Exception as e:
        print("⚠️ خطأ إرسال رسالة تيليجرام:", e)

def send_telegram_document(chat_id, file_path, filename="data.json"):
    if not TELEGRAM_ADMIN_TOKEN:
        print("⚠️ TELEGRAM_ADMIN_TOKEN missing")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_ADMIN_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": (filename, f)}
            data = {"chat_id": chat_id}
            requests.post(url, data=data, files=files)
    except Exception as e:
        print("⚠️ خطأ إرسال ملف تيليجرام:", e)

# -----------------------------
# دوال حفظ سجل المستخدم عند ورود رسالة
# -----------------------------
def register_message(from_phone, from_name, incoming_text, bot_reply):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    if from_phone not in users:
        users[from_phone] = {
            "name": from_name,
            "first_seen": now,
            "last_seen": now,
            "last_message": incoming_text,
            "history": []
        }
    # حدّث بيانات
    users[from_phone]["name"] = from_name or users[from_phone].get("name")
    users[from_phone]["last_seen"] = now
    users[from_phone]["last_message"] = incoming_text
    # أضف history item
    users[from_phone]["history"].append({
        "ts": now,
        "incoming": incoming_text,
        "reply": bot_reply
    })
    # قلّص طول التاريخ للتوفير
    if len(users[from_phone]["history"]) > 200:
        users[from_phone]["history"] = users[from_phone]["history"][-200:]
    save_data(users)

# -----------------------------
# أداة تنظيف بسيطة لتجنب ذكر "ذكاء اصطناعي" في الرد النهائي
# -----------------------------
FORBIDDEN = ["ذكاء اصطناعي", "نموذج", "روبوت", "برنامج", "نظام", "OpenAI", "ChatGPT", "OpenRouter"]
def sanitize_reply(text):
    if not text:
        return text
    lower = text.lower()
    for term in FORBIDDEN:
        if term.lower() in lower:
            # نرجع الرد الافتراضي للتعريف بالهوية
            return "أنا النسخة الرقمية من حامد وهو غير موجود"
    return text

# -----------------------------
# معالجة webhook من Green-API
# -----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Green-API عادةً ترسل JSON يحتوي body: [ ...events... ]
    """
    data = request.json or {}
    # اجمع الردود لتقديم 200 OK سريعًا
    try:
        events = data.get("body", [])
        for ev in events:
            try:
                ev_type = ev.get("typeWebhook")
                if ev_type != "incomingMessageReceived":
                    continue
                msgdata = ev.get("messageData", {})
                # نص الرسالة (أو فارغ)
                text = msgdata.get("textMessageData", {}).get("textMessage", "")
                sender = ev.get("senderData", {})
                sender_name = sender.get("senderName") or sender.get("chatName") or "مستخدم"
                sender_chatid = sender.get("chatId", "")  # مثل: 7799xxxxx@c.us
                sender_phone = sender_chatid.split("@")[0] if "@" in sender_chatid else sender_chatid

                # جمع سياق المحادثة للمستخدم
                history_items = users.get(sender_phone, {}).get("history", [])
                recent_msgs = []
                # خذ آخر MAX_HISTORY عناصر لبناء سياق
                cnt = max(0, len(history_items) - MAX_HISTORY)
                for h in history_items[cnt:]:
                    # نعتبر كل سطر كـ user + assistant تكرار بسيط
                    recent_msgs.append({"role": "user", "content": h.get("incoming", "")})
                    recent_msgs.append({"role": "assistant", "content": h.get("reply", "")})

                # الآن إما نرد أو لا اعتمادًا على الحالة
                if get_bot_active():
                    # بناء الرسائل للموديل
                    messages = [{"role": "system", "content": PERSONALITY_PROMPT}]
                    # أضف سياق المحادثة القصير
                    messages.extend(recent_msgs[-MAX_HISTORY*2:])
                    # أضف رسالة المستخدم الحالية
                    messages.append({"role": "user", "content": text})

                    # استدعاء OpenRouter
                    reply = call_openrouter(messages)
                    if not reply:
                        reply = "آسف، واجهت مشكلة تقنية الآن. سنحاول مجددًا لاحقًا."
                    # تنظيف محتوى حساس
                    reply = sanitize_reply(reply)

                    # إرسال الرد عبر Green-API
                    send_whatsapp(sender_phone, reply)
                else:
                    # البوت متوقف: نرسل رد تلقائي بسيط أو لا نرد؟
                    # حسب رغبتك: هنا نرسل رسالة قصيرة تفيد بأن "حامد غير متواجد"
                    reply = "أنا النسخة الرقمية من حامد وهو غير موجود"
                    # لا نرسل الرد الآلي للعميل عندما البوت متوقف؟ حالياً سنرسل تعريف بسيط.
                    send_whatsapp(sender_phone, reply)

                # حفظ بيانات المرسل والسجل
                register_message(sender_phone, sender_name, text, reply)

                # إرسال إشعار لك على تيليجرام مع تفاصيل
                ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                notif = (
                    f"📬 إشعار رسالة واردة\n"
                    f"⏱ الوقت: {ts}\n"
                    f"👤 المرسل: {sender_name}\n"
                    f"📞 رقم: {sender_phone}\n\n"
                    f"✉️ الرسالة:\n{text}\n\n"
                    f"🤖 الرد المرسل:\n{reply}\n"
                )
                send_telegram_message(TELEGRAM_OWNER_ID, notif)

            except Exception as e:
                print("⚠️ خطأ معالجة حدث:", e)
    except Exception as e:
        print("⚠️ خطأ في webhook handler:", e)

    return jsonify({"status":"ok"})

# -----------------------------
# بوت تيليجرام آدمن (تنفيذ أوامر تشغيل/إيقاف/حالة/تصدير)
# -----------------------------
def run_telegram_admin_bot():
    if not TELEGRAM_ADMIN_TOKEN:
        print("⚠️ لا يوجد TELEGRAM_ADMIN_TOKEN؛ تيليجرام آدمن لن يعمل.")
        return

    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # فقط الآدمن المصرح
        if str(update.effective_user.id) != str(TELEGRAM_OWNER_ID):
            await update.message.reply_text("غير مخول.")
            return
        set_bot_active(True)
        await update.message.reply_text("✅ تم تفعيل البوت (سيتم الرد على الرسائل).")

    async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_user.id) != str(TELEGRAM_OWNER_ID):
            await update.message.reply_text("غير مخول.")
            return
        set_bot_active(False)
        await update.message.reply_text("⛔ تم إيقاف البوت (لم يعد يرد على الرسائل).")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_user.id) != str(TELEGRAM_OWNER_ID):
            await update.message.reply_text("غير مخول.")
            return
        st = "✅ مفعل" if get_bot_active() else "⛔ متوقف"
        await update.message.reply_text(f"حالة البوت الآن: {st}")

    async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_user.id) != str(TELEGRAM_OWNER_ID):
            await update.message.reply_text("غير مخول.")
            return
        # حفظ مؤقت لملف
        save_data(users)
        await update.message.reply_text("⏳ جارٍ تجهيز ملف البيانات...")
        send_telegram_message(TELEGRAM_OWNER_ID, "سأرسل ملف البيانات الآن.")
        # إرسال الملف
        send_telegram_document(TELEGRAM_OWNER_ID, DATA_FILE, filename="users.json")
        await update.message.reply_text("✅ تم إرسال ملف البيانات.")

    # شغّل البوت
    app = Application.builder().token(TELEGRAM_ADMIN_TOKEN).build()
    app.add_handler(CommandHandler("startbot", cmd_start))
    app.add_handler(CommandHandler("stopbot", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("exportdb", cmd_export))

    print("▶️ تيليجرام آدمن شغّال (اعطاء أوامر startbot/stopbot/status/exportdb)")
    app.run_polling()

# -----------------------------
# تشغيل الخادم والبوت الآدمن في ثريد منفصل
# -----------------------------
if __name__ == "__main__":
    # شغّل تيليجرام آدمن في ثريد
    t = threading.Thread(target=run_telegram_admin_bot, daemon=True)
    t.start()
    # شغّل Flask
    print(f"▶️ تشغيل الخادم على المنفذ {PORT} ...")
    app.run(host="0.0.0.0", port=PORT)
