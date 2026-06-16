import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import json
import os
import threading
import time
import datetime
from flask import Flask

# ==========================================
#   Environment Variables
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("   Error: BOT_TOKEN is missing.")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8428347588"))
except ValueError:
    ADMIN_ID = 8428347588

# ==========================================
#   Database and Settings
# ==========================================

DB_FILE = "database.json"

DEFAULT_SETTINGS = {
    "channel_link": "@MineRocket",
    "admin_channel": str(ADMIN_ID),
    "ref_bonus": 0.5,
    "req_refs": 3,
    "min_withdraw": 5.0,
    "mining_reward": 0.10,
    "mining_hours": 1,
    "ref_mining_percent": 10,
}

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "tasks": {}, "bot_settings": DEFAULT_SETTINGS.copy()}
    with open(DB_FILE, "r") as f:
        data = json.load(f)
    for key, val in DEFAULT_SETTINGS.items():
        if key not in data["bot_settings"]:
            data["bot_settings"][key] = val
    if "tasks" not in data:
        data["tasks"] = {}
    save_db(data)
    return data

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

db = load_db()
user_steps = {}       
mining_timers = {}    

def get_user(user_id):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 0.0,
            "refs": 0,
            "rewarded": False,
            "referrer": None,
            "mining_status": "stopped",
            "mining_start": None,
            "completed_tasks": []
        }
        save_db(db)
    user = db["users"][uid]
    if "mining_start" not in user:
        user["mining_start"] = None
    if "completed_tasks" not in user:
        user["completed_tasks"] = []
    return user

def next_task_id():
    if not db["tasks"]:
        return "1"
    return str(max(int(k) for k in db["tasks"].keys()) + 1)

# ==========================================
#   Mining Reward System
# ==========================================

def give_mining_reward(user_id, chat_id):
    db2 = load_db()
    uid = str(user_id)
    if uid in db2["users"] and db2["users"][uid]["mining_status"] == "running":
        reward = db2["bot_settings"]["mining_reward"]
        db2["users"][uid]["balance"] += reward
        db2["users"][uid]["mining_status"] = "stopped"
        db2["users"][uid]["mining_start"] = None
        
        referrer = db2["users"][uid].get("referrer")
        if referrer and str(referrer) in db2["users"]:
            pct = db2["bot_settings"].get("ref_mining_percent", 10)
            commission = round((pct / 100.0) * reward, 4)
            db2["users"][str(referrer)]["balance"] += commission
            try:
                bot.send_message(
                    referrer,
                    f"🎁 Referral Mining Bonus!\n"
                    f"👤 Your referral completed mining.\n"
                    f"💰 Mining Reward: {reward} USDT\n"
                    f"📈 Commission: {commission} USDT\n"
                    f"Balance has been updated.",
                    parse_mode="Markdown"
                )
            except:
                pass
        
        save_db(db2)
        db.update(db2)
        mining_timers.pop(uid, None)
        try:
            bot.send_message(
                chat_id,
                f"⛏ *Mining Completed!*\n\n"
                f"You received *{reward} USDT*\n"
                f"Click *Mining* button to start again!",
                parse_mode="Markdown"
            )
        except:
            pass

