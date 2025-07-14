import logging
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
import os
from dotenv import load_dotenv
import mysql.connector
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# .env faylidan token va URL'ni o'qib olish
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL")

# Token yoki URL topilmasa, xatolik berish
if not BOT_TOKEN or not WEB_APP_URL:
    raise ValueError("Iltimos, .env fayliga BOT_TOKEN va WEB_APP_URL o'zgaruvchilarini kiriting.")

# Ma'lumotlar bazasi sozlamalari
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_PORT = os.getenv("DB_PORT")

def setup_database():
    """Ma'lumotlar bazasiga ulanadi va kerakli jadvalni yaratadi."""
    try:
        db = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT
        )
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                first_name VARCHAR(255) NOT NULL,
                last_name VARCHAR(255),
                username VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        logger.info("Ma'lumotlar bazasi muvaffaqiyatli sozlandi.")
    except mysql.connector.Error as err:
        logger.error(f"Database Error: {err}")

def save_user(user):
    """Foydalanuvchi ma'lumotlarini bazaga saqlaydi."""
    try:
        db = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT
        )
        cursor = db.cursor()
        sql = """
            INSERT INTO users (id, first_name, last_name, username)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE first_name=%s, last_name=%s, username=%s
        """
        val = (
            user.id, user.first_name, user.last_name, user.username,
            user.first_name, user.last_name, user.username
        )
        cursor.execute(sql, val)
        db.commit()
        logger.info(f"{user.id} ID'li foydalanuvchi bazaga saqlandi.")
    except mysql.connector.Error as err:
        logger.error(f"Foydalanuvchini saqlashda xatolik: {err}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Foydalanuvchi ma'lumotlarini saqlash
    save_user(update.message.from_user)
    """Foydalanuvchi /start buyrug'ini yuborganda web ilovani ochuvchi tugmani jo'natadi."""
    keyboard = [
        [KeyboardButton("Open Heart Animation ❤️", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Quyidagi tugmani bosing:",
        reply_markup=reply_markup,
    )

def main() -> None:
    """Botni ishga tushiradi."""
    # Ilovani yaratish
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start buyrug'i uchun handler qo'shish
    application.add_handler(CommandHandler("start", start))

    # Botni ishga tushirish
    logger.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    # Botni ishga tushirishdan oldin bazani sozlash
    setup_database()
    main()
