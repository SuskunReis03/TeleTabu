import json
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Log ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Kelimeleri Yükle
def load_cards():
    with open("cards.json", "r", encoding="utf-8") as f:
        return json.load(f)

CARDS = load_cards()

# Oyun Durumu (Her sohbet için ayrı tutulur)
games = {}

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in games and games[chat_id].get("active"):
        await update.message.reply_text("⚠️ Zaten devam eden bir oyun var!")
        return

    games[chat_id] = {
        "active": True,
        "score": 0,
        "pas_rights": 3,
        "current_card": None,
        "describer_id": update.effective_user.id
    }

    await update.message.reply_text(
        f"🎮 **TeleTabu Oyunu Başladı!**\n\n"
        f"Anlatıcı: [{update.effective_user.first_name}](tg://user?id={update.effective_user.id})\n"
        f"Anlatıcıya kartı özel mesaj (DM) olarak gönderdik!",
        parse_mode="Markdown"
    )
    
    await send_next_card(chat_id, context)

async def send_next_card(chat_id, context):
    game = games[chat_id]
    card = random.choice(CARDS)
    game["current_card"] = card

    text = (
        f"🎯 HEDEF KELİME:\n\n"
        f"🚫 **Yasaklı Kelimeler:**\n" + 
        "\n".join([f"• {w}" for w in card['forbidden']]) +
        f"\n\n📊 Puan: {game['score']} | 🔄 Kalan Pas: {game['pas_rights']}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Doğru (+1)", callback_data=f"correct_{chat_id}"),
            InlineKeyboardButton("❌ Tabu (-1)", callback_data=f"taboo_{chat_id}"),
        ],
        [InlineKeyboardButton("🔄 Pas Geç", callback_data=f"pass_{chat_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=game["describer_id"], 
            text=text, 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id, 
            text="⚠️ Anlatıcıya özel mesaj gönderilemedi. Lütfen botu özelden başlatın (`/start`)!"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    action = data[0]
    chat_id = int(data[1])

    if chat_id not in games or not games[chat_id]["active"]:
        await query.edit_message_text("Bu oyun sona erdi.")
        return

    game = games[chat_id]

    if query.from_user.id != game["describer_id"]:
        await query.answer("⚠️ Butonları sadece kelimeyi anlatan kişi kullanabilir!", show_alert=True)
        return

    if action == "correct":
        game["score"] += 1
        await context.bot.send_message(chat_id, f"🎉 Doğru tahmin! Mevcut Puan: {game['score']}")
        await send_next_card(chat_id, context)
    elif action == "taboo":
        game["score"] -= 1
        await context.bot.send_message(chat_id, f"💥 TABU! 1 Puan düşüldü. Mevcut Puan: {game['score']}")
        await send_next_card(chat_id, context)
    elif action == "pass":
        if game["pas_rights"] > 0:
            game["pas_rights"] -= 1
            await context.bot.send_message(chat_id, f"🔄 Pas kullanıldı. Kalan Pas: {game['pas_rights']}")
            await send_next_card(chat_id, context)
        else:
            await query.answer("❌ Pas hakkınız kalmadı!", show_alert=True)

if __name__ == "__main__":
    # .env dosyasından token okunacak şekilde ayarlanabilir
    import os
    TOKEN = os.getenv("BOT_TOKEN", "BURAYA_BOT_TOKEN_GELECEK")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("oyun", start_game))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("TeleTabu Bot çalışıyor...")
    app.run_polling()
  