def format_countdown(seconds_left):
    if seconds_left <= 0:
        return "0m 0s"
    h = int(seconds_left // 3600)
    m = int((seconds_left % 3600) // 60)
    s = int(seconds_left % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

# ==========================================
#   /start Command
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
            db["users"][user_id]["referrer"] = ref_id
            save_db(db)

    channel = db["bot_settings"]["channel_link"]
    keyboard = InlineKeyboardMarkup()
    # Restored Emojis: ✅ JOIN OFFICIAL CHANNEL, ✔️ I have Joined[cite: 1]
    keyboard.add(InlineKeyboardButton("✅ JOIN OFFICIAL CHANNEL", url=f"https://t.me/{channel.replace('@', '')}"))
    keyboard.add(InlineKeyboardButton("✔️ I have Joined", callback_data="check_join"))

    bot.send_message(
        message.chat.id,
        f"🚀 *WELCOME TO MINE ROCKET* \n\n"
        f"Hello *{first}*!\n\n"
        f"*Fast & Secure Mining Service*\n"
        f"*Earn & Withdraw USDT Easily*\n\n"
        f"Please join our official channel below to unlock the bot:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==========================================
#   /admin Command
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    # Restored Emojis: ⚙️ Admin Settings, ➕ Add Task, 📋 All Tasks, 🔙 Back to User Menu[cite: 1]
    markup.add(KeyboardButton("⚙️ Admin Settings"), KeyboardButton("➕ Add Task"))
    markup.add(KeyboardButton("📋 All Tasks"), KeyboardButton("🔙 Back to User Menu"))
    bot.send_message(
        message.chat.id,
        "🛠 *Mine Rocket Admin Dashboard*\n\nWelcome to the control panel.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==========================================
#   Main Text Handler
# ==========================================

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    text = message.text
    user_data = get_user(user_id)
    step = user_steps.get(user_id)

    # USER MENU HANDLERS (Restored button matching)[cite: 1]
    if text == "💰 Balance":
        bal = user_data["balance"]
        min_wd = db["bot_settings"]["min_withdraw"]
        bot.send_message(
            chat_id,
            f"💰 *ACCOUNT BALANCE*\n\n"
            f"Available: *{round(bal, 2)} USDT*\n"
            f"Min Withdraw: *{min_wd} USDT*",
            parse_mode="Markdown"
        )

    elif text == "⛏ Mining":
        s = db["bot_settings"]
        reward    = s["mining_reward"]
        hours     = s["mining_hours"]
        total_sec = hours * 3600

        if user_data["mining_status"] == "running":
            start_time = user_data.get("mining_start") or time.time()
            elapsed    = time.time() - start_time
            remaining  = max(0, total_sec - elapsed)
            countdown  = format_countdown(remaining)
            bot.send_message(
                chat_id,
                f"⛏ *Mining in Progress...*\n\n"
                f"Time Remaining: *{countdown}*\n"
                f"Reward: *{reward} USDT*\n\n"
                f"_We'll notify you when it's done!_",
                parse_mode="Markdown"
            )
        else:
            db["users"][user_id]["mining_status"] = "running"
            db["users"][user_id]["mining_start"]  = time.time()
            save_db(db)

            if user_id in mining_timers:
                mining_timers[user_id].cancel()

            t = threading.Timer(total_sec, give_mining_reward, args=[user_id, chat_id])
            t.daemon = True
            t.start()
            mining_timers[user_id] = t

            bot.send_message(
                chat_id,
                f"⛏ *Mining Started!*\n\n"
                f"Duration: *{hours} hour(s)*\n"
                f"Reward: *{reward} USDT*\n\n"
                f"Time Remaining: *{format_countdown(total_sec)}*\n\n"
                f"_We will notify you automatically when mining is complete!_",
                parse_mode="Markdown"
            )

    elif text == "👥 Referral":
        bot_username = bot.get_me().username
        ref_bonus  = db["bot_settings"]["ref_bonus"]
        ref_count  = user_data["refs"]
        ref_link   = f"https://t.me/{bot_username}?start={user_id}"
        bot.send_message(
            chat_id,
            f"👥 *Affiliate Program*\n\n"
            f"Bonus Per Referral: *{ref_bonus} USDT*\n"
            f"Total Referrals: *{ref_count}*\n\n"
            f"*Your Invitation Link:*\n`{ref_link}`",
            parse_mode="Markdown"
        )

    elif text == "📝 Tasks":
        tasks = db.get("tasks", {})
        active_tasks = {tid: t for tid, t in tasks.items() if t.get("active", True)}
        if not active_tasks:
            bot.send_message(chat_id, "❌ *No Tasks Available Right Now!*", parse_mode="Markdown")
            return

        completed = user_data.get("completed_tasks", [])
        sent_any  = False
        for tid, task in active_tasks.items():
            channel = task["channel"]
            reward  = task["reward"]
            title   = task.get("title", f"Task #{tid}")
            done    = tid in completed

            markup = InlineKeyboardMarkup()
            if not done:
                # Restored Emojis: ✅ Join Channel, ✔️ Verify & Claim[cite: 1]
                markup.add(InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{channel.replace('@','')}"))
                markup.add(InlineKeyboardButton("✔️ Verify & Claim", callback_data=f"check_task_{tid}"))
                status_text = f"Reward: *{reward} USDT*"
            else:
                status_text = "✅ *Completed*"

            bot.send_message(
                chat_id,
                f"📝 *{title}*\n\n"
                f"Channel: `{channel}`\n"
                f"{status_text}",
                reply_markup=markup if not done else None,
                parse_mode="Markdown"
            )
            sent_any = True

        if not sent_any:
            bot.send_message(chat_id, "❌ *No Tasks Available Right Now!*", parse_mode="Markdown")

    elif text == "📤 Withdraw":
        req_refs  = db["bot_settings"]["req_refs"]
        min_wd    = db["bot_settings"]["min_withdraw"]
        my_refs   = user_data["refs"]
        bal       = user_data["balance"]

        if my_refs < req_refs:
            bot.send_message(
                chat_id,
                f"❌ *Withdrawal Locked!*\n\n"
                f"Required Referrals: *{req_refs}*\n"
                f"Your Referrals: *{my_refs}*\n\n"
                f"Refer more people to unlock withdrawal!",
                parse_mode="Markdown"
            )
        elif bal < min_wd:
            bot.send_message(
                chat_id,
                f"❌ *Insufficient Balance!*\n\n"
                f"Minimum Withdraw: *{min_wd} USDT*\n"
                f"Your Balance: *{round(bal,2)} USDT*",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                f"📤 *Enter Withdrawal Amount (USDT):*\n\n"
                f"Minimum: *{min_wd} USDT*\n"
                f"Available: *{round(bal,2)} USDT*",
                parse_mode="Markdown"
            )
            user_steps[user_id] = "wait_amount"

    # ADMIN MENU HANDLERS (Restored button matching)[cite: 1]
    elif text == "⚙️ Admin Settings" and message.from_user.id == ADMIN_ID:
        s = db["bot_settings"]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Main Channel",     callback_data="set_channel"))
        markup.add(InlineKeyboardButton("Admin Channel",   callback_data="set_admin_channel"))
        markup.add(InlineKeyboardButton("Ref Bonus",       callback_data="set_bonus"))
        markup.add(InlineKeyboardButton("Req Referrals",   callback_data="set_refs"))
        markup.add(InlineKeyboardButton("Min Withdraw",    callback_data="set_min_withdraw"))
        markup.add(InlineKeyboardButton("Mining Reward",   callback_data="set_mining_reward"))
        markup.add(InlineKeyboardButton("Mining Hours",    callback_data="set_mining_hours"))
        markup.add(InlineKeyboardButton("Referral Mining %", callback_data="set_ref_mining_percent"))
        bot.send_message(
            chat_id,
            f"⚙️ *Bot Configuration*\n\n"
            f"Channel: `{s['channel_link']}`\n"
            f"Ref Bonus: *{s['ref_bonus']} USDT*\n"
            f"Req Refs: *{s['req_refs']}*\n"
            f"Min Withdraw: *{s['min_withdraw']} USDT*\n"
            f"Mining Reward: *{s['mining_reward']} USDT*\n"
            f"Mining Duration: *{s['mining_hours']} hour(s)*\n"
            f"Referral Mining %: *{s.get('ref_mining_percent', 10)}%*",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif text == "➕ Add Task" and message.from_user.id == ADMIN_ID:
        user_steps[user_id] = "add_task_title"
        bot.send_message(
            chat_id,
            "➕ *Step 1/3 Task Title*\n\nSend a title for this task:\n_(e.g. Join Crypto News Channel)_",
            parse_mode="Markdown"
        )

    elif text == "📋 All Tasks" and message.from_user.id == ADMIN_ID:
        tasks = db.get("tasks", {})
        if not tasks:
            bot.send_message(chat_id, "No tasks found.", parse_mode="Markdown")
            return
        for tid, task in tasks.items():
            channel    = task["channel"]
            reward     = task["reward"]
            title      = task.get("title", f"Task #{tid}")
            active     = task.get("active", True)
            done_count = len(task.get("done_users", []))
            status     = "🟢 Active" if active else "🔴 Inactive"

            markup = InlineKeyboardMarkup()
            # Restored Emojis: ✏️ Edit, 🗑 Delete, 🔴 Deactivate, 🟢 Activate[cite: 1]
            markup.add(
                InlineKeyboardButton("✏️ Edit",   callback_data=f"task_edit_{tid}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"task_delete_{tid}")
            )
            markup.add(
                InlineKeyboardButton(
                    "🔴 Deactivate" if active else "🟢 Activate",
                    callback_data=f"task_toggle_{tid}"
                )
            )
            markup.add(InlineKeyboardButton(f"✅ {done_count} Completed", callback_data=f"task_stats_{tid}"))

            bot.send_message(
                chat_id,
                f"📋 *{title}*\n\n"
                f"Channel: `{channel}`\n"
                f"Reward: *{reward} USDT*\n"
                f"Completed: *{done_count}*\n"
                f"Status: {status}",
                reply_markup=markup,
                parse_mode="Markdown"
            )

    elif text == "🔙 Back to User Menu":
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        # Restored User Menu with Emojis[cite: 1]
        markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
        markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
        markup.add(KeyboardButton("📤 Withdraw"))
        bot.send_message(chat_id, "🔙 *Switched to User Menu.*", reply_markup=markup, parse_mode="Markdown")

    # STEP HANDLERS (No logic changes)[cite: 1]
    elif step == "wait_amount":
        try:
            amount  = float(text)
            min_wd  = db["bot_settings"]["min_withdraw"]
            bal     = user_data["balance"]
            if amount <= 0 or amount > bal:
                bot.send_message(chat_id, "❌ *Invalid amount or insufficient balance.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            elif amount < min_wd:
                bot.send_message(chat_id, f"❌ *Minimum withdrawal is {min_wd} USDT.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            else:
                db["users"][user_id]["withdraw_amount"] = amount
                save_db(db)
                bot.send_message(chat_id, "🏦 *Enter your USDT (BEP20) Wallet Address:*", parse_mode="Markdown")
                user_steps[user_id] = "wait_address"
        except ValueError:
            bot.send_message(chat_id, "❌ *Please enter a valid number.*", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    elif step == "wait_address":
        address = text
        amount  = user_data.get("withdraw_amount", 0)
        db["users"][user_id]["balance"] -= amount
        save_db(db)
        user_steps.pop(user_id, None)

        username = message.from_user.username
        username_text = f"@{username}" if username else "No Username"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        markup = InlineKeyboardMarkup()
        # Restored Emojis: ✅ Approve, ❌ Reject[cite: 1]
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"wgrp_app_{user_id}_{amount}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"wgrp_rej_{user_id}_{amount}")
        )
        
        group_id = db["bot_settings"].get("admin_channel", str(ADMIN_ID))
        group_msg = (
            f"💸 NEW WITHDRAWAL REQUEST\n"
            f"👤 User ID: {user_id}\n"
            f"👤 Username: {username_text}\n"
            f"💰 Amount: {amount} USDT\n"
            f"🏦 Wallet:\n{address}\n"
            f"📅 Time:\n{now_str}\n"
            f"Status:\n⏳ Pending"
        )
        try:
            bot.send_message(group_id, group_msg, reply_markup=markup)
        except Exception as e:
            print(f"Error routing request: {e}")
            
        bot.send_message(chat_id, "✅ *Withdrawal Request Submitted!*\n\nPlease wait for admin approval.", parse_mode="Markdown")

    # ADMIN TASK STEP HANDLERS (No logic changes)[cite: 1]
    elif step == "add_task_title" and message.from_user.id == ADMIN_ID:
        user_steps[user_id] = {"action": "add_task", "title": text, "phase": "channel"}
        bot.send_message(
            chat_id,
            f"Title set: *{text}*\n\n"
            f"➕ *Step 2/3 Channel*\n\nSend the task channel link:\n_(e.g. @MyChannel)_",
            parse_mode="Markdown"
        )

    elif isinstance(step, dict) and step.get("action") == "add_task":
        phase = step.get("phase")
        if phase == "channel" and message.from_user.id == ADMIN_ID:
            step["channel"] = text
            step["phase"]   = "reward"
            user_steps[user_id] = step
            bot.send_message(
                chat_id,
                f"Channel set: `{text}`\n\n"
                f"➕ *Step 3/3 Reward*\n\nSend the reward amount:\n_(e.g. 0.50)_",
                parse_mode="Markdown"
            )

        elif phase == "reward" and message.from_user.id == ADMIN_ID:
            try:
                reward = float(text)
                if reward <= 0: raise ValueError
                tid = next_task_id()
                db["tasks"][tid] = {
                    "title": step["title"],
                    "channel": step["channel"],
                    "reward": reward,
                    "active": True,
                    "done_users": []
                }
                save_db(db)
                user_steps.pop(user_id, None)
                bot.send_message(chat_id, f"✅ *Task #{tid} Added!*", parse_mode="Markdown")
            except ValueError:
                bot.send_message(chat_id, "Invalid amount.", parse_mode="Markdown")
                user_steps.pop(user_id, None)

    # TASK EDIT STEP HANDLERS (No logic changes)[cite: 1]
    elif isinstance(step, dict) and step.get("action") == "edit_task":
        phase = step.get("phase")
        tid   = step.get("tid")
        if phase == "edit_title" and message.from_user.id == ADMIN_ID:
            db["tasks"][tid]["title"] = text
            save_db(db)
            user_steps.pop(user_id, None)
            bot.send_message(chat_id, f"✅ Title updated: *{text}*", parse_mode="Markdown")
        elif phase == "edit_channel" and message.from_user.id == ADMIN_ID:
            db["tasks"][tid]["channel"] = text
            save_db(db)
            user_steps.pop(user_id, None)
            bot.send_message(chat_id, f"✅ Channel updated: `{text}`", parse_mode="Markdown")
        elif phase == "edit_reward" and message.from_user.id == ADMIN_ID:
            try:
                reward = float(text)
                db["tasks"][tid]["reward"] = reward
                save_db(db)
                bot.send_message(chat_id, f"✅ Reward updated: *{reward} USDT*", parse_mode="Markdown")
            except ValueError:
                bot.send_message(chat_id, "Invalid amount.", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    # SETTINGS STEP HANDLERS (No logic changes)[cite: 1]
    elif step in ["set_channel", "set_admin_channel", "set_bonus", "set_refs", "set_min_withdraw", "set_mining_reward", "set_mining_hours", "set_ref_mining_percent"] and message.from_user.id == ADMIN_ID:
        try:
            if "hours" in step or "percent" in step or "reward" in step or "withdraw" in step or "bonus" in step:
                db["bot_settings"][step] = float(text) if "percent" not in step else int(text)
            elif "refs" in step:
                db["bot_settings"][step] = int(text)
            else:
                db["bot_settings"][step] = text
            save_db(db)
            bot.send_message(chat_id, f"✅ Configuration updated.", parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "❌ Error updating value.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

# ==========================================
#   Callback Handler
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    data    = call.data

    if data == "check_join":
        channel = db["bot_settings"]["channel_link"]
        try:
            status = bot.get_chat_member(channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                # Restored User Menu with Emojis[cite: 1]
                markup.add(KeyboardButton("💰 Balance"), KeyboardButton("⛏ Mining"))
                markup.add(KeyboardButton("👥 Referral"), KeyboardButton("📝 Tasks"))
                markup.add(KeyboardButton("📤 Withdraw"))
                bot.send_message(call.message.chat.id, "✅ *Verification Successful!*", reply_markup=markup, parse_mode="Markdown")
                bot.answer_callback_query(call.id)
                
                referrer = db["users"][user_id].get("referrer")
                if referrer and referrer in db["users"] and not db["users"][user_id].get("rewarded"):
                    db["users"][referrer]["refs"]    += 1
                    db["users"][user_id]["rewarded"]  = True
                    save_db(db)
            else:
                bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "Error verifying status.", show_alert=True)

    elif data.startswith("check_task_"):
        tid  = data.replace("check_task_", "")
        task = db.get("tasks", {}).get(tid)
        if not task: return bot.answer_callback_query(call.id, "Task not found.")
        
        completed = db["users"][user_id].get("completed_tasks", [])
        if tid in completed: return bot.answer_callback_query(call.id, "Already done!", show_alert=True)

        try:
            status = bot.get_chat_member(task["channel"], call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                reward = task["reward"]
                db["users"][user_id]["balance"] += reward
                db["users"][user_id]["completed_tasks"].append(tid)
                task["done_users"].append(user_id)
                save_db(db)
                bot.send_message(call.message.chat.id, f"✅ *Task Completed!* Received *{reward} USDT*", parse_mode="Markdown")
                bot.answer_callback_query(call.id)
            else:
                bot.answer_callback_query(call.id, "Join the task channel first!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "Error verifying task.", show_alert=True)

    elif data.startswith("task_edit_") and call.from_user.id == ADMIN_ID:
        tid  = data.replace("task_edit_", "")
        markup = InlineKeyboardMarkup()
        # Restored Button Texts: Edit Title, Edit Channel, Edit Reward[cite: 1]
        markup.add(InlineKeyboardButton("Edit Title", callback_data=f"tedit_title_{tid}"))
        markup.add(InlineKeyboardButton("Edit Channel", callback_data=f"tedit_channel_{tid}"))
        markup.add(InlineKeyboardButton("Edit Reward", callback_data=f"tedit_reward_{tid}"))
        bot.send_message(call.message.chat.id, "✏️ *Edit Task*", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data.startswith("tedit_"):
        parts = data.split("_", 2)
        user_steps[user_id] = {"action": "edit_task", "tid": parts[2], "phase": f"edit_{parts[1]}"}
        bot.send_message(call.message.chat.id, f"Send new {parts[1]}:")
        bot.answer_callback_query(call.id)

    elif data.startswith("task_delete_"):
        tid = data.replace("task_delete_", "")
        del db["tasks"][tid]
        save_db(db)
        bot.send_message(call.message.chat.id, "🗑 Task deleted.")
        bot.answer_callback_query(call.id)

    elif data.startswith("task_toggle_"):
        tid = data.replace("task_toggle_", "")
        db["tasks"][tid]["active"] = not db["tasks"][tid]["active"]
        save_db(db)
        bot.answer_callback_query(call.id, "Status toggled.")

    elif data.startswith("wgrp_app_") or data.startswith("wgrp_rej_"):
        is_app = "app" in data
        parts = data.split("_")
        t_user = parts[2]
        amount = float(parts[3])
        
        if is_app:
            bot.send_message(t_user, f"✅ *Withdrawal Approved!* *{amount} USDT* sent.")
            bot.edit_message_text("✅ *APPROVED*", call.message.chat.id, call.message.message_id)
        else:
            db2 = load_db()
            db2["users"][t_user]["balance"] += amount
            save_db(db2)
            bot.send_message(t_user, f"❌ *Withdrawal Rejected!* *{amount} USDT* returned.")
            bot.edit_message_text("❌ *REJECTED*", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data in ["set_channel", "set_admin_channel", "set_bonus", "set_refs", "set_min_withdraw", "set_mining_reward", "set_mining_hours", "set_ref_mining_percent"]:
        user_steps[user_id] = data
        bot.send_message(call.message.chat.id, f"Send new value for {data}:")
        bot.answer_callback_query(call.id)

# ==========================================
#   Render Integration
# ==========================================

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!"

def run_bot():
    while True:
        try:
            bot.polling(non_stop=True, timeout=60)
        except:
            time.sleep(5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
