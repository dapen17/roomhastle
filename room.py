import asyncio
import os
import httpx
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, ConversationHandler
)
from telegram.ext import CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
# Load token dari file .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Token bot tidak ditemukan. Pastikan BOT_TOKEN ada di file .env.")

# ID grup admin
ADMIN_GROUP_ID = -1002543243481  # Ganti dengan ID grup admin kamu

# States untuk ConversationHandler
RP_START = range(1)

# Database sementara
users = {}     # Menyimpan data pengguna
rooms = {}     # Menyimpan pasangan yang sedang chatting
timers = {}    # Menyimpan timer untuk setiap room
conversations = {}  # Menyimpan percakapan antar pengguna

# ------------------- UTILITY -------------------

async def send_message_with_retry(bot, chat_id, text, retries=3, delay=2):
    """Mengirim pesan dengan mekanisme retry jika terjadi error httpx atau jaringan."""
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id, text)
            return  # Berhenti jika berhasil
        except httpx.RemoteProtocolError as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                raise e
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                raise e

# ------------------- COMMANDS -------------------

CHANNEL_ID = "@MenfessHastle"
CHANNEL_LINK = f"https://t.me/{CHANNEL_ID[1:]}"  # Tautan ke channel

async def start(update: Update, context: CallbackContext):
    """Memulai bot dan memberikan informasi perintah yang tersedia."""
    user_id = update.effective_user.id
    
    # Cek apakah pengguna sudah menjadi anggota channel
    try:
        chat_member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if chat_member.status in ['left', 'kicked']:  # Jika pengguna belum bergabung atau diblokir
            await update.message.reply_text(
                "Untuk mengakses fitur bot ini, Anda perlu bergabung dengan channel kami.\n"
                f"Silakan join ke sini untuk dapat mengakses fitur bot: {CHANNEL_LINK}",
                reply_markup=InlineKeyboardMarkup([[ 
                    InlineKeyboardButton("Join Channel", url=CHANNEL_LINK),
                    InlineKeyboardButton("Sudah Bergabung", callback_data="already_joined")  # Tombol untuk yang sudah bergabung
                ]])  # Tombol untuk bergabung dengan channel dan tombol untuk yang sudah bergabung
            )
            return  # Hentikan eksekusi perintah lebih lanjut jika belum bergabung
    except Exception as e:
        print(f"Error while checking membership: {e}")
        await update.message.reply_text(
            "Terjadi kesalahan saat memeriksa status channel. Mohon coba lagi nanti."
        )
        return

    # Jika pengguna sudah bergabung, lanjutkan ke perintah /start
    await update.message.reply_text(
        "Halo! Selamat datang di matchmaking bot.\n\n"
        "Ini adalah bot RP (roleplay) yang tidak dapat digunakan untuk tujuan serius atau real-life conversations.\n"
        "Berikut adalah perintah yang tersedia:\n"
        "/start - Mulai percakapan dan cari pasangan\n"
        "/new - Memulai ulang percakapan dan mencari pasangan baru\n"
        "/stop - Menghentikan percakapan saat ini\n"
        "/next - Mencari pasangan baru\n"
        "/help - Menampilkan perintah yang tersedia\n"
        "/report - Kirim percakapan ke admin\n\n"
        "NOTE: Tidak boleh mengirim gambar, stiker, atau voice note.",
        reply_markup=ReplyKeyboardMarkup([["Mulai RP"]], one_time_keyboard=True)
    )
    return RP_START

from telegram.ext import CallbackQueryHandler

async def button_handler(update: Update, context: CallbackContext):
    """Menangani klik pada tombol InlineKeyboard."""
    query = update.callback_query
    user_id = query.from_user.id

    # Jika pengguna menekan tombol "Sudah Bergabung"
    if query.data == "already_joined":
        await query.answer()  # Menutup interaksi tombol
        
        # Cek lagi apakah pengguna sudah bergabung atau belum
        try:
            chat_member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            if chat_member.status in ['left', 'kicked']:  # Jika pengguna masih belum bergabung
                await query.message.reply_text(
                    "Sepertinya Anda belum bergabung dengan channel. Silakan join dengan tombol di bawah ini.\n"
                    f"{CHANNEL_LINK}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)]])
                )
            else:
                # Jika sudah bergabung, kirimkan pemberitahuan
                if query.message:
                    await query.message.reply_text(
                        "Terima kasih telah bergabung! Sekarang anda dapat memulai bot."
                    )
                # Panggil fungsi /start untuk melanjutkan interaksi bot
                await start(update, context)
        except Exception as e:
            print(f"Error while checking membership after button press: {e}")
            if query.message:
                await query.message.reply_text(
                    "Memulai bot nya dengan cara klik atau ketik /start lagi."
                )


