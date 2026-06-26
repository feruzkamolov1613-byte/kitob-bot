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
        "welcome": "Salom! Men KitobAI — aqlli kitob botman! 📚\n\nFaqat PDF varianti mavjud bo'lgan kitoblarni tavsiya qilaman va topib beraman.",
        "choose_lang": "Tilni tanlang:",
        "recommend": "📚 Kitob tavsiya",
        "search": "🔍 Kitob qidirish",
        "change_lang": "🌐 Tilni o'zgartirish",
        "ask_genre": "Qaysi mavzu yoki janrda kitob kerak?\n\nMasalan: biznes, psixologiya, islom, fantastika...",
        "ask_search": "Qaysi kitobni qidirayapsiz? Kitob nomi yoki muallif ismini yozing.",
        "searching": "🔍 Qidiryapman va PDF mavjudligini tekshiryapman...",
        "thinking": "🤔 Faqat PDF bor kitoblarni saralab tayyorlayapman...",
        "back": "🔙 Orqaga",
        "download_btn": "📥 PDF Yuklab olish",
        "error": "Xatolik yuz berdi. Qayta urinib ko'ring.",
        "not_found": "Bu kitobning PDF varianti topilmadi. Boshqa nom yoki muallif bilan qidirib ko'ring.",
        "detail_loading": "📖 Ma'lumot va PDF link yuklanmoqda...",
        "no_pdf_books": "Afsuski, bu mavzuda PDF varianti mavjud bo'lgan kitob topilmadi. Boshqa mavzu sinab ko'ring.",
    },
    "ru": {
        "welcome": "Привет! Я KitobAI — умный книжный бот! 📚\n\nРекомендую только книги с доступным PDF вариантом.",
        "choose_lang": "Выберите язык:",
        "recommend": "📚 Рекомендовать книгу",
        "search": "🔍 Найти книгу",
        "change_lang": "🌐 Сменить язык",
        "ask_genre": "Какая тема или жанр вас интересует?\n\nНапример: бизнес, психология, ислам, фантастика...",
        "ask_search": "Какую книгу ищете? Напишите название или автора.",
        "searching": "🔍 Ищу и проверяю наличие PDF...",
        "thinking": "🤔 Подбираю только книги с PDF...",
        "back": "🔙 Назад",
        "download_btn": "📥 Скачать PDF",
        "error": "Произошла ошибка. Попробуйте ещё раз.",
        "not_found": "PDF вариант этой книги не найден. Попробуйте другое название.",
        "detail_loading": "📖 Загружаю информацию и ссылку на PDF...",
        "no_pdf_books": "К сожалению, по этой теме не найдено книг с PDF. Попробуйте другую тему.",
    },
    "en": {
        "welcome": "Hello! I'm KitobAI — your smart book bot! 📚\n\nI only recommend books that have an available PDF version.",
        "choose_lang": "Choose your language:",
        "recommend": "📚 Recommend a book",
        "search": "🔍 Find a book",
        "change_lang": "🌐 Change language",
        "ask_genre": "What topic or genre are you interested in?\n\nFor example: business, psychology, Islam, sci-fi...",
        "ask_search": "Which book are you looking for? Write the title or author.",
        "searching": "🔍 Searching and verifying PDF availability...",
        "thinking": "🤔 Preparing only books with PDF versions...",
        "back": "🔙 Back",
        "download_btn": "📥 Download PDF",
        "error": "An error occurred. Please try again.",
        "not_found": "No PDF version found for this book. Try another title or author.",
        "detail_loading": "📖 Loading details and PDF link...",
        "no_pdf_books": "Sorry, no books with PDF available on this topic. Try another topic.",
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


async def check_pdf_on_archive(title, author):
    """Internet Archive da haqiqiy PDF borligini tekshiradi va link qaytaradi"""
    try:
        query = f'title:"{title}" creator:"{author}" mediatype:texts'
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": query,
            "fl[]": ["identifier", "title"],
            "sort[]": "downloads desc",
            "rows": 5,
            "output": "json"
        }
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)
            data = r.json()
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier", "")
                if identifier:
                    pdf_url = f"https://archive.org/download/{identifier}/{identifier}.pdf"
                    # PDF haqiqatan borligini HEAD so'rov bilan tekshiramiz
                    head_r = await c.head(pdf_url, follow_redirects=True)
                    if head_r.status_code == 200:
                        return {"url": pdf_url, "identifier": identifier}
    except Exception:
        pass
    return None


