import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os
import threading

# ==========================================
# 🔐 Environment Variables
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("⚠️ Error: BOT_TOKEN Environment Variable missing!")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8428347588"))
except:
    ADMIN_ID = 8428347588

# ==========================================
# 🧠 In-Memory Database (No File Writing - Render Free Friendly)
# ==========================================
db = {
    "users": {},
    "bot_settings": {
        "channel_link": "@MineRocket",
        "admin_channel": str(ADMIN_ID),
        "ref_bonus": 0.5,
        "req_refs": 3,
        "task_channel": ""
    }
}

user_steps = {}

def get_user(user_id):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 0.0,
            "refs": 0,
            "rewarded": False,
            "referrer": None,
            "mining_status": "stopped",
            "task_done": False
        }
    return db["users"][uid]

# ==========================================
# 🚀 /start Command
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    first = message.from_user.first_name
    user_data = get_user(user_id)

    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = args[1]
        if ref_id != user_id and user_data["referrer"] is None:
            user_data["referrer"] = ref_id

    channel = db["bot_settings"]["channel_link"]
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ JOIN OFFICIAL CHANNEL", url=f"https://t.me/{channel.replace('@', '')}"))
    keyboard.add(InlineKeyboardButton("✔️ I have Joined", callback_data="check_join"))

    bot.send_message(
        message.chat.id,
        f"🚀 *WELCOME TO MINE ROCKET* 🚀\n\n👋 Hello *{first}*!\n\n⚡ *Fast & Secure Mining Service*\n💰 *Earn & Withdraw USDT Easily*\n\n📢 Please join our official channel below to unlock the bot:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==========================================
# 👨‍💻 /admin Command
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("⚙️ Admin Settings"), KeyboardButton("➕ Add Task"))
        markup.add(KeyboardButton("🔙 Back to User Menu"))
        bot.send_message(message.chat.id, "👨‍💻 *Mine Rocket Admin Dashboard*", reply_markup=markup, parse_mode="Markdown")

# ==========================================
# ⏰ Mining Timer Function
# ==========================================
def give_mining_reward(user_id, chat_id):
    uid = str(user_id)
    if uid in db["users"] and db["users"][uid]["mining_status"] == "running":
        db["users"][uid]["balance"] += 0.10
        db["users"][uid]["mining_status"] = "stopped"
        try:
            bot.send_message(chat_id, "✅ *Mining Completed!*\n\nYou received *0.10 USDT*. Click ⛏ Mining to start again!", parse_mode="Markdown")
        except:
            pass

# ==========================================
# ⌨️ Buttons & Text Handler
# ==========================================
@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    text = message.text
    user_data = get_user(user_id)
    step = user_steps.get(user_id)

    if text == "💰 Balance":
        bal = user_data["balance"]
        bot.send_message(chat_id, f"💳 *ACCOUNT BALANCE*\n\n💵 Available: *{round(bal, 2)} USDT*", parse_mode="Markdown")
        
    elif text == "⛏ Mining":
        if user_data["mining_status"] == "running":
            bot.send_message(chat_id, "⏳ *Mining is already running!*", parse_mode="Markdown")
        else:
            db["users"][user_id]["mining_status"] = "running"
            bot.send_message(chat_id, "⚡ *Mining Started!*\n\nCompleted in 1 hour. We will notify you!", parse_mode="Markdown")
            threading.Timer(3600, give_mining_reward, args=[user_id, chat_id]).start()

    elif text == "👥 Referral":
        try:
            bot_username = bot.get_me().username
        except:
            bot_username = "Bot"
        ref_bonus = db["bot_settings"]["ref_bonus"]
        ref_count = user_data["refs"]
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        bot.send_message(chat_id, f"👑 *Affiliate Program*\n\n🎁 Bonus: *{ref_bonus} USDT*\n📊 Total Refs: *{ref_count}*\n\n🔗 *Link:*\n`{ref_link}`", parse_mode="Markdown")

    elif text == "📝 Tasks":
        task_channel = db["bot_settings"].get("task_channel", "")
        if not task_channel:
            bot.send_message(chat_id, "⏳ *No Tasks Available!*", parse_mode="Markdown")
        elif user_data.get("task_done", False):
            bot.send_message(chat_id, "✅ *Task already completed.*", parse_mode="Markdown")
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{task_channel.replace('@', '')}"))
            markup.add(InlineKeyboardButton("✔️ Check Task", callback_data="check_task"))
            bot.send_message(chat_id, "📝 *New Task Available!*", reply_markup=markup, parse_mode="Markdown")

    elif text == "📤 Withdraw":
        req_refs = db["bot_settings"]["req_refs"]
        my_refs = user_data["refs"]
        if my_refs < req_refs:
            bot.send_message(chat_id, f"❌ *Withdrawal Locked!* Need *{req_refs}* referrals. You have: *{my_refs}*", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "💵 *Enter Withdrawal Amount (USDT):*", parse_mode="Markdown")
            user_steps[user_id] = "wait_amount"

    elif text == "⚙️ Admin Settings" and message.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Set Main Channel", callback_data="set_channel"))
        markup.add(InlineKeyboardButton("🔔 Set Admin Channel", callback_data="set_admin_channel"))
        markup.add(InlineKeyboardButton("🎁 Set Ref Bonus", callback_data="set_bonus"))
        markup.add(InlineKeyboardButton("👥 Set Req Refs", callback_data="set_refs"))
        bot.send_message(chat_id, "⚙️ *Bot Configuration*", reply_markup=markup, parse_mode="Markdown")
        
    elif text == "➕ Add Task" and message.from_user.id == ADMIN_ID:
        bot.send_message(chat_id, "Send task channel link (e.g. @MyTaskChannel):")
        user_steps[user_id] = "add_task"

    elif text == "🔙 Back to User Menu":
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
        markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
        markup.add(KeyboardButton("📤 Withdraw"))
        bot.send_message(chat_id, "📱 *Switched to User Menu.*", reply_markup=markup, parse_mode="Markdown")

    # --- Input Steps ---
    elif step == "wait_amount":
        try:
            amount = float(text)
            if amount > user_data["balance"] or amount <= 0:
                bot.send_message(chat_id, "⚠️ *Invalid amount or insufficient balance.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            else:
                db["users"][user_id]["withdraw_amount"] = amount
                bot.send_message(chat_id, "🏦 *Enter your USDT (BEP20) Address:*", parse_mode="Markdown")
                user_steps[user_id] = "wait_address"
        except:
            bot.send_message(chat_id, "⚠️ *Enter a valid number.*", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    elif step == "wait_address":
        address = text
        amount = user_data.get("withdraw_amount", 0)
        db["users"][user_id]["balance"] -= amount
        user_steps.pop(user_id, None)
        
        admin_channel = db["bot_settings"]["admin_channel"]
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}_{amount}")
        )
        admin_msg = f"🔔 *NEW WITHDRAWAL*\n\n👤 User ID: `{user_id}`\n💰 Amount: *{amount} USDT*\n🏦 Address: `{address}`"
        
        try:
            bot.send_message(admin_channel, admin_msg, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="Markdown")
            
        bot.send_message(chat_id, "🚀 *Request Submitted Successfully!*", parse_mode="Markdown")

    elif message.from_user.id == ADMIN_ID:
        if step == "add_task":
            db["bot_settings"]["task_channel"] = text
            bot.send_message(chat_id, "✅ Task channel updated!")
            user_steps.pop(user_id, None)
        elif step == "set_channel":
            db["bot_settings"]["channel_link"] = text
            bot.send_message(chat_id, "✅ Main channel updated!")
            user_steps.pop(user_id, None)
        elif step == "set_admin_channel":
            db["bot_settings"]["admin_channel"] = text
            bot.send_message(chat_id, "✅ Admin channel updated!")
            user_steps.pop(user_id, None)
        elif step == "set_bonus":
            try:
                db["bot_settings"]["ref_bonus"] = float(text)
                bot.send_message(chat_id, "✅ Ref bonus updated!")
            except: pass
            user_steps.pop(user_id, None)
        elif step == "set_refs":
            try:
                db["bot_settings"]["req_refs"] = int(text)
                bot.send_message(chat_id, "✅ Required refs updated!")
            except: pass
            user_steps.pop(user_id, None)

