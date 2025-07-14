from faster_whisper import WhisperModel
import os
import logging

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Modelni optimallashtirish bilan yuklash
try:
    # Modelni faqat bir marta yuklash uchun global o'zgaruvchi
    logging.info("Whisper modelini yuklash boshlandi...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    logging.info("Whisper modeli muvaffaqiyatli yuklandi.")
except Exception as e:
    logging.error(f"Whisper modelini yuklashda xatolik: {e}")
    model = None

def transcribe_audio(file_path: str) -> str:
    """
    Berilgan audio/video faylni matnga o'giradi va kengaytirilgan xatolik tekshiruvini amalga oshiradi.

    Args:
        file_path: Transkripsiya qilinadigan faylning yo'li.

    Returns:
        Faylning matnga o'girilgan shakli yoki xatolik haqida tushunarli xabar.
    """
    if model is None:
        return "Xatolik: Transkripsiya modeli yuklanmagan. Iltimos, server loglarini tekshiring."

    if not os.path.exists(file_path):
        logging.error(f"Fayl topilmadi: {file_path}")
        return "Kechirasiz, yuborilgan faylni qayta ishlashda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."

    try:
        logging.info(f"'{os.path.basename(file_path)}' faylini transkripsiya qilish boshlandi...")
        segments, info = model.transcribe(file_path, beam_size=5)

        logging.info(f"Aniqlangan til: '{info.language}' (ehtimollik: {info.language_probability:.2f})")

        transcription = "".join(segment.text for segment in segments).strip()

        if not transcription:
            logging.warning(f"'{os.path.basename(file_path)}' faylida nutq topilmadi.")
            return "Kechirasiz, yuborilgan faylda hech qanday nutq aniqlanmadi."

        logging.info(f"Transkripsiya muvaffaqiyatli yakunlandi.")
        return transcription

    except Exception as e:
        logging.error(f"Transkripsiya jarayonida kutilmagan xatolik: {e}", exc_info=True)
        # Foydalanuvchiga texnik tafsilotlarni ko'rsatmaslik kerak
        return "Kechirasiz, faylni transkripsiya qilishda kutilmagan xatolik yuz berdi. Fayl formati to'g'ri ekanligiga ishonch hosil qiling (masalan, MP3, MP4, WAV, OGG)."
    finally:
        # Ishlov berib bo'lingandan so'ng faylni o'chirish
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Vaqtinchalik fayl o'chirildi: {file_path}")
            except OSError as e:
                logging.error(f"Vaqtinchalik faylni o'chirishda xatolik: {e}")