async def get_book_list_with_pdf(topic, lang):
    """AI dan kitoblar so'raydi, keyin faqat PDF borlarini filtrlab qaytaradi"""
    desc_lang = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
    prompt = f"""You are a book expert. Give 10 REAL, famous books about "{topic}".

CRITICAL RULES:
- Use EXACT ORIGINAL book titles. NEVER translate titles to any other language.
- If the book was originally written in English, the title MUST be in English.
- If originally in Russian, title MUST be in Russian.
- Sort by global popularity.
- Write "desc" field ONLY in {desc_lang[lang]} language.
- Reply ONLY valid JSON array, nothing else:

[
  {{"title": "EXACT ORIGINAL TITLE", "author": "Full author name", "desc": "Short description in {desc_lang[lang]}"}}
]"""
    ans = await groq_ask(prompt)
    if not ans:
        return None
    try:
        start = ans.find('[')
        end = ans.rfind(']') + 1
        all_books = json.loads(ans[start:end])
    except Exception:
        return None

    # Har bir kitob uchun parallel ravishda PDF tekshiramiz
    tasks = []
    for book in all_books:
        tasks.append(check_pdf_on_archive(book["title"], book["author"]))

    results = await asyncio.gather(*tasks)

    # Faqat PDF topilgan kitoblarni qoldiramiz (maksimum 5 ta)
    pdf_books = []
    for book, pdf_info in zip(all_books, results):
        if pdf_info:
            book["pdf_url"] = pdf_info["url"]
            book["pdf_identifier"] = pdf_info["identifier"]
            pdf_books.append(book)
        if len(pdf_books) >= 5:
            break

    return pdf_books if pdf_books else None


async def search_single_book_pdf(text, lang):
    """Bitta kitob qidirish va PDF topish"""
    desc_lang = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
    prompt = f"""Find the EXACT original title and full author name for the book query: "{text}".

RULES:
- Return the ORIGINAL title (NEVER translate).
- If the book does NOT exist or you are unsure, reply ONLY: NOT_FOUND
- Otherwise reply ONLY in valid JSON:
{{"title": "EXACT ORIGINAL TITLE", "author": "Full author name"}}"""

    ans = await groq_ask(prompt)
    if not ans or "NOT_FOUND" in ans.upper():
        return None
    try:
        start = ans.find('{')
        end = ans.rfind('}') + 1
        book = json.loads(ans[start:end])
    except Exception:
        return None

    pdf_info = await check_pdf_on_archive(book["title"], book["author"])
    if not pdf_info:
        return None

    # Tezislar olish
    tezis_prompt = f"""Write 3-4 key theses about the book "{book['title']}" by {book['author']}.
Each thesis starts with ✦ symbol.
Write in {desc_lang[lang]} language."""
    tezis = await groq_ask(tezis_prompt)

    book["pdf_url"] = pdf_info["url"]
    book["pdf_identifier"] = pdf_info["identifier"]
    book["tezis"] = tezis or ""
    return book


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
    text = "📚 *Faqat PDF mavjud bo'lgan kitoblar:*\n\n"
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
            desc_lang_map = {"uz": "O'zbek", "ru": "Russian", "en": "English"}

            await q.edit_message_text(t(uid, "detail_loading"))

            tezis_prompt = f"""Write 3-4 key theses about the book "{book['title']}" by {book['author']}.
Each thesis starts with ✦ symbol.
Write in {desc_lang_map[lang]} language."""

            cover_url, tezis = await asyncio.gather(
                get_book_cover_url(book["title"], book["author"]),
                groq_ask(tezis_prompt)
            )

            final_tezis = tezis or book.get("tezis", "")
            text = f"📖 *{book['title']}*\n👤 _{book['author']}_\n\n{final_tezis}"

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(uid, "download_btn"), url=book["pdf_url"])],
                [InlineKeyboardButton(t(uid, "back"), callback_data="back_books")]
            ])

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
        books = await get_book_list_with_pdf(text, lang)
        if books:
            ctx.user_data["books"] = books
            msg_text, kb = build_book_list(uid, books)
            await m.edit_text(msg_text, parse_mode="Markdown", reply_markup=kb)
        else:
            await m.edit_text(t(uid, "no_pdf_books"), reply_markup=back_kb(uid))
        ctx.user_data["mode"] = None

    elif mode == "srch":
        m = await update.message.reply_text(t(uid, "searching"))
        result = await search_single_book_pdf(text, lang)
        if result:
            # Qidiruv natijasini ham books ga saqlaymiz (back_books uchun)
            ctx.user_data["books"] = [result]
            desc_lang_map = {"uz": "O'zbek", "ru": "Russian", "en": "English"}
            final_tezis = result.get("tezis", "")
            caption = f"📖 *{result['title']}*\n👤 _{result['author']}_\n\n{final_tezis}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(uid, "download_btn"), url=result["pdf_url"])],
                [InlineKeyboardButton(t(uid, "back"), callback_data="back")]
            ])
            cover_url = await get_book_cover_url(result["title"], result["author"])
            try:
                if cover_url:
                    await m.delete()
                    await update.message.reply_photo(photo=cover_url, caption=caption, parse_mode="Markdown", reply_markup=kb)
                else:
                    await m.edit_text(caption, parse_mode="Markdown", reply_markup=kb)
            except Exception:
                await m.edit_text(caption, parse_mode="Markdown", reply_markup=kb)
        else:
            await m.edit_text(t(uid, "not_found"), reply_markup=back_kb(uid))
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
