import os
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

user_lang = {}

TEXTS = {
    "uz": {
        "welcome": "Salom! Men KitobAI — aqlli kitob botman! 📚\n\nKitob tavsiya qilaman va elektron kitob topib beraman.",
        "choose_lang": "Tilni tanlang:",
        "recommend": "📚 Kitob tavsiya",
        "search": "🔍 Kitob qidirish",
        "change_lang": "🌐 Tilni o'zgartirish",
        "ask_genre": "Qaysi mavzu yoki janrda kitob kerak?\n\nMasalan: biznes, psixologiya, islom, fantastika...",
        "ask_search": "Qaysi kitobni qidirayapsiz? Kitob nomi yoki muallif ismini yozing.",
        "searching": "🔍 Qidiryapman...",
        "thinking": "🤔 Tavsiyalar tayyorlanmoqda...",
        "back": "🔙 Orqaga",
        "download": "📥 Yuklab olish uchun saytlar:",
    },
    "ru": {
        "welcome": "Привет! Я KitobAI — умный книжный бот! 📚\n\nРекомендую книги и помогаю найти электронные версии.",
        "choose_lang": "Выберите язык:",
        "recommend": "📚 Рекомендовать книгу",
        "search": "🔍 Найти книгу",
        "change_lang": "🌐 Сменить язык",
        "ask_genre": "Какая тема или жанр вас интересует?\n\nНапример: бизнес, психология, ислам, фантастика...",
        "ask_search": "Какую книгу ищете? Напишите название или автора.",
        "searching": "🔍 Ищу...",
        "thinking": "🤔 Готовлю рекомендации...",
        "back": "🔙 Назад",
        "download": "📥 Сайты для скачивания:",
    },
    "en": {
        "welcome": "Hello! I'm KitobAI — your smart book bot! 📚\n\nI recommend books and help find digital versions.",
        "choose_lang": "Choose your language:",
        "recommend": "📚 Recommend a book",
        "search": "🔍 Find a book",
        "change_lang": "🌐 Change language",
        "ask_genre": "What topic or genre are you interested in?\n\nFor example: business, psychology, Islam, sci-fi...",
        "ask_search": "Which book are you looking for? Write the title or author.",
        "searching": "🔍 Searching...",
        "thinking": "🤔 Preparing recommendations...",
        "back": "🔙 Back",
        "download": "📥 Download sites:",
    }
}


def get_lang(uid): return user_lang.get(uid, "uz")
def t(uid, key): return TEXTS[get_lang(uid)].get(key, "")


def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]])


def main_kb(uid):
    lang = get_lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXTS[lang]["recommend"], callback_data="rec")],
        [InlineKeyboardButton(TEXTS[lang]["search"], callback_data="srch")],
        [InlineKeyboardButton(TEXTS[lang]["change_lang"], callback_data="lang")]
    ])


def back_kb(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "back"), callback_data="back")]])


async def gemini(prompt):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(GEMINI_URL, json={"contents": [{"parts": [{"text": prompt}]}]})
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Xatolik: {e}"


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📚 KitobAI\n\nTilni tanlang / Выберите язык / Choose language:", reply_markup=lang_kb())


async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data

    if d.startswith("lang_"):
        user_lang[uid] = d.split("_")[1]
        await q.edit_message_text(t(uid, "welcome"), reply_markup=main_kb(uid))
    elif d == "lang":
        await q.edit_message_text(t(uid, "choose_lang"), reply_markup=lang_kb())
    elif d == "rec":
        ctx.user_data["mode"] = "rec"
        await q.edit_message_text(t(uid, "ask_genre"))
    elif d == "srch":
        ctx.user_data["mode"] = "srch"
        await q.edit_message_text(t(uid, "ask_search"))
    elif d == "back":
        ctx.user_data["mode"] = None
        await q.edit_message_text(t(uid, "welcome"), reply_markup=main_kb(uid))


async def msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    mode = ctx.user_data.get("mode")
    lang = get_lang(uid)

    if mode == "rec":
        m = await update.message.reply_text(t(uid, "thinking"))
        prompts = {
            "uz": f'"{text}" mavzusida 5 ta eng yaxshi kitob tavsiya qil. Har biri: nom, muallif, 1-2 qator tavsif. O\'zbek tilida.',
            "ru": f'Порекомендуй 5 лучших книг на тему "{text}". Каждая: название, автор, 1-2 строки. На русском.',
            "en": f'Recommend 5 best books about "{text}". Each: title, author, 1-2 lines. In English.'
        }
        ans = await gemini(prompts[lang])
        await m.edit_text(f"📚\n\n{ans}", reply_markup=back_kb(uid))
        ctx.user_data["mode"] = None

    elif mode == "srch":
        m = await update.message.reply_text(t(uid, "searching"))
        prompts = {
            "uz": f'"{text}" kitobini topib ber: to\'liq nomi, muallifi, qisqa mazmuni (2-3 gap), janri, yili. O\'zbek tilida.',
            "ru": f'Найди книгу "{text}": полное название, автор, краткое содержание (2-3 предложения), жанр, год. На русском.',
            "en": f'Find the book "{text}": full title, author, brief summary (2-3 sentences), genre, year. In English.'
        }
        ans = await gemini(prompts[lang])
        sites = "• z-lib.id\n• archive.org\n• pdfdrive.com\n• t.me/kitoblar_uz"
        await m.edit_text(f"📖\n\n{ans}\n\n{t(uid, 'download')}\n{sites}", reply_markup=back_kb(uid))
        ctx.user_data["mode"] = None

    else:
        await update.message.reply_text(t(uid, "welcome"), reply_markup=main_kb(uid))


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    print("✅ KitobAI ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
