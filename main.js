// main.js
// كل شيء في ملف واحد: WhatsApp (whatsapp-web.js) + Telegram admin + OpenRouter replies + DB + Express ping.

import fs from "fs-extra";
import path from "path";
import qrcode from "qrcode-terminal";
import express from "express";
import axios from "axios";
import FormData from "form-data";
import { Client, LocalAuth, MessageMedia } from "whatsapp-web.js";
import TelegramBot from "node-telegram-bot-api";


// ---------------------------
// إعدادات (لا تضع القيم هنا — ضعها في Secrets / Environment variables في Replit)
// ---------------------------
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;   // توكن بوت التيليجرام (BotFather)
const TELEGRAM_OWNER_ID = process.env.TELEGRAM_OWNER_ID || ""; // chat id (مثال: 7799197049)
const OPENROUTER_KEY = process.env.OPENROUTER_KEY;           // مفتاح OpenRouter (sk-or-...)
const PORT = process.env.PORT || 3000;

// تحقق سريع
if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_OWNER_ID || !OPENROUTER_KEY) {
  console.warn("⚠️ تحذير: تأكد من وضع TELEGRAM_BOT_TOKEN وTELEGRAM_OWNER_ID وOPENROUTER_KEY في Secrets.");
}

// ---------------------------
// ملف قاعدة البيانات
// ---------------------------
const DATA_DIR = "./data";
const DB_FILE = path.join(DATA_DIR, "users.json");
fs.ensureDirSync(DATA_DIR);
if (!fs.existsSync(DB_FILE)) fs.writeJsonSync(DB_FILE, {});

// تحميل/حفظ DB
function loadDB() {
  try { return fs.readJsonSync(DB_FILE); } 
  catch(e){ console.error("خطأ قراءة DB:", e); return {}; }
}
function saveDB(db) {
  try { fs.writeJsonSync(DB_FILE, db, { spaces: 2 }); } 
  catch(e){ console.error("خطأ حفظ DB:", e); }
}
let DB = loadDB();

// ---------------------------
// برمبت الشخصية المحسّن والاحترافي
// ---------------------------
const PERSONALITY_PROMPT = `
أنت "النسخة الرقمية من حامد". قاعدة صارمة:
- تحدث بالعربية الفصحى المبسطة مع لمسات يمنية عند الحاجة.
- أسلوبك: صريح، عملي، مباشر، مُحفّز، وتشرح خطوات قابلة للتطبيق. تلخّص أولاً ثم توسع عند الحاجة.
- لا تذكر أبداً أنك "ذكاء اصطناعي" أو "نموذج" أو "برنامج" أو "ChatGPT" أو "OpenRouter".
- إذا سُئلت "من أنت؟" أو "مين أنت" أجب حرفيًا: "أنا النسخة الرقمية من حامد وهو غير موجود".
- استخدم معلومات المحادثات السابقة مع المرسل لصياغة إجابة شخصية ومتصلة بالسياق. اعتمد على آخر 50 رسالة كحد أقصى.
- ابدأ إجابتك بجملة قصيرة واضحة، ثم خطوات / نقاط عملية إن لزم.
- إذا لم تكن لديك معلومات كافية قل: "ما عندي معلومات كافية الآن، لكن أقدر أوجهك لخطوات للبحث" ثم اقترح خطوات.
- استخدم 0-2 إيموجي بحذر (مثال: ✅ 🔧 ✨).
- عند الإجابة التقنية، قدم أمثلة أو أوامر عملية إن تطلب.
`;

// ---------------------------
// مساعد: بناء رسالة للموديل باستخدام سياق طويل
// ---------------------------
function buildMessagesForUser(phone) {
  const user = DB[phone];
  const history = user && user.history ? user.history.slice(-100) : [];
  // نأخذ آخر 50 رسالة (user+assistant) كنص متسلسل
  const textHistory = history.map(h => `${h.direction === "in" ? "User:" : "You:"} ${h.text}`).join("\n");
  const messages = [
    { role: "system", content: PERSONALITY_PROMPT },
    { role: "user", content: `هذا سجل محادثة سابقة (اعتمد عليه لصياغة إجابة كحامد):\n${textHistory}` }
  ];
  return messages;
}

// ---------------------------
// استدعاء OpenRouter (Chat Completions)
// ---------------------------
async function generateReplyWithOpenRouter(messages) {
  try {
    const resp = await axios.post("https://openrouter.ai/api/v1/chat/completions", {
      model: "gpt-3.5-turbo",
      messages: messages,
      temperature: 0.22,
      max_tokens: 800
    }, {
      headers: {
        "Authorization": `Bearer ${OPENROUTER_KEY}`,
        "Content-Type": "application/json"
      },
      timeout: 30000
    });
    const content = resp.data?.choices?.[0]?.message?.content;
    return content || null;
  } catch (err) {
    console.error("OpenRouter error:", err?.response?.data || err.message || err);
    return null;
  }
}

// ---------------------------
// Telegram admin bot (node-telegram-bot-api) — تحكم وإشعارات
// ---------------------------
let tgBot = null;
if (TELEGRAM_BOT_TOKEN) {
  tgBot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });

  // أوامر آدمن: start/stop/status/export
  tgBot.onText(/\/startbot/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    whatsappActive = true;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, "✅ تم تفعيل البوت. الآن سيرد على الرسائل.");
  });
  tgBot.onText(/\/stopbot/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    whatsappActive = false;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, "⛔ تم إيقاف البوت. لن يرد الآن.");
  });
  tgBot.onText(/\/status/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, `حالة البوت: ${whatsappActive ? "✅ مفعل" : "⛔ متوقف"}`);
  });
  tgBot.onText(/\/exportdb/, async (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    saveDB(DB);
    await tgBot.sendMessage(TELEGRAM_OWNER_ID, "⏳ جارٍ تجهيز الملف...");
    await tgBot.sendDocument(TELEGRAM_OWNER_ID, DB_FILE);
  });
}