# ==========================================
# 🖱️ Callback Handler
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    data = call.data

    if data == "check_join":
        channel = db["bot_settings"]["channel_link"]
        try:
            status = bot.get_chat_member(channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
                markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
                markup.add(KeyboardButton("📤 Withdraw"))
                bot.send_message(call.message.chat.id, "🎉 *Verification Successful!*\nWelcome to Mine Rocket.", reply_markup=markup, parse_mode="Markdown")
                
                referrer = db["users"][user_id].get("referrer")
                if referrer and not db["users"][user_id].get("rewarded"):
                    bonus = db["bot_settings"]["ref_bonus"]
                    if referrer in db["users"]:
                        db["users"][referrer]["balance"] += bonus
                        db["users"][referrer]["refs"] += 1
                    db["users"][user_id]["rewarded"] = True
                    try:
                        bot.send_message(referrer, f"🎁 *New Referral!* You received *{bonus} USDT*.", parse_mode="Markdown")
                    except: pass
            else:
                bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "⚠️ Error checking status. Is bot admin in channel?", show_alert=True)

    elif data == "check_task":
        task_channel = db["bot_settings"]["task_channel"]
        try:
            status = bot.get_chat_member(task_channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                db["users"][user_id]["task_done"] = True
                db["users"][user_id]["balance"] += 0.50
                bot.send_message(call.message.chat.id, "✅ *Task Completed!* Received *0.50 USDT*.", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ Join the task channel first!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "⚠️ Error checking task status.", show_alert=True)

    elif data.startswith("app_") and call.from_user.id == ADMIN_ID:
        _, target_user, amount = data.split("_")
        try: bot.send_message(target_user, f"✅ *Withdrawal Approved!*\nYour {amount} USDT has been sent.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"✅ *APPROVED*\nUser: `{target_user}`\nAmount: {amount} USDT", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data.startswith("rej_") and call.from_user.id == ADMIN_ID:
        _, target_user, amount = data.split("_")
        amount = float(amount)
        if target_user in db["users"]:
            db["users"][target_user]["balance"] += amount
        try: bot.send_message(target_user, f"❌ *Withdrawal Rejected!*\n{amount} USDT returned to balance.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"❌ *REJECTED*\nUser: `{target_user}`\nAmount: {amount} USDT", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif data in ["set_channel", "set_admin_channel", "set_bonus", "set_refs"] and call.from_user.id == ADMIN_ID:
        user_steps[user_id] = data
        prompts = {
            "set_channel": "📢 Send the new Main Channel link (e.g. @MineRocket):",
            "set_admin_channel": "🔔 Send Admin/Withdraw Channel link (e.g. @MyAdminChannel):",
            "set_bonus": "🎁 Send the new referral bonus amount (e.g. 0.5):",
            "set_refs": "👥 Send the required referrals for withdraw (e.g. 3):"
        }
        bot.send_message(call.message.chat.id, prompts[data])

print("🚀 Mine Rocket is live on Render Free tier!")
bot.infinity_polling()
