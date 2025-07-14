import logging
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
import os
from dotenv import load_dotenv
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    main()
