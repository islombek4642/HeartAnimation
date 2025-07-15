import logging
import uuid
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
import os
from dotenv import load_dotenv
import mysql.connector
from urllib.parse import urlparse, quote_plus
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, InlineQueryHandler
import asyncio
from transcriber import transcribe_audio
import telegram

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# .env faylidan kerakli ma'lumotlarni olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL")
MYSQL_PUBLIC_URL = os.getenv("MYSQL_PUBLIC_URL")

# Global o'zgaruvchilar
db_connection = None
db_cursor = None

def setup_database():
    """Ma'lumotlar bazasiga ulanishni sozlaydi."""
    global db_connection, db_cursor
    try:
        if MYSQL_PUBLIC_URL:
            url = urlparse(MYSQL_PUBLIC_URL)
            db_connection = mysql.connector.connect(
                host=url.hostname,
                user=url.username,
                password=url.password,
                database=url.path[1:],
                port=url.port
            )
            db_cursor = db_connection.cursor()
            logger.info("Ma'lumotlar bazasiga muvaffaqiyatli ulanildi.")

            # users jadvalini yaratish (agar mavjud bo'lmasa)
            db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Mavjud jadval uchun "id" ustunida AUTO_INCREMENT mavjudligini ta'minlash
            logger.info("'id' ustunida AUTO_INCREMENT xususiyatini tekshirish...")
            db_cursor.execute("ALTER TABLE users MODIFY COLUMN id INT AUTO_INCREMENT")
            logger.info("'id' ustuni AUTO_INCREMENT sifatida sozlandi.")

            # Barcha kerakli ustunlarni tekshirish va kerak bo'lsa qo'shish
            required_columns = {
                'user_id': 'BIGINT UNIQUE NOT NULL AFTER id',
                'first_name': 'VARCHAR(255)',
                'last_name': 'VARCHAR(255)',
                'username': 'VARCHAR(255)',
                'language_code': 'VARCHAR(10)'
            }

            for column, definition in required_columns.items():
                db_cursor.execute(f"SHOW COLUMNS FROM users LIKE '{column}'")
                if not db_cursor.fetchone():
                    logger.info(f"'{column}' ustuni topilmadi. Jadvalga qo'shilmoqda...")
                    db_cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                    logger.info(f"'{column}' ustuni muvaffaqiyatli qo'shildi.")

            db_connection.commit()
        else:
            logger.warning("MYSQL_PUBLIC_URL topilmadi. Ma'lumotlar bazasi funksiyalari o'chirilgan.")
    except mysql.connector.Error as err:
        logger.error(f"Ma'lumotlar bazasi xatosi: {err}")
        db_connection = None
        db_cursor = None