async def help_command(update: Update, context: CallbackContext):
    """Menampilkan bantuan perintah."""
    await update.message.reply_text(
        "Berikut adalah perintah yang tersedia:\n"
        "/start - Mulai percakapan dan cari pasangan\n"
        "/new - Mulai ulang percakapan dan cari pasangan baru\n"
        "/stop - Menghentikan percakapan saat ini\n"
        "/next - Cari pasangan baru\n"
        "/help - Menampilkan perintah yang tersedia\n"
        "/report - Kirim percakapan ke admin"
    )

async def new(update: Update, context: CallbackContext):
    """Memulai ulang percakapan dan menghapus data user."""
    user_id = update.effective_user.id
    if user_id in users:
        del users[user_id]

    await update.message.reply_text(
        "Silakan mulai RP baru. Pilih untuk memulai percakapan.",
        reply_markup=ReplyKeyboardMarkup([["Mulai RP"]], one_time_keyboard=True)
    )
    return RP_START

async def start_rp(update: Update, context: CallbackContext):
    """Mulai RP, tanpa batasan umur, hanya untuk roleplay."""
    user_id = update.effective_user.id

    users[user_id] = {
        "matched": False,
    }

    await update.message.reply_text("Data kamu telah disimpan. Kami akan mencarikan pasangan untukmu.")
    await match_user(update, context, user_id)
    return ConversationHandler.END

async def match_user(update: Update, context: CallbackContext, user_id):
    """Mencari pasangan tanpa kategori umur, hanya berdasarkan availability."""
    user_data = users[user_id]

    for other_id, other_data in users.items():
        if not other_data["matched"] and other_id != user_id:
            # Pasangkan user
            rooms[user_id] = other_id
            rooms[other_id] = user_id
            users[user_id]["matched"] = True
            users[other_id]["matched"] = True

            await send_message_with_retry(context.bot, user_id, "Anda telah dipasangkan! Mulai chat sekarang.")
            await send_message_with_retry(context.bot, other_id, "Anda telah dipasangkan! Mulai chat sekarang.")

            # Mulai timer
            timers[user_id] = asyncio.create_task(chat_timer(update, context, user_id, other_id))
            timers[other_id] = timers[user_id]
            return

    await send_message_with_retry(context.bot, user_id, "Belum ada pasangan yang cocok. Mohon tunggu.")

async def chat_timer(update: Update, context: CallbackContext, user_id, partner_id):
    """Timer percakapan 10 menit, dengan notifikasi 5 menit dan 1 menit terakhir."""
    await asyncio.sleep(300)
    await send_message_with_retry(context.bot, user_id, "Sisa waktu 5 menit lagi.")
    await send_message_with_retry(context.bot, partner_id, "Sisa waktu 5 menit lagi.")

    await asyncio.sleep(240)
    await send_message_with_retry(context.bot, user_id, "Sisa waktu 1 menit lagi.")
    await send_message_with_retry(context.bot, partner_id, "Sisa waktu 1 menit lagi.")

    await asyncio.sleep(60)
    await send_message_with_retry(context.bot, user_id, "Waktu percakapan telah selesai.")
    await send_message_with_retry(context.bot, partner_id, "Waktu percakapan telah selesai.")
    await stop_conversation(update, context, user_id, partner_id)

async def stop(update: Update, context: CallbackContext):
    """Perintah untuk menghentikan percakapan aktif."""
    user_id = update.effective_user.id
    if user_id in rooms:
        partner_id = rooms[user_id]
        await stop_conversation(update, context, user_id, partner_id)
    else:
        await update.message.reply_text("Anda belum memiliki pasangan yang bisa dihentikan.")

async def stop_conversation(update: Update, context: CallbackContext, user_id, partner_id):
    """Menghapus data pasangan dan menghentikan timer."""
    if user_id in rooms:
        del rooms[user_id]
    if partner_id in rooms:
        del rooms[partner_id]

    if user_id in timers:
        timers[user_id].cancel()
        del timers[user_id]
    if partner_id in timers:
        timers[partner_id].cancel()
        del timers[partner_id]

    await send_message_with_retry(context.bot, user_id, "Percakapan telah dihentikan.")
    await send_message_with_retry(context.bot, partner_id, "Percakapan telah dihentikan.")

async def next_match(update: Update, context: CallbackContext):
    """Mencari pasangan baru tanpa kategori umur atau batasan tertentu."""
    user_id = update.effective_user.id

    if user_id in users:
        if user_id in rooms:
            partner_id = rooms[user_id]
            await stop_conversation(update, context, user_id, partner_id)

        await match_user(update, context, user_id)
    else:
        await update.message.reply_text("Kamu belum memulai percakapan. Silakan gunakan /start terlebih dahulu.")

