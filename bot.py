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
    """/start buyrug'iga javob beradi."""
    # Ma'lumotlar bazasi operatsiyasini bloklanmaydigan qilish
    try:
        await asyncio.to_thread(save_user, update.message.from_user)
    except Exception as e:
        logger.error(f"save_user funksiyasini chaqirishda xato: {e}")

    keyboard = [
        [InlineKeyboardButton("Animatsiyani ochish", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Quyidagi tugmani bosing:",
        reply_markup=reply_markup,
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
        web_app=WebAppInfo(url=url_with_text)
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"'{query}' matnli animatsiyani yuborish",
            input_message_content=InputTextMessageContent(
                f"Men '{query}' so'zi bilan ajoyib animatsiya yaratdim! Siz ham quyidagi tugmani bosib, o'zingiz uchun yarating:"
            ),
            reply_markup=reply_markup,
            description=f"'{query}' matnini animatsiya qilish",
            thumbnail_url="https://raw.githubusercontent.com/islombek4642/HeartAnimation/master/heart.png",
            thumbnail_width=64,
            thumbnail_height=64
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
                switch_inline_query_current_chat=user_text
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Matningiz bilan animatsiya yaratish uchun quyidagi tugmani bosing:",
        reply_markup=reply_markup,
    )


# --- Transkripsiya uchun yangi funksiyalar ---

async def transcriber_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/transcriber buyrug'iga javob beradi."""
    await update.message.reply_text(
        "Iltimos, matnga o'girish uchun audio, video yoki ovozli xabar yuboring."
    )

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

    status_message = await message.reply_text(f"{file_type.capitalize()} faylingiz qabul qilindi va qayta ishlanmoqda. Iltimos, kuting...")

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
        await status_message.edit_text(f"**Transkripsiya natijasi:**\n\n{transcription}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Media faylni qayta ishlashda xato: {e}", exc_info=True)
        await status_message.edit_text("Kechirasiz, faylingizni qayta ishlashda kutilmagan xatolik yuz berdi.")


def main() -> None:
    """Botni ishga tushiradi."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
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
