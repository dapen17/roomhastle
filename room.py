import asyncio
import os
import httpx
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, ConversationHandler
)

# Load token dari file .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Token bot tidak ditemukan. Pastikan BOT_TOKEN ada di file .env.")

# States untuk ConversationHandler
AGE = range(1)

# Database sementara
users = {}  # Menyimpan data pengguna
rooms = {}  # Menyimpan pasangan yang sedang chatting
timers = {}  # Menyimpan timer untuk setiap room

# Function to handle retry logic for HTTP requests
async def send_message_with_retry(bot, chat_id, text, retries=3, delay=2):
    """Mengirim pesan dengan mekanisme retry jika terjadi error httpx."""
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id, text)
            return  # Berhenti jika berhasil
        except httpx.RemoteProtocolError as e:
            # Menangani kesalahan khusus httpx
            if attempt < retries - 1:
                await asyncio.sleep(delay)  # Tunggu sebelum mencoba lagi
            else:
                raise e  # Jika sudah mencapai maksimal retry, lempar error
        except Exception as e:
            # Tangani exception lain (misalnya network error)
            if attempt < retries - 1:
                await asyncio.sleep(delay)  # Tunggu sebelum mencoba lagi
            else:
                raise e

async def start(update: Update, context: CallbackContext):
    """Memulai bot dan memberikan informasi perintah yang tersedia."""
    await update.message.reply_text(
        "Halo! Selamat datang di matchmaking bot.\n\n"
        "Berikut adalah perintah yang tersedia:\n"
        "/start - Mulai percakapan dan cari pasangan\n"
        "/new - Memulai ulang percakapan dan mencari pasangan baru\n"
        "/stop - Menghentikan percakapan saat ini\n"
        "/next - Mencari pasangan baru dengan kategori umur yang sama\n"
        "/help - Menampilkan perintah yang tersedia\n\n"
        "Berapa umurmu? Pilih kategori:\n"
        "1. Di bawah 18 tahun\n"
        "2. Di atas 18 tahun\n"
        "NOTE : TIDAK BISA MENGIRIM GAMBAR, STIKER ATAU VOICENOTE",
        reply_markup=ReplyKeyboardMarkup([["Di bawah 18 tahun", "Di atas 18 tahun"]], one_time_keyboard=True)
    )
    return AGE

async def help_command(update: Update, context: CallbackContext):
    """Menampilkan perintah yang tersedia."""
    await update.message.reply_text(
        "Berikut adalah perintah yang tersedia:\n"
        "/start - Mulai percakapan dan cari pasangan\n"
        "/new - Memulai ulang percakapan dan mencari pasangan baru\n"
        "/stop - Menghentikan percakapan saat ini\n"
        "/next - Mencari pasangan baru dengan kategori umur yang sama\n"
        "/help - Menampilkan perintah yang tersedia"
    )

async def new(update: Update, context: CallbackContext):
    """Memulai ulang percakapan dari awal dengan menghapus data pengguna.""" 
    user_id = update.effective_user.id

    # Hapus data pengguna yang ada
    if user_id in users:
        del users[user_id]

    # Mulai percakapan dari awal
    await update.message.reply_text(
        "Silakan pilih kategori umur kamu. (Di bawah 18 tahun / Di atas 18 tahun)",
        reply_markup=ReplyKeyboardMarkup([["Di bawah 18 tahun", "Di atas 18 tahun"]], one_time_keyboard=True)
    )
    return AGE

async def set_age(update: Update, context: CallbackContext):
    """Menyimpan umur dan mencoba mencocokkan pengguna."""
    age_category = update.message.text.lower()
    if age_category not in ["di bawah 18 tahun", "di atas 18 tahun"]:
        await update.message.reply_text("Silakan pilih kategori umur yang valid.")
        return AGE

    context.user_data['age'] = age_category
    user_id = update.effective_user.id

    # Simpan data pengguna
    users[user_id] = {
        "age": context.user_data['age'],
        "matched": False,
    }
    await update.message.reply_text("Data kamu telah disimpan. Kami akan mencarikan pasangan untukmu.")
    await match_user(update, context, user_id)
    return ConversationHandler.END

async def match_user(update: Update, context: CallbackContext, user_id):
    """Mencocokkan pengguna berdasarkan kategori umur."""
    user_data = users[user_id]
    
    # Cari pasangan yang cocok
    for other_id, other_data in users.items():
        if not other_data["matched"] and \
           other_data["age"] == user_data["age"] and \
           other_id != user_id:
            # Pasangkan
            rooms[user_id] = other_id
            rooms[other_id] = user_id
            users[user_id]["matched"] = True
            users[other_id]["matched"] = True
            await send_message_with_retry(context.bot, user_id, "Anda telah dipasangkan! Mulai chat sekarang.")
            await send_message_with_retry(context.bot, other_id, "Anda telah dipasangkan! Mulai chat sekarang.")
            
            # Mulai timer untuk pasangan ini
            timers[user_id] = asyncio.create_task(chat_timer(update, context, user_id, other_id))
            timers[other_id] = timers[user_id]
            return

    # Jika belum ada pasangan
    await send_message_with_retry(context.bot, user_id, "Belum ada pasangan yang cocok. Mohon tunggu.")

