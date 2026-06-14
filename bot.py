import telebot
import os
import json
import time
import random
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Render এর Environment Variables থেকে টোকেন এবং অ্যাডমিন আইডি নেওয়া হচ্ছে
# কোডের ভেতর কোনো টোকেন বা আইডি দেওয়া নেই
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_STR = os.getenv("ADMIN_ID")

if not TOKEN or not ADMIN_ID_STR:
    print("⚠️ Error: BOT_TOKEN or ADMIN_ID is missing in Environment Variables!")
    exit()

ADMIN_ID = int(ADMIN_ID_STR)
bot = telebot.TeleBot(TOKEN)

# ডাটাবেস সেটআপ (JSON ফাইল)
DATA_FILE = "database.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {}, 
        "settings": {
            "channel_link": "@YourChannel",
            "ref_bonus": 0.5,
            "req_refs": 3,
            "withdraw_status": "ON",
            "withdraw_off_msg": "⚠️ Withdrawals are currently disabled by the administrator."
        }
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

db = load_data()

# --- কীবোর্ড মেনু ---
def user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"),
        KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"),
        KeyboardButton("📤 Withdraw")
    )
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("⚙️ General Settings"), KeyboardButton("📤 Withdraw Settings"),
        KeyboardButton("📣 Broadcast"), KeyboardButton("🔙 User Menu")
    )
    return markup

# --- ইউজার কমান্ডসমূহ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    
    if user_id not in db["users"]:
        db["users"][user_id] = {"balance": 0.0, "refs": 0, "last_mining": 0, "referrer": None, "rewarded": False}
        
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = args[1]
            if ref_id != user_id and ref_id in db["users"]:
                db["users"][user_id]["referrer"] = ref_id
        save_data(db)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ I have joined", callback_data="check_join"))
    bot.send_message(message.chat.id, f"👋 *Welcome!*\n\nPlease join our official channel first:\n📢 {db['settings']['channel_link']}", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_channel_join(call):
    user_id = str(call.from_user.id)
    channel = db['settings']["channel_link"]
    
    try:
        status = bot.get_chat_member(channel, call.from_user.id).status
        if status in ['member', 'administrator', 'creator']:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ *Verification Successful!*\n\nWelcome to the dashboard.", reply_markup=user_menu(), parse_mode="Markdown")
            
            # রেফার বোনাস
            user_data = db["users"][user_id]
            ref_id = user_data["referrer"]
            if ref_id and not user_data["rewarded"]:
                db["users"][ref_id]["balance"] += db['settings']["ref_bonus"]
                db["users"][ref_id]["refs"] += 1
                db["users"][user_id]["rewarded"] = True
                save_data(db)
                bot.send_message(int(ref_id), f"🎉 *New Referral!* You received {db['settings']['ref_bonus']} USDT.", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet!", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ Error checking status. Is the bot an admin in the channel?", show_alert=True)

@bot.message_handler(func=lambda message: message.text == "💰 Balance")
def check_balance(message):
    user_id = str(message.from_user.id)
    balance = db["users"].get(user_id, {}).get("balance", 0.0)
    bot.send_message(message.chat.id, f"💳 *Account Balance:*\n\nAvailable: *{balance:.2f} USDT*", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "⛏ Mining")
def mining(message):
    user_id = str(message.from_user.id)
    now = time.time()
    last_mining = db["users"][user_id]["last_mining"]
    cooldown = 3600 
    
    if now - last_mining < cooldown:
        wait_time = int((cooldown - (now - last_mining)) / 60)
        bot.send_message(message.chat.id, f"⏳ *Mining Cooldown*\nPlease wait {wait_time} minutes.", parse_mode="Markdown")
        return
        
    reward = round(random.uniform(0.01, 0.15), 2)
    db["users"][user_id]["balance"] += reward
    db["users"][user_id]["last_mining"] = now
    save_data(db)
    
    bot.send_message(message.chat.id, f"⛏ *Mining Completed!*\nYou have successfully mined *{reward} USDT*.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "👥 Referral")
def referral(message):
    user_id = str(message.from_user.id)
    ref_count = db["users"][user_id]["refs"]
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    msg = f"👥 *Affiliate Program*\nEarn *{db['settings']['ref_bonus']} USDT* per referral.\n\n📊 *Your Referrals:* {ref_count}\n🔗 *Link:* `{ref_link}`"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📤 Withdraw")
def withdraw(message):
    user_id = str(message.from_user.id)
    
    if db['settings']["withdraw_status"] == "OFF":
        bot.send_message(message.chat.id, db['settings']["withdraw_off_msg"], parse_mode="Markdown")
        return
        
    if db["users"][user_id]["refs"] < db['settings']["req_refs"]:
        bot.send_message(message.chat.id, f"❌ You need at least *{db['settings']['req_refs']}* referrals to withdraw.", parse_mode="Markdown")
        return
        
    msg = bot.send_message(message.chat.id, "💵 Enter the amount of *USDT* you wish to withdraw:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_withdraw_amount)

def process_withdraw_amount(message):
    user_id = str(message.from_user.id)
    try:
        amount = float(message.text)
        if amount > db["users"][user_id]["balance"] or amount <= 0:
            bot.send_message(message.chat.id, "⚠️ Invalid amount or insufficient balance.")
            return
            
        db["users"][user_id]["withdraw_amount"] = amount
        save_data(db)
        
        msg = bot.send_message(message.chat.id, "🏦 Enter your *USDT (TRC20) Wallet Address*:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_withdraw_address)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Please enter a valid number.")

def process_withdraw_address(message):
    user_id = str(message.from_user.id)
    address = message.text
    amount = db["users"][user_id]["withdraw_amount"]
    
    db["users"][user_id]["balance"] -= amount
    save_data(db)
    
    admin_msg = f"🔔 *New Withdrawal Request*\n\n👤 User ID: `{user_id}`\n💰 Amount: *{amount} USDT*\n🏦 Address: `{address}`"
    bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    bot.send_message(message.chat.id, f"✅ *Request Submitted!*\nYour request for {amount} USDT is sent to admin.", parse_mode="Markdown")

# --- অ্যাডমিন প্যানেল কমান্ডসমূহ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(ADMIN_ID, "👨‍💻 *Admin Dashboard*", reply_markup=admin_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🔙 User Menu" and message.from_user.id == ADMIN_ID)
def back_to_user(message):
    bot.send_message(ADMIN_ID, "📱 *Switched to User Menu.*", reply_markup=user_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📣 Broadcast" and message.from_user.id == ADMIN_ID)
def broadcast_step(message):
    msg = bot.send_message(ADMIN_ID, "📝 Send the message you want to broadcast:")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    count = 0
    for uid in db["users"].keys():
        try:
            bot.send_message(int(uid), message.text)
            count += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ Broadcast sent to {count} users.")

@bot.message_handler(func=lambda message: message.text == "📤 Withdraw Settings" and message.from_user.id == ADMIN_ID)
def wd_settings(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🟢 Turn ON", callback_data="wd_on"), InlineKeyboardButton("🔴 Turn OFF", callback_data="wd_off"))
    bot.send_message(ADMIN_ID, f"⚙️ Withdraw Status: *{db['settings']['withdraw_status']}*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["wd_on", "wd_off"])
def change_wd_status(call):
    if call.from_user.id != ADMIN_ID:
        return
    db['settings']["withdraw_status"] = "ON" if call.data == "wd_on" else "OFF"
    save_data(db)
    bot.edit_message_text(f"✅ Withdrawals are now **{db['settings']['withdraw_status']}**.", chat_id=ADMIN_ID, message_id=call.message.message_id, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
