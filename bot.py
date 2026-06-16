import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import json
import os
import threading

# ==========================================
# 🔐 Environment Variables (Render থেকে অটোমেটিক নিবে)
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("⚠️ Error: BOT_TOKEN is missing. Please set it in Render Environment Variables.")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

# অ্যাডমিন আইডি Render থেকে নিবে
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8428347588"))
except ValueError:
    ADMIN_ID = 8428347588

# ==========================================
# 💾 ডাটাবেস সিস্টেম (JSON)
# ==========================================

DB_FILE = "database.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "bot_settings": {
                "channel_link": "@MineRocket",
                "admin_channel": str(ADMIN_ID),
                "ref_bonus": 0.5,
                "req_refs": 3,
                "task_channel": "",
                "task_reward": 0.50  # ডিফল্ট টাস্ক রিওয়ার্ড
            }
        }
    with open(DB_FILE, "r") as f:
        data = json.load(f)
    # পুরনো DB তে task_reward না থাকলে যোগ করো
    if "task_reward" not in data["bot_settings"]:
        data["bot_settings"]["task_reward"] = 0.50
        save_db(data)
    return data

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

db = load_db()
user_steps = {}  # ইউজারের বর্তমান ইনপুট স্টেপ

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
        save_db(db)
    return db["users"][uid]