async def chat_timer(update: Update, context: CallbackContext, user_id, partner_id):
    """Timer selama 10 menit untuk chat dengan peringatan di 5 menit dan 1 menit."""
    await asyncio.sleep(300)  # Tunggu 5 menit
    await send_message_with_retry(context.bot, user_id, "Sisa waktu 5 menit lagi.")
    await send_message_with_retry(context.bot, partner_id, "Sisa waktu 5 menit lagi.")

    await asyncio.sleep(240)  # Tunggu 4 menit lagi (total 9 menit)
    await send_message_with_retry(context.bot, user_id, "Sisa waktu 1 menit lagi.")
    await send_message_with_retry(context.bot, partner_id, "Sisa waktu 1 menit lagi.")

    await asyncio.sleep(60)  # Tunggu 1 menit lagi (total 10 menit)
    await send_message_with_retry(context.bot, user_id, "Waktu percakapan telah selesai.")
    await send_message_with_retry(context.bot, partner_id, "Waktu percakapan telah selesai.")
    await stop_conversation(update, context, user_id, partner_id)

async def stop(update: Update, context: CallbackContext):
    """Fitur untuk berhenti dari percakapan."""
    user_id = update.effective_user.id
    if user_id in rooms:
        partner_id = rooms[user_id]
        await stop_conversation(update, context, user_id, partner_id)
    else:
        await update.message.reply_text("Anda belum memiliki pasangan yang bisa dihentikan.")

async def stop_conversation(update: Update, context: CallbackContext, user_id, partner_id):
    """Menghentikan percakapan dan menghapus data terkait."""
    if user_id in rooms:
        del rooms[user_id]
    if partner_id in rooms:
        del rooms[partner_id]
    
    if user_id in timers:
        timers[user_id].cancel()  # Hentikan timer
        del timers[user_id]
    if partner_id in timers:
        timers[partner_id].cancel()  # Hentikan timer
        del timers[partner_id]
    
    # Kirim pesan pemberitahuan
    await send_message_with_retry(context.bot, user_id, "Percakapan telah dihentikan.")
    await send_message_with_retry(context.bot, partner_id, "Percakapan telah dihentikan.")

async def next_match(update: Update, context: CallbackContext):
    """Mencari pasangan baru dengan kategori yang sama, tapi bukan pasangan yang lama."""
    user_id = update.effective_user.id
    
    if user_id in users:
        age_category = users[user_id]['age']
        
        # Menghentikan percakapan lama jika ada
        if user_id in rooms:
            partner_id = rooms[user_id]
            await stop_conversation(update, context, user_id, partner_id)

        # Cari pasangan baru yang memiliki kategori umur dan gender berbeda
        await match_user(update, context, user_id)
    else:
        await update.message.reply_text("Anda belum memiliki pasangan. Harap tunggu sampai dipasangkan.")

async def message_handler(update: Update, context: CallbackContext):
    """Meneruskan pesan antar pengguna yang dipasangkan."""
    user_id = update.effective_user.id
    if user_id in rooms:
        partner_id = rooms[user_id]
        await send_message_with_retry(context.bot, partner_id, update.message.text)
    else:
        await update.message.reply_text("Anda belum memiliki pasangan. Ingin mencari pasangan harap melakukan /start lagi.")

async def main():
    """Main function untuk menjalankan bot.""" 
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("new", new)],  # Menambahkan /new
        states={  
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
        },
        fallbacks=[CommandHandler("stop", stop), CommandHandler("next", next_match)],  # Menambahkan perintah next
    )

async def media_handler(update: Update, context: CallbackContext):
    """Meneruskan stiker, gambar, dan voice note antar pasangan."""
    user_id = update.effective_user.id
    if user_id in rooms:
        partner_id = rooms[user_id]

        # Cek tipe media
        if update.message.sticker:
            await context.bot.send_sticker(partner_id, update.message.sticker.file_id)
        elif update.message.photo:
            await context.bot.send_photo(partner_id, update.message.photo[-1].file_id, caption=update.message.caption)
        elif update.message.voice:
            await context.bot.send_voice(partner_id, update.message.voice.file_id)
        else:
            await update.message.reply_text("Media tidak didukung.")
    else:
        await update.message.reply_text("Anda belum memiliki pasangan. Gunakan /start untuk mencari pasangan.")

async def main():
    """Main function untuk menjalankan bot.""" 
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("new", new)],  # Menambahkan /new
        states={  
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
        },
        fallbacks=[CommandHandler("stop", stop), CommandHandler("next", next_match)],  # Menambahkan perintah next
    )

    # Tambahkan semua handler
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.STICKER, media_handler))
    application.add_handler(MessageHandler(filters.PHOTO, media_handler))
    application.add_handler(MessageHandler(filters.VOICE, media_handler))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("next", next_match))
    application.add_handler(CommandHandler("help", help_command))  # Menambahkan perintah /help

    # Menunggu (await) run_polling untuk memastikan coroutine dijalankan
    await application.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()  # Membantu menjalankan event loop dalam Jupyter / IDE lain yang sudah punya event loop
    asyncio.get_event_loop().run_until_complete(main())  # Gunakan get_event_loop() dan run_until_complete()
