// main.js — WhatsApp Digital Hamed Bot + Telegram admin
// لا يحتاج ملف config.json، كل القيم مأخوذة من Replit Secrets

const fs = require("fs-extra");
const path = require("path");
const qrcode = require("qrcode-terminal");
const express = require("express");
const axios = require("axios");
const FormData = require("form-data");
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const TelegramBot = require("node-telegram-bot-api");

// ---------------------------
// قراءة الإعدادات من environment variables
// ---------------------------
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_OWNER_ID = process.env.TELEGRAM_OWNER_ID;
const OPENROUTER_KEY = process.env.OPENROUTER_KEY;
let whatsappActive = process.env.WHATSAPP_ACTIVE === "true" || false;
const PORT = process.env.PORT || 3000;

if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_OWNER_ID || !OPENROUTER_KEY) {
  console.error("⚠️ تأكد من إعداد كل Secrets: TELEGRAM_BOT_TOKEN و TELEGRAM_OWNER_ID و OPENROUTER_KEY");
}

// ---------------------------
// قاعدة البيانات
// ---------------------------
const DATA_DIR = "./data";
const DB_FILE = path.join(DATA_DIR, "users.json");
fs.ensureDirSync(DATA_DIR);
if (!fs.existsSync(DB_FILE)) fs.writeJsonSync(DB_FILE, {});

let DB = fs.readJsonSync(DB_FILE);

// ---------------------------
// برمبت الشخصية
// ---------------------------
const PERSONALITY_PROMPT = `
أنت "النسخة الرقمية من حامد". قواعد صارمة:
- تحدث بالعربية الفصحى المبسطة مع لمسات يمنية.
- أسلوبك: صريح، عملي، مباشر، مُحفّز.
- لا تذكر أبداً أنك "ذكاء اصطناعي" أو "نموذج".
- إذا سُئلت من أنت أجب: "أنا النسخة الرقمية من حامد وهو غير موجود".
- استخدم المحادثات السابقة مع المرسل لصياغة إجابة شخصية.
- اعتمد آخر 50 رسالة فقط.
- عند الإجابة التقنية قدم أمثلة عملية.
`;

// ---------------------------
// وظائف قاعدة البيانات
// ---------------------------
function saveDB() {
  fs.writeJsonSync(DB_FILE, DB, { spaces: 2 });
}

function recordMessage(phone, direction, text) {
  if (!DB[phone]) DB[phone] = { name: null, firstSeen: new Date().toISOString(), history: [] };
  DB[phone].name = DB[phone].name || phone;
  DB[phone].history.push({ ts: new Date().toISOString(), direction, text });
  if (DB[phone].history.length > 500) DB[phone].history = DB[phone].history.slice(-500);
  saveDB();
}

// ---------------------------
// Telegram Bot للتحكم والإشعارات
// ---------------------------
let tgBot = null;
if (TELEGRAM_BOT_TOKEN) {
  tgBot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });

  tgBot.onText(/\/startbot/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    whatsappActive = true;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, "✅ تم تفعيل البوت.");
  });

  tgBot.onText(/\/stopbot/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    whatsappActive = false;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, "⛔ تم إيقاف البوت.");
  });

  tgBot.onText(/\/status/, (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    tgBot.sendMessage(TELEGRAM_OWNER_ID, `حالة البوت: ${whatsappActive ? "✅ مفعل" : "⛔ متوقف"}`);
  });

  tgBot.onText(/\/exportdb/, async (msg) => {
    if (String(msg.from.id) !== String(TELEGRAM_OWNER_ID)) return;
    await tgBot.sendMessage(TELEGRAM_OWNER_ID, "⏳ جاري تجهيز الملف...");
    await tgBot.sendDocument(TELEGRAM_OWNER_ID, DB_FILE, { caption: "ملف قاعدة بيانات المستخدمين" });
  });
}