// ---------------------------
// Express server بسيط لPing (UptimeRobot)
// ---------------------------
const app = express();
app.get("/", (req, res) => res.send("Digital Hamed Bot — alive"));
app.listen(PORT, () => console.log(`Express server listening on ${PORT}`));

// ---------------------------
// WhatsApp client (whatsapp-web.js) مع LocalAuth لحفظ الجلسة
// ---------------------------
const client = new Client({ authStrategy: new LocalAuth(), puppeteer: { headless: true } });

let whatsappActive = false; // يتحكم به تيليجرام
client.on("qr", qr => {
  qrcode.generate(qr, { small: true });
  console.log("امسح QR من واتساب لتسجيل الجلسة.");
});
client.on("ready", () => {
  console.log("WhatsApp client ready!");
});
client.on("auth_failure", msg => console.error("Auth failure", msg));
client.on("disconnected", reason => console.log("WhatsApp disconnected:", reason));

// مساعدة: إرسال إشعار إلى تيليجرام (نص أو ملف)
async function notifyTelegramText(text) {
  if (!tgBot) return;
  try { await tgBot.sendMessage(TELEGRAM_OWNER_ID, text); } 
  catch (e) { console.error("tg notify error:", e); }
}
async function notifyTelegramDocument(filepath, caption) {
  if (!tgBot) return;
  try { await tgBot.sendDocument(TELEGRAM_OWNER_ID, filepath, { caption }); } 
  catch (e) { console.error("tg doc error:", e); }
}

// حفظ رسالة في DB
function recordMessage(phone, direction, text) {
  if (!DB[phone]) DB[phone] = { name: null, firstSeen: new Date().toISOString(), history: [] };
  DB[phone].name = DB[phone].name || phone;
  DB[phone].history.push({ ts: new Date().toISOString(), direction, text });
  // قلّص طول التاريخ
  if (DB[phone].history.length > 500) DB[phone].history = DB[phone].history.slice(-500);
  saveDB(DB);
}

// تنظيف رد لا يذكر مصطلحات ممنوعة
function sanitizeReply(text) {
  if (!text) return text;
  const forbidden = ["ذكاء اصطناعي","نموذج","روبوت","برنامج","ChatGPT","OpenAI","OpenRouter"];
  const lower = text.toLowerCase();
  for (const f of forbidden) if (lower.includes(f.toLowerCase())) return "أنا النسخة الرقمية من حامد وهو غير موجود";
  return text;
}

// التعامل مع الرسائل واردة
client.on("message", async msg => {
  try {
    const from = msg.from; // مثال: "9677xxxxxxx@c.us"
    const phone = from.split("@")[0];
    const isMedia = msg.hasMedia && msg.type !== "chat";

    // حفظ في DB كـ incoming
    if (msg.type === "chat") {
      const text = msg.body || "";
      recordMessage(phone, "in", text);
      // إرسال إشعار نصي لتيليجرام
      await notifyTelegramText(`📩 رسالة واردة من: ${phone}\n\n${text}`);
    } else {
      // ميديا: تحميلها مؤقتًا ثم إرسالها لتيليجرام
      const media = await msg.downloadMedia();
      if (media && media.data) {
        const ext = (media.mimetype || "bin").split("/")[1] || "dat";
        const tempPath = path.join(DATA_DIR, `media_${Date.now()}.${ext}`);
        fs.writeFileSync(tempPath, Buffer.from(media.data, "base64"));
        // حفظ سجل في DB (بمسار الملف المحلي)
        recordMessage(phone, "in", `[media:${tempPath}]`);
        await notifyTelegramDocument(tempPath, `📩 وسائط واردة من ${phone}`);
        // لا تنسى إزالة الملف بعد بعض الوقت (يمكن تركه أو حذفه)
        // fs.unlinkSync(tempPath);
      }
    }

    // هل البوت مفعل للرد؟ نفعل الرد الذكي فقط إذا مفعل
    if (!whatsappActive) {
      // نرسل تعريف الهوية البسيط إذا رغبت — هنا نتركه يرسل رسالة واحدة توضيحية
      // للتصرف المختلف، يمكن تعطيل الإرسال نهائياً.
      const offlineText = "أنا النسخة الرقمية من حامد وهو غير موجود";
      await client.sendMessage(from, offlineText);
      recordMessage(phone, "out", offlineText);
      await notifyTelegramText(`↩️ (تم إرسال رد تلقائي أثناء الإيقاف) إلى ${phone}: ${offlineText}`);
      return;
    }

    // بناء سياق كامل - نوفر آخر 50 عنصر من الـ history
    const messagesForModel = buildMessagesForUser(phone);
    // أضف الرسالة الحالية بصيغة user
    if (msg.type === "chat") messagesForModel.push({ role: "user", content: msg.body });

    // اطلب من OpenRouter توليد رد
    const generated = await generateReplyWithOpenRouter(messagesForModel);
    let finalReply = generated ? sanitizeReply(generated) : "عذرًا، واجهت مشكلة تقنية الآن. سأعاود لاحقًا.";
    // إرسال الرد للمرسل
    await client.sendMessage(from, finalReply);
    // حفظ الرد في DB
    recordMessage(phone, "out", finalReply);
    // إشعار لك في تيليجرام بالرد المرسل
    await notifyTelegramText(`✅ تم الرد على ${phone} بالرسالة:\n\n${finalReply}`);
  } catch (err) {
    console.error("خطأ في معالجة رسالة:", err);
  }
});

// بدء العميل
client.initialize();
