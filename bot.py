import logging
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
import os
from dotenv import load_dotenv
import mysql.connector
from urllib.parse import urlparse, quote_plus, urlencode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

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
DATABASE_URL = os.getenv("MYSQL_PUBLIC_URL")
if not DATABASE_URL:
    raise ValueError("MYSQL_PUBLIC_URL o'zgaruvchisi .env faylida yoki hosting sozlamalarida topilmadi.")

# URL'ni qismlarga ajratish
try:
    url = urlparse(DATABASE_URL)
    db_config = {
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'database': url.path[1:],  # Boshidagi '/' belgisini olib tashlash
        'port': url.port
    }
except Exception as e:
    logger.error(f"DATABASE_URL ni o'qishda xatolik: {e}")
    raise ValueError("DATABASE_URL noto'g'ri formatda.")


def get_db_connection():
    """Ma'lumotlar bazasiga ulanishni yaratadi va qaytaradi."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Ma'lumotlar bazasiga ulanishda xatolik: {err}")
        return None

def setup_database():
    """'users' jadvalini (agar mavjud bo'lmasa) yaratadi."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    first_name VARCHAR(255) NOT NULL,
                    last_name VARCHAR(255),
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("Ma'lumotlar bazasi muvaffaqiyatli sozlandi.")
        except mysql.connector.Error as err:
            logger.error(f"Baza sozlashda xatolik: {err}")
        finally:
            conn.close()

def save_user(user):
    """Foydalanuvchi ma'lumotlarini bazaga saqlaydi."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
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
            conn.commit()
            logger.info(f"{user.id} ID'li foydalanuvchi bazaga saqlandi.")
        except mysql.connector.Error as err:
            logger.error(f"Foydalanuvchini saqlashda xatolik: {err}")
        finally:
            conn.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oddiy matnli xabarlarni qabul qiladi va matnli animatsiya uchun link yaratadi."""
    user_text = update.message.text
    # Matnni URL uchun xavfsiz formatga o'tkazish
    encoded_text = quote_plus(user_text)

    # Matn bilan maxsus URL yaratish
    url_with_text = f"{WEB_APP_URL}?text={encoded_text}"

    # Web App tugmasini yaratish
    keyboard = [
        [InlineKeyboardButton(
            f"'{user_text[:25]}...' matnli animatsiyani ochish",
            web_app=WebAppInfo(url=url_with_text)
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Foydalanuvchiga javob yuborish
    await update.message.reply_text(
        "Matningiz bilan animatsiya yaratish uchun quyidagi tugmani bosing:",
        reply_markup=reply_markup,
    )


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

    # Oddiy matnli xabarlar uchun handler qo'shish
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Botni ishga tushirish
    logger.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    # Botni ishga tushirishdan oldin bazani sozlash
    setup_database()
    main()