def save_user(user):
    """Foydalanuvchi ma'lumotlarini bazaga saqlaydi."""
    try:
        if not db_connection or not db_connection.is_connected():
            logger.info("Ma'lumotlar bazasi bilan aloqa yo'q. Qayta ulanishga harakat qilinmoqda...")
            setup_database()
        
        # Ulanishdan keyin ham kursor mavjudligini tekshirish
        if not db_cursor:
            logger.warning("DB ulanishi mavjud emas. Foydalanuvchi saqlanmadi.")
            return
    except Exception as e:
        logger.error(f"DB ulanishini tekshirishda xato: {e}")
        return # Ulanishda xato bo'lsa, funksiyadan chiqish

    try:
        # Foydalanuvchi mavjudligini tekshirish
        db_cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
        result = db_cursor.fetchone()

        if result:
            # Agar mavjud bo'lsa, ma'lumotlarni yangilash
            sql = """
            UPDATE users
            SET first_name = %s, last_name = %s, username = %s, language_code = %s
            WHERE user_id = %s
            """
            val = (user.first_name, user.last_name, user.username, user.language_code, user.id)
            db_cursor.execute(sql, val)
            logger.info(f"Foydalanuvchi {user.id} ma'lumotlari yangilandi.")
        else:
            # Agar mavjud bo'lmasa, yangi foydalanuvchi qo'shish
            sql = """
            INSERT INTO users (user_id, first_name, last_name, username, language_code)
            VALUES (%s, %s, %s, %s, %s)
            """
            val = (user.id, user.first_name, user.last_name, user.username, user.language_code)
            db_cursor.execute(sql, val)
            logger.info(f"Yangi foydalanuvchi {user.id} bazaga saqlandi.")

        db_connection.commit()

    except mysql.connector.Error as err:
        logger.error(f"Foydalanuvchini saqlashda xato: {err}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start buyrug'i uchun javob qaytaradi."""
    try:
        await asyncio.to_thread(save_user, update.message.from_user)
    except Exception as e:
        logger.error(f"start buyrug'ida save_user funksiyasini chaqirishda xato: {e}")

    await update.message.reply_text(
        "Salom! 👋\n\n"
        "Ismingiz, sevgan insoningiz ismi yoki istalgan so'zni yozing va men uni yurakchalar bilan bezalgan 💖 ajoyib animatsiyaga aylantirib beraman.\n\n"
        "Shunchaki matn yuboring va sehrni ko'ring! ✨\n\n"
        "*Qo'shimcha imkoniyat:* Audio/video xabarlarni matnga o'girish uchun /transcriber buyrug'ini ishlating. 🎤"
    )


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Foydalanuvchi bot nomini yozganda ishga tushadigan ichki so'rovni boshqaradi."""
    query = update.inline_query.query

    if not query:
        return

    encoded_text = quote_plus(query)
    url_with_text = f"{WEB_APP_URL}?text={encoded_text}"
    keyboard = [[InlineKeyboardButton(
        f"Animatsiyani ochish: '{query[:20]}...'",
        url=url_with_text
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"💖 Animatsiyani yuborish",
            description=f"'{query}' so'zi bilan sevgi ulashing!",
            input_message_content=InputTextMessageContent(
                f"Men '{query}' so'zi bilan ajoyib animatsiya yaratdim! ✨\n\nSiz ham o'zingiz uchun yaratib ko'ring! 👇"
            ),
            reply_markup=reply_markup,
            thumbnail_url="https://raw.githubusercontent.com/islombek4642/HeartAnimation/master/heart.png"
        )
    ]

    await update.inline_query.answer(results)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oddiy matnli xabarlarni qabul qiladi va matnli animatsiya uchun link yaratadi."""
    user_text = update.message.text
    encoded_text = quote_plus(user_text)
    url_with_text = f"{WEB_APP_URL}?text={encoded_text}"
    keyboard = [
        [
            InlineKeyboardButton(
                f"Animatsiyani ochish",
                web_app=WebAppInfo(url=url_with_text)
            ),
            InlineKeyboardButton(
                "Ulashish",
                switch_inline_query=user_text
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "✨ Ajoyib! Matningiz animatsiyaga tayyor.\n\nQuyidagi tugmalar orqali uni oching yoki do'stlaringizga ulashing 👇",
        reply_markup=reply_markup,
    )


# --- Transkripsiya uchun yangi funksiyalar ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help buyrug'i uchun yordam matnini ko'rsatadi."""
    await update.message.reply_text(
        "**Yordam kerakmi? 🤔 Mana men nimalar qila olaman:**\n\n"
        "**1. 💖 Animatsiyalari**\n"
        "Menga istalgan so'z yoki ismni yuboring, men uni yurakchalar bilan bezalgan chiroyli animatsiyaga aylantiraman. Do'stlaringizga ulashishni unutmang!\n\n"
        "**2. 🎤 Nutqni Matnga O'girish**\n"
        "Audio, video yoki ovozli xabar yuboring, men uni siz uchun matnga o'girib beraman. Buning uchun /transcriber buyrug'idan foydalaning."
    )


async def transcriber_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/transcriber buyrug'iga javob beradi."""
    await update.message.reply_text("Mengami? 🎧 Audio, video yoki ovozli xabaringizni yuboring, men uni siz uchun matnga o'girib beraman.")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Audio, video yoki ovozli xabarlarni qabul qilib, transkripsiya qiladi."""
    message = update.message
    file_id = None
    file_type = None

    if message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "ovozli xabar"

    if not file_id:
        return

    status_message = await message.reply_text(f"⏳ {file_type.capitalize()} faylingiz qabul qilindi. Uni matnga o'girishni boshlayapman... Bu biroz vaqt olishi mumkin.")

    try:
        file = await context.bot.get_file(file_id)
        
        # Faylni saqlash uchun unikal nom yaratish
        file_path = f"{file_id}.ogg"
        await file.download_to_drive(file_path)

        # Transkripsiya qilish (bu uzoq davom etishi mumkin)
        loop = asyncio.get_event_loop()
        transcription = await loop.run_in_executor(
            None, transcribe_audio, file_path
        )

        # Natijani yuborish
        if len(transcription) > 4000: # Telegram chegarasi 4096, ehtiyot uchun 4000
            await status_message.edit_text("✅ Tayyor! Natija juda uzun bo'lgani uchun qismlarga bo'lib yuborilmoqda...")
            parts = []
            while len(transcription) > 0:
                if len(transcription) > 4000:
                    split_pos = transcription.rfind(' ', 0, 4000)
                    if split_pos == -1: # Agar so'z topilmasa, majburan bo'lish
                        split_pos = 4000
                    parts.append(transcription[:split_pos])
                    transcription = transcription[split_pos:].lstrip()
                else:
                    parts.append(transcription)
                    break
            
            for part in parts:
                await message.reply_text(part)
        else:
            await status_message.edit_text(f"✅ Tayyor! Mana natija:\n\n> {transcription}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Media faylni qayta ishlashda xato: {e}", exc_info=True)
        # Xato turini tekshirish
        if isinstance(e, telegram.error.BadRequest) and "Message_too_long" in str(e):
             await status_message.edit_text("😔 Kechirasiz, transkripsiya matni juda uzun chiqdi va uni yuborib bo'lmadi.")
        else:
            await status_message.edit_text("😔 Kechirasiz, faylingizni qayta ishlashda xatolik yuz berdi. Iltimos, boshqa fayl bilan urinib ko'ring.")


def main() -> None:
    """Botni ishga tushiradi."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("transcriber", transcriber_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.VOICE, handle_media))
    application.add_handler(InlineQueryHandler(inline_query))

    # Botni ishga tushurish
    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    setup_database()
    main()