// ---------------------------
// Express server لPing
// ---------------------------
const app = express();
app.get("/", (req, res) => res.send("Digital Hamed Bot — alive"));
app.listen(PORT, () => console.log(`Express listening on ${PORT}`));

// ---------------------------
// WhatsApp client
// ---------------------------
const client = new Client({ authStrategy: new LocalAuth(), puppeteer: { headless: true } });

client.on("qr", qr => qrcode.generate(qr, { small: true }));
client.on("ready", () => console.log("WhatsApp ready!"));
client.on("auth_failure", msg => console.error("Auth failure", msg));
client.on("disconnected", reason => console.log("WhatsApp disconnected:", reason));

// إشعارات تيليجرام
async function notifyTelegramText(text) { if(tgBot) try { await tgBot.sendMessage(TELEGRAM_OWNER_ID, text); } catch(e){console.error(e);} }
async function notifyTelegramDocument(filepath, caption) { if(tgBot) try { await tgBot.sendDocument(TELEGRAM_OWNER_ID, filepath, { caption }); } catch(e){console.error(e);} }

// ---------------------------
// إنشاء الرد عبر OpenRouter
// ---------------------------
async function buildReply(phone, incomingText) {
  const user = DB[phone];
  const history = user && user.history ? user.history.slice(-50) : [];
  const textHistory = history.map(h => `${h.direction === "in" ? "User:" : "You:"} ${h.text}`).join("\n");

  const messages = [
    { role: "system", content: PERSONALITY_PROMPT },
    { role: "user", content: `سجل محادثة سابقة:\n${textHistory}` },
    { role: "user", content: incomingText }
  ];

  try {
    const resp = await axios.post("https://openrouter.ai/api/v1/chat/completions", {
      model: "gpt-3.5-turbo",
      messages,
      temperature: 0.22,
      max_tokens: 800
    }, {
      headers: { "Authorization": `Bearer ${OPENROUTER_KEY}`, "Content-Type": "application/json" },
      timeout: 30000
    });

    const content = resp.data?.choices?.[0]?.message?.content;
    return content || "عذرًا، واجهت مشكلة تقنية.";
  } catch(err) {
    console.error("OpenRouter error:", err?.response?.data || err.message);
    return "عذرًا، واجهت مشكلة تقنية.";
  }
}

// ---------------------------
// التعامل مع الرسائل
// ---------------------------
client.on("message", async msg => {
  try {
    const from = msg.from;
    const phone = from.split("@")[0];
    const isMedia = msg.hasMedia && msg.type !== "chat";

    if(msg.type === "chat") {
      const text = msg.body || "";
      recordMessage(phone, "in", text);
      await notifyTelegramText(`📩 رسالة واردة من: ${phone}\n\n${text}`);
    } else if(isMedia) {
      const media = await msg.downloadMedia();
      if(media && media.data) {
        const ext = (media.mimetype || "bin").split("/")[1] || "dat";
        const tempPath = path.join(DATA_DIR, `media_${Date.now()}.${ext}`);
        fs.writeFileSync(tempPath, Buffer.from(media.data, "base64"));
        recordMessage(phone, "in", `[media:${tempPath}]`);
        await notifyTelegramDocument(tempPath, `📩 وسائط واردة من ${phone}`);
      }
    }

    if(!whatsappActive){
      const offlineText = "أنا النسخة الرقمية من حامد وهو غير موجود";
      await client.sendMessage(from, offlineText);
      recordMessage(phone, "out", offlineText);
      await notifyTelegramText(`↩️ تم الرد أثناء الإيقاف إلى ${phone}: ${offlineText}`);
      return;
    }

    if(msg.type === "chat") {
      const reply = await buildReply(phone, msg.body);
      await client.sendMessage(from, reply);
      recordMessage(phone, "out", reply);
      await notifyTelegramText(`✅ تم الرد على ${phone}:\n\n${reply}`);
    }

  } catch(err) { console.error("Message handling error:", err); }
});

client.initialize();
