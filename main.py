import json
import random
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Log Ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Kelimeleri Yükle
def load_cards():
    try:
        with open("cards.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"cards.json yüklenirken hata oluştu: {e}")
        return []

CARDS = load_cards()

# Oyun Durumları
games = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start Komutu: Hoş geldin mesajı ve gruba ekleme butonu"""
    bot_username = context.bot.username
    add_to_group_url = f"https://t.me/{bot_username}?startgroup=true"
    
    welcome_text = (
        "👋 **TeleTabu Oyun Botuna Hoş Geldiniz!**\n\n"
        "Grubunuzda arkadaşlarınızla eğlenceli Tabu oyunları oynamak için beni bir gruba ekleyebilirsiniz.\n\n"
        "🎮 **Gruba Ekledikten Sonra:**\n"
        "Grubunuzda `/game` veya `/oyun` yazarak modu seçip oyunu başlatabilirsiniz!"
    )
    
    keyboard = [
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=add_to_group_url)],
        [InlineKeyboardButton("📖 Kurallar", callback_data="show_rules")]
    ]
    
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/game veya /oyun Komutu: Mod seçimi yaptırır"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    # Özel mesajda çalıştırılırsa gruba yönlendir
    if chat_type == "private":
        bot_username = context.bot.username
        add_url = f"https://t.me/{bot_username}?startgroup=true"
        keyboard = [[InlineKeyboardButton("➕ Gruba Ekle ve Oyna", url=add_url)]]
        await update.message.reply_text("⚠️ `/game` komutu sadece **gruplarda** kullanılabilir!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if chat_id in games and games[chat_id].get("active"):
        await update.message.reply_text("⚠️ Zaten devam eden bir oyun var! Bitirmek için `/bitir` yazabilirsiniz.")
        return

    text = (
        "🎯 **TeleTabu Oyun Modunu Seçin**\n\n"
        "Hangi modda oynamak istersiniz?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Normal Tabu", callback_data=f"selectmode_normal_{chat_id}"),
            InlineKeyboardButton("🎙️ Sesli Tabu", callback_data=f"selectmode_sesli_{chat_id}")
        ]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    action = data[0]
    user = query.from_user

    # Kurallar Butonu
    if action == "show_rules":
        await query.answer(
            "📖 Kurallar:\n"
            "1. Anlatıcı 'Kelimeye Bak' butonu ile kelimesini gizlice öğrenir.\n"
            "2. Doğru tahmin eden kişi sonraki turda yeni anlatıcı olur!\n"
            "3. Sesli tabuda sadece sesli mesaj/sesli sohbet ile anlatılabilir.",
            show_alert=True
        )
        return

    # Oyun Modu Seçildiğinde
    if action == "selectmode":
        mode = data[1]
        chat_id = int(data[2])

        if not CARDS:
            await query.answer("❌ Kelime veritabanı boş!", show_alert=True)
            return

        if chat_id in games and games[chat_id].get("active"):
            await query.answer("⚠️ Oyun zaten başladı!", show_alert=True)
            return

        card = random.choice(CARDS)
        games[chat_id] = {
            "active": True,
            "mode": mode,
            "score": 0,
            "pas_rights": 3,
            "current_card": card,
            "describer_id": user.id,
            "describer_name": user.first_name
        }

        mode_title = "🎙️ SESLİ TABU" if mode == "sesli" else "📝 NORMAL TABU"
        text = (
            f"🎮 **{mode_title} BAŞLADI!**\n\n"
            f"🗣️ **Sıradaki Anlatıcı:** [{user.first_name}](tg://user?id={user.id})\n"
            f"📊 **Puan:** 0 | 🔄 **Kalan Pas:** 3\n\n"
            f"👇 Anlatıcı aşağıdaki buton ile kelimesine bakıp oyunu başlatabilir!"
        )

        keyboard = create_game_keyboard(chat_id)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # Genel Oyun İçi İşlemler
    chat_id = int(data[1]) if len(data) > 1 else query.message.chat_id

    if chat_id not in games or not games[chat_id]["active"]:
        await query.answer("❌ Bu oyun aktif değil.", show_alert=True)
        return

    game = games[chat_id]

    # --- KELİMEYE BAK BUTONU ---
    if action == "showcard":
        if user.id != game["describer_id"]:
            await query.answer("⚠️ Kelimeyi anlatacak kişi sen değilsin!", show_alert=True)
            return

        card = game["current_card"]
        forbidden_list = "\n".join([f"• {w}" for w in card['forbidden']])
        mode_instruction = "\n\n🎙️ *Kelimeyi sesli mesaj veya sesli sohbet üzerinden anlatmalısın!*" if game["mode"] == "sesli" else ""

        secret_text = f"🎯 HEDEF KELİME: {card['word']}\n\n🚫 Yasaklı Kelimeler:\n{forbidden_list}{mode_instruction}"
        await query.answer(secret_text, show_alert=True)

    # --- DOĞRU BİLDİM BUTONU ---
    elif action == "correct":
        if user.id == game["describer_id"]:
            await query.answer("⚠️ Kendi kelimene 'Doğru Bildim' diyemezsin. Doğru tahmin eden oyuncunun basması gerekir!", show_alert=True)
            return

        game["score"] += 1
        game["describer_id"] = user.id
        game["describer_name"] = user.first_name
        game["current_card"] = random.choice(CARDS)

        await query.answer("🎉 Doğru bildiniz! Sıradaki anlatıcı sizsiniz.")
        mode_title = "🎙️ SESLİ TABU" if game["mode"] == "sesli" else "📝 NORMAL TABU"
        
        text = (
            f"🎉 **Tebrikler!** [{user.first_name}](tg://user?id={user.id}) doğru tahmin etti!\n\n"
            f"🎮 **{mode_title}**\n"
            f"🗣️ **Yeni Anlatıcı:** [{user.first_name}](tg://user?id={user.id})\n"
            f"📊 **Mevcut Puan:** {game['score']} | 🔄 **Kalan Pas:** {game['pas_rights']}\n\n"
            f"👇 Yeni anlatıcı buton ile kelimesine bakabilir!"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(create_game_keyboard(chat_id)), parse_mode="Markdown")

    # --- TABU BUTONU ---
    elif action == "taboo":
        game["score"] -= 1
        game["current_card"] = random.choice(CARDS)

        await query.answer("💥 TABU yapıldı! 1 puan düşüldü.")
        mode_title = "🎙️ SESLİ TABU" if game["mode"] == "sesli" else "📝 NORMAL TABU"

        text = (
            f"💥 **TABU YAPILDI!** (-1 Puan)\n\n"
            f"🎮 **{mode_title}**\n"
            f"🗣️ **Anlatıcı:** [{game['describer_name']}](tg://user?id={game['describer_id']})\n"
            f"📊 **Mevcut Puan:** {game['score']} | 🔄 **Kalan Pas:** {game['pas_rights']}"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(create_game_keyboard(chat_id)), parse_mode="Markdown")

    # --- PAS BUTONU ---
    elif action == "pass":
        if user.id != game["describer_id"]:
            await query.answer("⚠️ Kelimeyi sadece sıradaki anlatıcı değiştirebilir!", show_alert=True)
            return

        if game["pas_rights"] > 0:
            game["pas_rights"] -= 1
            game["current_card"] = random.choice(CARDS)
            await query.answer("🔄 Pas kullanıldı. Yeni kelimenize 'Kelimeye Bak' butonundan bakabilirsiniz.", show_alert=True)

            mode_title = "🎙️ SESLİ TABU" if game["mode"] == "sesli" else "📝 NORMAL TABU"
            text = (
                f"🔄 **Pas Kullanıldı!**\n\n"
                f"🎮 **{mode_title}**\n"
                f"🗣️ **Anlatıcı:** [{game['describer_name']}](tg://user?id={game['describer_id']})\n"
                f"📊 **Mevcut Puan:** {game['score']} | 🔄 **Kalan Pas:** {game['pas_rights']}"
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(create_game_keyboard(chat_id)), parse_mode="Markdown")
        else:
            await query.answer("❌ Pas hakkınız kalmadı!", show_alert=True)

    # --- OYUNU BİTİR BUTONU ---
    elif action == "stop":
        score = game["score"]
        games[chat_id]["active"] = False
        await query.edit_message_text(f"🏁 **Oyun Sona Erdi!**\n\n🏆 Toplam Kazanılan Puan: **{score}**", parse_mode="Markdown")

def create_game_keyboard(chat_id):
    """Oyun esnasındaki buton yapısını döndürür"""
    return [
        [InlineKeyboardButton("👁️ Kelimeye Bak", callback_data=f"showcard_{chat_id}")],
        [
            InlineKeyboardButton("✅ Doğru Bildim", callback_data=f"correct_{chat_id}"),
            InlineKeyboardButton("❌ Tabu (-1)", callback_data=f"taboo_{chat_id}")
        ],
        [InlineKeyboardButton("🔄 Kelimeyi Değiştir (Pas)", callback_data=f"pass_{chat_id}")],
        [InlineKeyboardButton("🛑 Oyunu Bitir", callback_data=f"stop_{chat_id}")]
    ]

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id].get("active"):
        score = games[chat_id]["score"]
        games[chat_id]["active"] = False
        await update.message.reply_text(f"🏁 **Oyun Sona Erdi!**\n\n🏆 Toplam Kazanılan Puan: **{score}**", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Aktif bir oyun bulunamadı.")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN", "BURAYA_TOKEN_GELECEK")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("oyun", game_command))
    app.add_handler(CommandHandler("bitir", stop_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("TeleTabu Bot başarıyla başlatıldı...")
    # drop_pending_updates=True eklenerek eski takılı kalan istekler temizlenir.
    app.run_polling(drop_pending_updates=True)
        