# ------------------- MESSAGE HANDLER -------------------

# Database percakapan
conversations = {}  # Menyimpan percakapan antara pasangan (user_id -> list_of_messages)

async def message_handler(update: Update, context: CallbackContext):
    """Meneruskan pesan antar pengguna yang dipasangkan dan menyimpan percakapan."""
    user_id = update.effective_user.id

    # Validasi jika pesan bukan text biasa (misalnya gambar, voice note, dsb)
    if not update.message.text:
        await update.message.reply_text("Pesan hanya boleh berupa teks biasa.")
        return

    if user_id in rooms:
        partner_id = rooms[user_id]
        partner_message = update.message.text

        # Menyimpan percakapan untuk setiap pasangan
        if user_id not in conversations:
            conversations[user_id] = []
        if partner_id not in conversations:
            conversations[partner_id] = []

        # Menambahkan pesan ke percakapan
        conversations[user_id].append(f"User: {partner_message}")
        conversations[partner_id].append(f"Partner: {partner_message}")

        # Meneruskan pesan ke pasangan
        await send_message_with_retry(context.bot, partner_id, partner_message)
    else:
        await update.message.reply_text(
            "Anda belum memiliki pasangan. Untuk mencari pasangan, silakan gunakan perintah /start terlebih dahulu."
        )

async def report(update: Update, context: CallbackContext):
    """Mengirimkan laporan percakapan ke grup admin."""
    user_id = update.effective_user.id

    # Pastikan pengguna memiliki pasangan yang sedang aktif
    if user_id not in rooms:
        await update.message.reply_text("Anda belum memiliki pasangan yang bisa dilaporkan.")
        return

    partner_id = rooms[user_id]
    
    # Ambil percakapan yang ada
    user_conversation = conversations.get(user_id, [])
    partner_conversation = conversations.get(partner_id, [])

    if not user_conversation or not partner_conversation:
        await update.message.reply_text("Tidak ada percakapan untuk dilaporkan.")
        return

    # Ambil username pengguna dan pasangan, jika ada
    user_username = update.effective_user.username
    if user_username:
        user_mention = f"<a href='tg://user?id={user_id}'>@{user_username}</a>"
    else:
        user_mention = f"<a href='tg://user?id={user_id}'>User tanpa username</a>"

    # Gunakan await untuk menunggu hasil get_chat
    partner_chat = await context.bot.get_chat(partner_id)
    partner_username = partner_chat.username
    if partner_username:
        partner_mention = f"<a href='tg://user?id={partner_id}'>@{partner_username}</a>"
    else:
        partner_mention = f"<a href='tg://user?id={partner_id}'>User tanpa username</a>"

    # Format laporan
    report_message = (
        f"***Laporan Percakapan***\n\n"
        f"Pelapor: {user_mention} (ID: {user_id})\n"
        f"Pelapor Username: {user_username if user_username else 'Tidak ada username'}\n"
        f"Tersangka: {partner_mention} (ID: {partner_id})\n"
        f"Tersangka Username: {partner_username if partner_username else 'Tidak ada username'}\n\n"
        "Percakapan:\n"
    )

    # Tambahkan percakapan ke laporan
    for message in user_conversation + partner_conversation:
        if message.startswith("User:"):
            report_message += f"• Pelapor: {message[6:]}\n"
        elif message.startswith("Partner:"):
            report_message += f"• Tersangka: {message[9:]}\n"

    # Kirim laporan ke grup admin dengan parse_mode=HTML
    await context.bot.send_message(ADMIN_GROUP_ID, report_message, parse_mode="HTML")
    await update.message.reply_text("Laporan percakapan telah dikirim ke admin.")

# ------------------- MAIN -------------------

async def main():
    """Main function untuk menjalankan bot."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation handler untuk proses awal pengambilan umur
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("new", new)
        ],
        states={
            RP_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_rp)],
        },
        fallbacks=[
            CommandHandler("stop", stop),
            CommandHandler("next", next_match),
        ],
    )

    # Tambahkan semua handler ke aplikasi
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("next", next_match))
    application.add_handler(CommandHandler("report", report))  # Menambahkan handler untuk /report
    # Menambahkan handler untuk tombol
    application.add_handler(CallbackQueryHandler(button_handler))


    # Handler untuk semua pesan teks biasa
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Jalankan bot
    print("Bot sedang berjalan...")
    await application.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()

    try:
        asyncio.get_event_loop().run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot dihentikan.")