# ==========================================
# 🚀 /start কমান্ড
# ==========================================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    first = message.from_user.first_name
    user_data = get_user(user_id)

    # রেফারেল ট্র্যাকিং
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = args[1]
        if ref_id != user_id and user_data["referrer"] is None:
            user_data["referrer"] = ref_id
            save_db(db)

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
# 👨‍💻 /admin কমান্ড
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("⚙️ Admin Settings"), KeyboardButton("➕ Add Task"))
        markup.add(KeyboardButton("🔙 Back to User Menu"))
        bot.send_message(
            message.chat.id,
            "👨‍💻 *Mine Rocket Admin Dashboard*\n\nWelcome to the control panel.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==========================================
# ⏰ অটোমেটিক মাইনিং রিওয়ার্ড ফাংশন
# ==========================================

def give_mining_reward(user_id, chat_id):
    db = load_db()
    uid = str(user_id)
    if uid in db["users"] and db["users"][uid]["mining_status"] == "running":
        db["users"][uid]["balance"] += 0.10
        db["users"][uid]["mining_status"] = "stopped"
        save_db(db)
        try:
            bot.send_message(
                chat_id,
                "✅ *Mining Completed!*\n\nYou received *0.10 USDT*. Click ⛏ Mining to start again!",
                parse_mode="Markdown"
            )
        except:
            pass

# ==========================================
# ⌨️ টেক্সট ও মেনু বাটন হ্যান্ডলার
# ==========================================

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    text = message.text
    user_data = get_user(user_id)
    step = user_steps.get(user_id)

    # ────────────────────────────────
    # USER MENU
    # ────────────────────────────────

    if text == "💰 Balance":
        bal = user_data["balance"]
        bot.send_message(
            chat_id,
            f"💳 *ACCOUNT BALANCE*\n\n💵 Available: *{round(bal, 2)} USDT*",
            parse_mode="Markdown"
        )

    elif text == "⛏ Mining":
        if user_data["mining_status"] == "running":
            bot.send_message(chat_id, "⏳ *Mining is already running!*\nPlease wait for it to finish.", parse_mode="Markdown")
        else:
            db["users"][user_id]["mining_status"] = "running"
            save_db(db)
            bot.send_message(
                chat_id,
                "⚡ *Mining Started!*\n\nYour mining will be completed in 1 hour. We will notify you automatically!",
                parse_mode="Markdown"
            )
            threading.Timer(3600, give_mining_reward, args=[user_id, chat_id]).start()

    elif text == "👥 Referral":
        bot_username = bot.get_me().username
        ref_bonus = db["bot_settings"]["ref_bonus"]
        ref_count = user_data["refs"]
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        bot.send_message(
            chat_id,
            f"👑 *Affiliate Program*\n\n🎁 Bonus Per Referral: *{ref_bonus} USDT*\n📊 Total Referrals: *{ref_count}*\n\n🔗 *Your Invitation Link:*\n`{ref_link}`",
            parse_mode="Markdown"
        )

    elif text == "📝 Tasks":
        task_channel = db["bot_settings"].get("task_channel", "")
        task_reward = db["bot_settings"].get("task_reward", 0.50)
        if not task_channel:
            bot.send_message(chat_id, "⏳ *No Tasks Available Right Now!*", parse_mode="Markdown")
        elif user_data.get("task_done", False):
            bot.send_message(chat_id, "✅ *You have already completed the available task.*", parse_mode="Markdown")
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{task_channel.replace('@', '')}"))
            markup.add(InlineKeyboardButton("✔️ Check Task", callback_data="check_task"))
            bot.send_message(
                chat_id,
                f"📝 *New Task Available!*\n\n🎁 Reward: *{task_reward} USDT*\n\nJoin the channel below to earn your reward.",
                reply_markup=markup,
                parse_mode="Markdown"
            )

    elif text == "📤 Withdraw":
        req_refs = db["bot_settings"]["req_refs"]
        my_refs = user_data["refs"]
        if my_refs < req_refs:
            bot.send_message(
                chat_id,
                f"❌ *Withdrawal Locked!*\n\nYou need at least *{req_refs}* referrals.\nYour current referrals: *{my_refs}*",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(chat_id, "💵 *Enter Withdrawal Amount (USDT):*\n\nType the amount below:", parse_mode="Markdown")
            user_steps[user_id] = "wait_amount"

    # ────────────────────────────────
    # ADMIN MENU
    # ────────────────────────────────

    elif text == "⚙️ Admin Settings" and message.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Set Main Channel", callback_data="set_channel"))
        markup.add(InlineKeyboardButton("🔔 Set Admin Channel", callback_data="set_admin_channel"))
        markup.add(InlineKeyboardButton("🎁 Set Ref Bonus", callback_data="set_bonus"))
        markup.add(InlineKeyboardButton("👥 Set Req Refs", callback_data="set_refs"))
        bot.send_message(chat_id, "⚙️ *Bot Configuration*", reply_markup=markup, parse_mode="Markdown")

    elif text == "➕ Add Task" and message.from_user.id == ADMIN_ID:
        bot.send_message(
            chat_id,
            "📢 *Step 1/2 — Task Setup*\n\nSend the task channel link:\n_(e.g. @MyTaskChannel)_",
            parse_mode="Markdown"
        )
        user_steps[user_id] = "add_task_channel"

    elif text == "🔙 Back to User Menu":
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
        markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
        markup.add(KeyboardButton("📤 Withdraw"))
        bot.send_message(chat_id, "📱 *Switched to User Menu.*", reply_markup=markup, parse_mode="Markdown")

    # ────────────────────────────────
    # STEP INPUTS — USER
    # ────────────────────────────────

    elif step == "wait_amount":
        try:
            amount = float(text)
            if amount <= 0 or amount > user_data["balance"]:
                bot.send_message(chat_id, "⚠️ *Invalid amount or insufficient balance.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            else:
                db["users"][user_id]["withdraw_amount"] = amount
                save_db(db)
                bot.send_message(chat_id, "🏦 *Enter your USDT (BEP20) Wallet Address:*", parse_mode="Markdown")
                user_steps[user_id] = "wait_address"
        except ValueError:
            bot.send_message(chat_id, "⚠️ *Please enter a valid number.*", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    elif step == "wait_address":
        address = text
        amount = user_data.get("withdraw_amount", 0)
        db["users"][user_id]["balance"] -= amount
        save_db(db)
        user_steps.pop(user_id, None)

        admin_channel = db["bot_settings"]["admin_channel"]
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}_{amount}")
        )
        admin_msg = (
            f"🔔 *NEW WITHDRAWAL REQUEST*\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"💰 Amount: *{amount} USDT*\n"
            f"🏦 Address: `{address}`"
        )

        try:
            bot.send_message(admin_channel, admin_msg, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(ADMIN_ID, admin_msg, reply_markup=markup, parse_mode="Markdown")

        bot.send_message(chat_id, "🚀 *Withdrawal Request Submitted Successfully!*\n\nPlease wait for admin approval.", parse_mode="Markdown")

    # ────────────────────────────────
    # STEP INPUTS — ADMIN (Task Setup)
    # ────────────────────────────────

    elif step == "add_task_channel" and message.from_user.id == ADMIN_ID:
        # Step 1: চ্যানেল লিংক সেভ করো, reward চাও
        db["bot_settings"]["task_channel"] = text
        db["bot_settings"]["task_done_users"] = []  # নতুন টাস্কে সবার task_done রিসেট
        # সব ইউজারের task_done False করো নতুন টাস্কের জন্য
        for uid in db["users"]:
            db["users"][uid]["task_done"] = False
        save_db(db)
        user_steps[user_id] = "add_task_reward"
        bot.send_message(
            chat_id,
            "🎁 *Step 2/2 — Set Reward*\n\nSend the reward amount for this task:\n_(e.g. 0.50)_",
            parse_mode="Markdown"
        )

    elif step == "add_task_reward" and message.from_user.id == ADMIN_ID:
        # Step 2: reward সেট করো
        try:
            reward = float(text)
            if reward <= 0:
                raise ValueError
            db["bot_settings"]["task_reward"] = reward
            save_db(db)
            task_channel = db["bot_settings"]["task_channel"]
            bot.send_message(
                chat_id,
                f"✅ *Task Added Successfully!*\n\n📢 Channel: `{task_channel}`\n🎁 Reward: *{reward} USDT*\n\n⚠️ Make sure the bot is *admin* in `{task_channel}` to verify members.",
                parse_mode="Markdown"
            )
        except ValueError:
            bot.send_message(chat_id, "⚠️ Invalid amount. Please send a valid number (e.g. 0.50).", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    # ────────────────────────────────
    # STEP INPUTS — ADMIN (Settings)
    # ────────────────────────────────

    elif step == "set_channel" and message.from_user.id == ADMIN_ID:
        db["bot_settings"]["channel_link"] = text
        save_db(db)
        bot.send_message(chat_id, "✅ Main channel updated!")
        user_steps.pop(user_id, None)

    elif step == "set_admin_channel" and message.from_user.id == ADMIN_ID:
        db["bot_settings"]["admin_channel"] = text
        save_db(db)
        bot.send_message(chat_id, "✅ Admin channel updated!")
        user_steps.pop(user_id, None)

    elif step == "set_bonus" and message.from_user.id == ADMIN_ID:
        try:
            db["bot_settings"]["ref_bonus"] = float(text)
            save_db(db)
            bot.send_message(chat_id, "✅ Ref bonus updated!")
        except ValueError:
            bot.send_message(chat_id, "⚠️ Invalid amount.")
        user_steps.pop(user_id, None)

    elif step == "set_refs" and message.from_user.id == ADMIN_ID:
        try:
            db["bot_settings"]["req_refs"] = int(text)
            save_db(db)
            bot.send_message(chat_id, "✅ Required refs updated!")
        except ValueError:
            bot.send_message(chat_id, "⚠️ Invalid number.")
        user_steps.pop(user_id, None)

# ==========================================
# 🖱️ ইনলাইন কলব্যাক হ্যান্ডলার
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    data = call.data

    # ── চ্যানেল জয়েন চেক ──
    if data == "check_join":
        channel = db["bot_settings"]["channel_link"]
        try:
            status = bot.get_chat_member(channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
                markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
                markup.add(KeyboardButton("📤 Withdraw"))
                bot.send_message(
                    call.message.chat.id,
                    "🎉 *Verification Successful!*\n\nWelcome to Mine Rocket! 🚀",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )

                # রেফারেল বোনাস দেওয়া
                referrer = db["users"][user_id].get("referrer")
                if referrer and referrer in db["users"] and not db["users"][user_id].get("rewarded"):
                    bonus = db["bot_settings"]["ref_bonus"]
                    db["users"][referrer]["balance"] += bonus
                    db["users"][referrer]["refs"] += 1
                    db["users"][user_id]["rewarded"] = True
                    save_db(db)
                    try:
                        bot.send_message(
                            referrer,
                            f"🎁 *New Referral Bonus!*\n\nYou received *{bonus} USDT*.",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
            else:
                bot.answer_callback_query(call.id, "❌ You haven't joined the channel yet!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, "⚠️ Error! Make sure the bot is admin in the channel.", show_alert=True)

    # ── টাস্ক চেক ──
    elif data == "check_task":
        task_channel = db["bot_settings"].get("task_channel", "")
        task_reward = db["bot_settings"].get("task_reward", 0.50)

        if not task_channel:
            bot.answer_callback_query(call.id, "⚠️ No task channel set.", show_alert=True)
            return

        if db["users"].get(user_id, {}).get("task_done", False):
            bot.answer_callback_query(call.id, "✅ You already completed this task!", show_alert=True)
            return

        try:
            status = bot.get_chat_member(task_channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                db["users"][user_id]["task_done"] = True
                db["users"][user_id]["balance"] += task_reward
                save_db(db)
                bot.send_message(
                    call.message.chat.id,
                    f"✅ *Task Completed!*\n\nYou received *{task_reward} USDT* 🎉",
                    parse_mode="Markdown"
                )
            else:
                bot.answer_callback_query(call.id, "❌ You haven't joined the task channel yet!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, "⚠️ Error! Make sure the bot is admin in the task channel.", show_alert=True)

    # ── Withdrawal Approve ──
    elif data.startswith("app_") and call.from_user.id == ADMIN_ID:
        parts = data.split("_")
        target_user = parts[1]
        amount = parts[2]
        try:
            bot.send_message(
                target_user,
                f"✅ *Withdrawal Approved!*\n\n💰 *{amount} USDT* has been sent to your wallet.",
                parse_mode="Markdown"
            )
        except:
            pass
        bot.edit_message_text(
            f"✅ *APPROVED*\n\nUser: `{target_user}`\nAmount: {amount} USDT",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )

    # ── Withdrawal Reject ──
    elif data.startswith("rej_") and call.from_user.id == ADMIN_ID:
        parts = data.split("_")
        target_user = parts[1]
        amount = float(parts[2])
        db["users"][target_user]["balance"] += amount
        save_db(db)
        try:
            bot.send_message(
                target_user,
                f"❌ *Withdrawal Rejected!*\n\n*{amount} USDT* has been returned to your balance.",
                parse_mode="Markdown"
            )
        except:
            pass
        bot.edit_message_text(
            f"❌ *REJECTED*\n\nUser: `{target_user}`\nAmount: {amount} USDT",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )

    # ── Admin Settings Callbacks ──
    elif data in ["set_channel", "set_admin_channel", "set_bonus", "set_refs"] and call.from_user.id == ADMIN_ID:
        user_steps[user_id] = data
        prompts = {
            "set_channel":       "📢 Send the new Main Channel link:\n_(e.g. @MineRocket)_",
            "set_admin_channel": "🔔 Send Admin/Withdraw Channel link:\n_(e.g. @MyAdminChannel)_",
            "set_bonus":         "🎁 Send the new referral bonus amount:\n_(e.g. 0.5)_",
            "set_refs":          "👥 Send the required referral count for withdrawal:\n_(e.g. 3)_"
        }
        bot.send_message(call.message.chat.id, prompts[data], parse_mode="Markdown")

# ==========================================
# 🚀 Bot Start
# ==========================================

print("🚀 Mine Rocket Bot is running...")
bot.infinity_polling()
