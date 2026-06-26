import os
import json
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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
        "error": "Xatolik yuz berdi. Qayta urinib ko'ring.",
        "not_found": "Bu kitob topilmadi. To'g'ri nom yoki muallif ismini kiriting.",
        "detail_loading": "📖 Ma'lumot yuklanmoqda...",
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
        "error": "Произошла ошибка. Попробуйте ещё раз.",
        "not_found": "Книга не найдена. Введите правильное название или имя автора.",
        "detail_loading": "📖 Загружаю информацию...",
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
        "error": "An error occurred. Please try again.",
        "not_found": "Book not found. Please enter correct title or author name.",
        "detail_loading": "📖 Loading details...",
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


async def groq_ask(prompt):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                    "temperature": 0.3
                }
            )
            data = r.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None


async def get_book_list_json(topic, lang):
    desc_lang = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
    prompt = f"""You are a book expert. Give 5 REAL, famous books about "{topic}".
Sort by global popularity rating - most popular book MUST be first.
Use ORIGINAL book titles (do not translate titles).
Write the "desc" field in {desc_lang[lang]} language.
Reply ONLY in valid JSON array format, nothing else:
[
  {{"title": "Original title", "author": "Full author name", "desc": "1 line description in {desc_lang[lang]}"}},
  {{"title": "Original title", "author": "Full author name", "desc": "1 line description in {desc_lang[lang]}"}},
  {{"title": "Original title", "author": "Full author name", "desc": "1 line description in {desc_lang[lang]}"}},
  {{"title": "Original title", "author": "Full author name", "desc": "1 line description in {desc_lang[lang]}"}},
  {{"title": "Original title", "author": "Full author name", "desc": "1 line description in {desc_lang[lang]}"}}
]"""
    ans = await groq_ask(prompt)
    if not ans:
        return None
    try:
        start = ans.find('[')
        end = ans.rfind(']') + 1
        return json.loads(ans[start:end])
    except Exception:
        return None


async def get_book_cover_url(title, author):
    try:
        query = f"{title} {author}".replace(" ", "+")
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
            data = r.json()
            items = data.get("items", [])
            if items:
                img = items[0].get("volumeInfo", {}).get("imageLinks", {})
                return img.get("thumbnail") or img.get("smallThumbnail")
    except Exception:
        pass
    return None


def build_book_list(uid, books):
    text = "📚\n\n"
    buttons = []
    for i, book in enumerate(books):
        text += f"*{i+1}. {book['title']}*\n_{book['author']}_\n{book['desc']}\n\n"
        buttons.append([InlineKeyboardButton(f"📖 {book['title']}", callback_data=f"book_{i}")])
    buttons.append([InlineKeyboardButton(t(uid, "back"), callback_data="back")])
    return text, InlineKeyboardMarkup(buttons)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 KitobAI\n\nTilni tanlang / Выберите язык / Choose language:",
        reply_markup=lang_kb()
    )


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
    elif d.startswith("book_"):
        idx = int(d.split("_")[1])
        books = ctx.user_data.get("books", [])
        if idx < len(books):
            book = books[idx]
            lang = get_lang(uid)
            desc_lang = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
            tezis_prompt = f"""Write 3-4 key theses about the book "{book['title']}" by {book['author']}.
Each thesis starts with ✦ symbol.
Write in {desc_lang[lang]} language."""

            cover_url, tezis = await asyncio.gather(
                get_book_cover_url(book["title"], book["author"]),
                groq_ask(tezis_prompt)
            )

            sites = "• z-lib.id\n• archive.org\n• pdfdrive.com"
            text = f"📖 *{book['title']}*\n👤 _{book['author']}_\n\n{tezis or ''}\n\n{t(uid, 'download')}\n{sites}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "back"), callback_data="back_books")]])

            try:
                if cover_url:
                    await q.message.reply_photo(photo=cover_url, caption=text, parse_mode="Markdown", reply_markup=kb)
                else:
                    await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
            except Exception:
                await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "back_books":
        books = ctx.user_data.get("books", [])
        if books:
            msg_text, kb = build_book_list(uid, books)
            await q.edit_message_text(msg_text, parse_mode="Markdown", reply_markup=kb)


async def msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    mode = ctx.user_data.get("mode")
    lang = get_lang(uid)

    if mode == "rec":
        m = await update.message.reply_text(t(uid, "thinking"))
        books = await get_book_list_json(text, lang)
        if books:
            ctx.user_data["books"] = books
            msg_text, kb = build_book_list(uid, books)
            await m.edit_text(msg_text, parse_mode="Markdown", reply_markup=kb)
        else:
            await m.edit_text(t(uid, "error"), reply_markup=back_kb(uid))
        ctx.user_data["mode"] = None

    elif mode == "srch":
        m = await update.message.reply_text(t(uid, "searching"))
        desc_lang = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
        prompt = f"""Find the book "{text}". If it REALLY EXISTS provide:
- Exact original title
- Full author name
- Brief summary (2-3 sentences) in {desc_lang[lang]}
- Genre
- Year published
Write in {desc_lang[lang]} language.
If not found or unsure, write only: NOT FOUND"""
        ans = await groq_ask(prompt)
        if ans:
            if "NOT FOUND" in ans.upper() or "TOPILMADI" in ans.upper():
                await m.edit_text(t(uid, "not_found"), reply_markup=back_kb(uid))
            else:
                sites = "• z-lib.id\n• archive.org\n• pdfdrive.com\n• t.me/kitoblar_uz"
                await m.edit_text(f"📖\n\n{ans}\n\n{t(uid, 'download')}\n{sites}", reply_markup=back_kb(uid))
        else:
            await m.edit_text(t(uid, "error"), reply_markup=back_kb(uid))
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
