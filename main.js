const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const fs = require('fs');
const express = require('express');
const axios = require('axios');

const app = express();
const port = process.env.PORT || 3000;

const client = new Client();

// قاعدة بيانات لتخزين المستخدمين والمحادثات
const USERS_FILE = './users.json';
let usersDB = {};
if (fs.existsSync(USERS_FILE)) {
    usersDB = JSON.parse(fs.readFileSync(USERS_FILE));
}

let qrImageData = '';

// قراءة المفاتيح من Secrets في Replit
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_OWNER_ID = process.env.TELEGRAM_OWNER_ID;
const OPENROUTER_KEY = process.env.OPENROUTER_KEY;

// Telegram bot لمتابعة الرسائل (اختياري)
const TelegramBot = require('node-telegram-bot-api');
const telegramBot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });

// توليد QR Code
client.on('qr', async (qr) => {
    qrImageData = await qrcode.toDataURL(qr);
    telegramBot.sendMessage(TELEGRAM_OWNER_ID, 'تم توليد QR Code جديد! افتح Web Preview لمسحه.');
});

// جاهزية WhatsApp
client.on('ready', () => {
    console.log('WhatsApp bot جاهز ✅');
    telegramBot.sendMessage(TELEGRAM_OWNER_ID, 'WhatsApp bot جاهز ✅');
});

// استقبال الرسائل
client.on('message', async msg => {
    const userId = msg.from;
    const userMessage = msg.body;

    if (!usersDB[userId]) usersDB[userId] = [];
    const history = usersDB[userId].join('\n');

    const reply = await getAIReply(userId, userMessage, history);

    await msg.reply(reply);

    usersDB[userId].push(`User: ${userMessage}`);
    usersDB[userId].push(`Hamed: ${reply}`);
    fs.writeFileSync(USERS_FILE, JSON.stringify(usersDB, null, 2));

    telegramBot.sendMessage(TELEGRAM_OWNER_ID, `رسالة من: ${userId}\nالمحتوى: ${userMessage}\nالرد: ${reply}`);
});

// Web preview لعرض QR Code
app.get('/', (req, res) => {
    if (qrImageData) {
        res.send(`<h2>امسح QR Code لتسجيل WhatsApp</h2><img src="${qrImageData}" />`);
    } else {
        res.send('<h2>جاري توليد QR Code...</h2>');
    }
});

// تشغيل السيرفر
app.listen(port, () => console.log(`Web preview QR Code: http://localhost:${port}`));

// تهيئة WhatsApp client
client.initialize();

// دالة OpenRouter API
async function getAIReply(userName, userMessage, history) {
    const prompt = `
أنت النسخة الرقمية من حامد، ودود، صبور، ذكي، محترف، وتحلل كل شيء بعقلانية وهدوء. 
يجب أن تتحدث كما لو كنت حامد بالضبط، بنفس أسلوبه في الكتابة والتفكير، وتشمل ردودك:

1. التحية والاحترام.
2. محاولة فهم احتياجات الشخص.
3. تحليل الرسالة بمنطق وذكاء.
4. تقديم الحل أو النصيحة بطريقة ودية وواقعية.
5. إضافة لمسة شخصية تعكس شخصية حامد.
6. عدم ذكر أنك بوت أو ذكاء اصطناعي أبدًا.
7. إذا سألك أحد عن هويتك، قل أنك النسخة الرقمية من حامد، وأنه غير موجود حاليًا.
8. الحفاظ على سجل المحادثة والرجوع إليه لفهم سياق الحديث.

المستخدم: ${userName}
الرسالة الأخيرة: ${userMessage}
سجل المحادثة السابق: ${history || 'لا يوجد'}.

أجب بطريقة شاملة ومفصلة، بحيث يشعر المستخدم أنه يتحدث مباشرة مع حامد.
`;

    try {
        const response = await axios.post('https://api.openrouter.ai/v1/chat/completions', {
            model: "gpt-4o-mini",
            messages: [{ role: "user", content: prompt }]
        }, {
            headers: {
                'Authorization': `Bearer ${OPENROUTER_KEY}`,
                'Content-Type': 'application/json'
            }
        });

        return response.data.choices[0].message.content;
    } catch (err) {
        console.error('OpenRouter API error:', err);
        return 'آسف، حدث خطأ مؤقت. حاول لاحقًا.';
    }
}
