import logging
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import os
from dotenv import load_dotenv
import mysql.connector
from urllib.parse import urlparse, quote_plus
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
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
                user_id BIGINT UNIQUE NOT NULL,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                username VARCHAR(255),
                language_code VARCHAR(10),
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            db_connection.commit()
        else:
            logger.warning("MYSQL_PUBLIC_URL topilmadi. Ma'lumotlar bazasi funksiyalari o'chirilgan.")
    except mysql.connector.Error as err:
        logger.error(f"Ma'lumotlar bazasi xatosi: {err}")
        db_connection = None
        db_cursor = None

def save_user(user):
    """Foydalanuvchi ma'lumotlarini bazaga saqlaydi."""
    if not db_cursor:
        logger.warning("DB ulanishi mavjud emas. Foydalanuvchi saqlanmadi.")
        return

    try:
        sql = """
        INSERT INTO users (user_id, first_name, last_name, username, language_code)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        first_name = VALUES(first_name), last_name = VALUES(last_name), username = VALUES(username)
        """
        val = (user.id, user.first_name, user.last_name, user.username, user.language_code)
        db_cursor.execute(sql, val)
        db_connection.commit()
        logger.info(f"Foydalanuvchi {user.id} bazaga saqlandi/yangilandi.")
    except mysql.connector.Error as err:
        logger.error(f"Foydalanuvchini saqlashda xato: {err}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start buyrug'iga javob beradi."""
    save_user(update.message.from_user)
    keyboard = [
        [InlineKeyboardButton("Animatsiyani ochish", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Quyidagi tugmani bosing:",
        reply_markup=reply_markup,
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oddiy matnli xabarlarni qabul qiladi va matnli animatsiya uchun link yaratadi."""
    user_text = update.message.text
    encoded_text = quote_plus(user_text)
    url_with_text = f"{WEB_APP_URL}?text={encoded_text}"
    keyboard = [
        [
            InlineKeyboardButton(
                f"'{user_text[:25]}...' matnli animatsiyani ochish",
                web_app=WebAppInfo(url=url_with_text)
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

    # Botni ishga tushurish
    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    setup_database()
    main()
