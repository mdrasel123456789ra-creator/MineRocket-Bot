import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import json
import os
import threading
import time
import datetime
# --- NEW CHANGE: Imported Flask for Render Web Service Health Check ---
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
#          
# ==========================================

DB_FILE = "database.json"

DEFAULT_SETTINGS = {
    "channel_link": "@MineRocket",
    "admin_channel": str(ADMIN_ID),
    "ref_bonus": 0.5,
    "req_refs": 3,
    "min_withdraw": 5.0,       #                     
    "mining_reward": 0.10,     #                 USDT
    "mining_hours": 1,         #                       
    "ref_mining_percent": 10,  # Added: Referral Mining Percentage Setting
}

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "tasks": {}, "bot_settings": DEFAULT_SETTINGS.copy()}
    with open(DB_FILE, "r") as f:
        data = json.load(f)
    #      settings key                  
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
user_steps = {}       #                 step
mining_timers = {}    # active mining timers {user_id: Timer}

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
    #       user-       field    
    if "mining_start" not in user:
        user["mining_start"] = None
    if "completed_tasks" not in user:
        user["completed_tasks"] = []
    return user

# task_id         
def next_task_id():
    if not db["tasks"]:
        return "1"
    return str(max(int(k) for k in db["tasks"].keys()) + 1)

# ==========================================
#                         
# ==========================================

def give_mining_reward(user_id, chat_id):
    db2 = load_db()
    uid = str(user_id)
    if uid in db2["users"] and db2["users"][uid]["mining_status"] == "running":
        reward = db2["bot_settings"]["mining_reward"]
        db2["users"][uid]["balance"] += reward
        db2["users"][uid]["mining_status"] = "stopped"
        db2["users"][uid]["mining_start"] = None
        
        # --- FEATURE #1: REFERRAL MINING COMMISSION SYSTEM ---
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
                f"  *Mining Completed!*\n\n"
                f"  You received *{reward} USDT*\n"
                f"  Click *Mining* button to start again!",
                parse_mode="Markdown"
            )
        except:
            pass

#                   
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
#   /start       
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
    keyboard.add(InlineKeyboardButton("  JOIN OFFICIAL CHANNEL", url=f"https://t.me/{channel.replace('@', '')}"))
    keyboard.add(InlineKeyboardButton("   I have Joined", callback_data="check_join"))

    bot.send_message(
        message.chat.id,
        f"  *WELCOME TO MINE ROCKET* \n\n"
        f"  Hello *{first}*!\n\n"
        f"  *Fast & Secure Mining Service*\n"
        f"  *Earn & Withdraw USDT Easily*\n\n"
        f"  Please join our official channel below to unlock the bot:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==========================================
#     /admin       
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("   Admin Settings"), KeyboardButton("  Add Task"))
    markup.add(KeyboardButton("  All Tasks"), KeyboardButton("  Back to User Menu"))
    bot.send_message(
        message.chat.id,
        "    *Mine Rocket Admin Dashboard*\n\nWelcome to the control panel.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==========================================
#                         
# ==========================================

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    text = message.text
    user_data = get_user(user_id)
    step = user_steps.get(user_id)

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # USER MENU
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    if text == "  Balance":
        bal = user_data["balance"]
        min_wd = db["bot_settings"]["min_withdraw"]
        bot.send_message(
            chat_id,
            f"  *ACCOUNT BALANCE*\n\n"
            f"  Available: *{round(bal, 2)} USDT*\n"
            f"  Min Withdraw: *{min_wd} USDT*",
            parse_mode="Markdown"
        )

    elif text == "  Mining":
        s = db["bot_settings"]
        reward    = s["mining_reward"]
        hours     = s["mining_hours"]
        total_sec = hours * 3600

        if user_data["mining_status"] == "running":
            # countdown      
            start_time = user_data.get("mining_start") or time.time()
            elapsed    = time.time() - start_time
            remaining  = max(0, total_sec - elapsed)
            countdown  = format_countdown(remaining)
            bot.send_message(
                chat_id,
                f"  *Mining in Progress...*\n\n"
                f"  Time Remaining: *{countdown}*\n"
                f"  Reward: *{reward} USDT*\n\n"
                f"_We'll notify you when it's done!_",
                parse_mode="Markdown"
            )
        else:
            db["users"][user_id]["mining_status"] = "running"
            db["users"][user_id]["mining_start"]  = time.time()
            save_db(db)

            #       timer cancel     (        )
            if user_id in mining_timers:
                mining_timers[user_id].cancel()

            t = threading.Timer(total_sec, give_mining_reward, args=[user_id, chat_id])
            t.daemon = True
            t.start()
            mining_timers[user_id] = t

            bot.send_message(
                chat_id,
                f"  *Mining Started!*\n\n"
                f"  Duration: *{hours} hour(s)*\n"
                f"  Reward: *{reward} USDT*\n\n"
                f"  Time Remaining: *{format_countdown(total_sec)}*\n\n"
                f"_We will notify you automatically when mining is complete!_",
                parse_mode="Markdown"
            )

    elif text == "  Referral":
        bot_username = bot.get_me().username
        ref_bonus  = db["bot_settings"]["ref_bonus"]
        ref_count  = user_data["refs"]
        ref_link   = f"https://t.me/{bot_username}?start={user_id}"
        bot.send_message(
            chat_id,
            f"  *Affiliate Program*\n\n"
            f"  Bonus Per Referral: *{ref_bonus} USDT*\n"
            f"  Total Referrals: *{ref_count}*\n\n"
            f"  *Your Invitation Link:*\n`{ref_link}`",
            parse_mode="Markdown"
        )

    elif text == "  Tasks":
        tasks = db.get("tasks", {})
        active_tasks = {tid: t for tid, t in tasks.items() if t.get("active", True)}
        if not active_tasks:
            bot.send_message(chat_id, "  *No Tasks Available Right Now!*", parse_mode="Markdown")
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
                markup.add(InlineKeyboardButton("  Join Channel", url=f"https://t.me/{channel.replace('@','')}"))
                markup.add(InlineKeyboardButton("   Verify & Claim", callback_data=f"check_task_{tid}"))
                status_text = f"  Reward: *{reward} USDT*"
            else:
                status_text = "  *Completed*"

            bot.send_message(
                chat_id,
                f"  *{title}*\n\n"
                f"  Channel: `{channel}`\n"
                f"{status_text}",
                reply_markup=markup if not done else None,
                parse_mode="Markdown"
            )
            sent_any = True

        if not sent_any:
            bot.send_message(chat_id, "  *No Tasks Available Right Now!*", parse_mode="Markdown")

    elif text == "  Withdraw":
        req_refs  = db["bot_settings"]["req_refs"]
        min_wd    = db["bot_settings"]["min_withdraw"]
        my_refs   = user_data["refs"]
        bal       = user_data["balance"]

        if my_refs < req_refs:
            bot.send_message(
                chat_id,
                f"  *Withdrawal Locked!*\n\n"
                f"  Required Referrals: *{req_refs}*\n"
                f"  Your Referrals: *{my_refs}*\n\n"
                f"Refer more people to unlock withdrawal!",
                parse_mode="Markdown"
            )
        elif bal < min_wd:
            bot.send_message(
                chat_id,
                f"  *Insufficient Balance!*\n\n"
                f"  Minimum Withdraw: *{min_wd} USDT*\n"
                f"  Your Balance: *{round(bal,2)} USDT*",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                f"  *Enter Withdrawal Amount (USDT):*\n\n"
                f"  Minimum: *{min_wd} USDT*\n"
                f"  Available: *{round(bal,2)} USDT*",
                parse_mode="Markdown"
            )
            user_steps[user_id] = "wait_amount"

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # ADMIN MENU
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    elif text == "   Admin Settings" and message.from_user.id == ADMIN_ID:
        s = db["bot_settings"]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("  Main Channel",     callback_data="set_channel"))
        markup.add(InlineKeyboardButton("  Admin Channel",   callback_data="set_admin_channel"))
        markup.add(InlineKeyboardButton("  Ref Bonus",       callback_data="set_bonus"))
        markup.add(InlineKeyboardButton("  Req Referrals",   callback_data="set_refs"))
        markup.add(InlineKeyboardButton("  Min Withdraw",    callback_data="set_min_withdraw"))
        markup.add(InlineKeyboardButton("  Mining Reward",   callback_data="set_mining_reward"))
        markup.add(InlineKeyboardButton("  Mining Hours",    callback_data="set_mining_hours"))
        markup.add(InlineKeyboardButton("📈 Referral Mining %", callback_data="set_ref_mining_percent"))
        bot.send_message(
            chat_id,
            f"   *Bot Configuration*\n\n"
            f"  Channel: `{s['channel_link']}`\n"
            f"  Ref Bonus: *{s['ref_bonus']} USDT*\n"
            f"  Req Refs: *{s['req_refs']}*\n"
            f"  Min Withdraw: *{s['min_withdraw']} USDT*\n"
            f"  Mining Reward: *{s['mining_reward']} USDT*\n"
            f"  Mining Duration: *{s['mining_hours']} hour(s)*\n"
            f"  Referral Mining %: *{s.get('ref_mining_percent', 10)}%*",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif text == "  Add Task" and message.from_user.id == ADMIN_ID:
        user_steps[user_id] = "add_task_title"
        bot.send_message(
            chat_id,
            "  *Step 1/3   Task Title*\n\nSend a title for this task:\n_(e.g. Join Crypto News Channel)_",
            parse_mode="Markdown"
        )

    elif text == "  All Tasks" and message.from_user.id == ADMIN_ID:
        tasks = db.get("tasks", {})
        if not tasks:
            bot.send_message(chat_id, "  No tasks found.", parse_mode="Markdown")
            return
        for tid, task in tasks.items():
            channel    = task["channel"]
            reward     = task["reward"]
            title      = task.get("title", f"Task #{tid}")
            active     = task.get("active", True)
            done_count = len(task.get("done_users", []))
            status     = "  Active" if active else "  Inactive"

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("   Edit",   callback_data=f"task_edit_{tid}"),
                InlineKeyboardButton("  Delete", callback_data=f"task_delete_{tid}")
            )
            markup.add(
                InlineKeyboardButton(
                    "  Deactivate" if active else "  Activate",
                    callback_data=f"task_toggle_{tid}"
                )
            )
            markup.add(InlineKeyboardButton(f"  {done_count} Completed", callback_data=f"task_stats_{tid}"))

            bot.send_message(
                chat_id,
                f"  *{title}*\n\n"
                f"  Channel: `{channel}`\n"
                f"  Reward: *{reward} USDT*\n"
                f"  Completed: *{done_count}*\n"
                f"Status: {status}",
                reply_markup=markup,
                parse_mode="Markdown"
            )

    elif text == "  Back to User Menu":
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("  Balance"), KeyboardButton("  Mining"))
        markup.add(KeyboardButton("  Referral"), KeyboardButton("  Tasks"))
        markup.add(KeyboardButton("  Withdraw"))
        bot.send_message(chat_id, "  *Switched to User Menu.*", reply_markup=markup, parse_mode="Markdown")

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # USER STEPS   Withdrawal
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    elif step == "wait_amount":
        try:
            amount  = float(text)
            min_wd  = db["bot_settings"]["min_withdraw"]
            bal     = user_data["balance"]
            if amount <= 0 or amount > bal:
                bot.send_message(chat_id, "   *Invalid amount or insufficient balance.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            elif amount < min_wd:
                bot.send_message(chat_id, f"   *Minimum withdrawal is {min_wd} USDT.*", parse_mode="Markdown")
                user_steps.pop(user_id, None)
            else:
                db["users"][user_id]["withdraw_amount"] = amount
                save_db(db)
                bot.send_message(chat_id, "  *Enter your USDT (BEP20) Wallet Address:*", parse_mode="Markdown")
                user_steps[user_id] = "wait_address"
        except ValueError:
            bot.send_message(chat_id, "   *Please enter a valid number.*", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    elif step == "wait_address":
        address = text
        amount  = user_data.get("withdraw_amount", 0)
        db["users"][user_id]["balance"] -= amount
        save_db(db)
        user_steps.pop(user_id, None)

        # --- FEATURE #2: PRIVATE GROUP WITHDRAW SYSTEM ---
        username = message.from_user.username
        username_text = f"@{username}" if username else "No Username"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"wgrp_app_{user_id}_{amount}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"wgrp_rej_{user_id}_{amount}")
        )
        
        group_id = -1004387474085
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
            print(f"Error routing request to group: {e}")
            
        bot.send_message(chat_id, "  *Withdrawal Request Submitted!*\n\nPlease wait for admin approval.", parse_mode="Markdown")

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # ADMIN STEPS   Add Task (3 steps)
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    elif step == "add_task_title" and message.from_user.id == ADMIN_ID:
        user_steps[user_id] = {"action": "add_task", "title": text, "phase": "channel"}
        bot.send_message(
            chat_id,
            f"  Title set: *{text}*\n\n"
            f"  *Step 2/3   Channel*\n\nSend the task channel link:\n_(e.g. @MyChannel)_",
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
                f"  Channel set: `{text}`\n\n"
                f"  *Step 3/3   Reward*\n\nSend the reward amount:\n_(e.g. 0.50)_",
                parse_mode="Markdown"
            )

        elif phase == "reward" and message.from_user.id == ADMIN_ID:
            try:
                reward = float(text)
                if reward <= 0:
                    raise ValueError
                tid   = next_task_id()
                title = step["title"]
                chan  = step["channel"]
                db["tasks"][tid] = {
                    "title":      title,
                    "channel":    chan,
                    "reward":     reward,
                    "active":     True,
                    "done_users": []
                }
                save_db(db)
                user_steps.pop(user_id, None)
                bot.send_message(
                    chat_id,
                    f"  *Task #{tid} Added!*\n\n"
                    f"  Title: *{title}*\n"
                    f"  Channel: `{chan}`\n"
                    f"  Reward: *{reward} USDT*\n\n"
                    f"   Make sure the bot is *admin* in `{chan}`",
                    parse_mode="Markdown"
                )
            except ValueError:
                bot.send_message(chat_id, "   Invalid amount. Send a valid number (e.g. 0.50)", parse_mode="Markdown")
                user_steps.pop(user_id, None)

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # ADMIN STEPS   Edit Task
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    elif isinstance(step, dict) and step.get("action") == "edit_task":
        phase = step.get("phase")
        tid   = step.get("tid")

        if phase == "edit_title" and message.from_user.id == ADMIN_ID:
            db["tasks"][tid]["title"] = text
            save_db(db)
            user_steps.pop(user_id, None)
            bot.send_message(chat_id, f"  Title updated to: *{text}*", parse_mode="Markdown")

        elif phase == "edit_channel" and message.from_user.id == ADMIN_ID:
            db["tasks"][tid]["channel"] = text
            save_db(db)
            user_steps.pop(user_id, None)
            bot.send_message(chat_id, f"  Channel updated to: `{text}`", parse_mode="Markdown")

        elif phase == "edit_reward" and message.from_user.id == ADMIN_ID:
            try:
                reward = float(text)
                db["tasks"][tid]["reward"] = reward
                save_db(db)
                bot.send_message(chat_id, f"  Reward updated to: *{reward} USDT*", parse_mode="Markdown")
            except ValueError:
                bot.send_message(chat_id, "   Invalid amount.", parse_mode="Markdown")
            user_steps.pop(user_id, None)

    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ
    # ADMIN STEPS   Settings
    # ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ

    elif step == "set_channel" and message.from_user.id == ADMIN_ID:
        db["bot_settings"]["channel_link"] = text
        save_db(db)
        bot.send_message(chat_id, f"  Main channel updated: `{text}`", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_admin_channel" and message.from_user.id == ADMIN_ID:
        db["bot_settings"]["admin_channel"] = text
        save_db(db)
        bot.send_message(chat_id, f"  Admin channel updated: `{text}`", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_bonus" and message.from_user.id == ADMIN_ID:
        try:
            db["bot_settings"]["ref_bonus"] = float(text)
            save_db(db)
            bot.send_message(chat_id, f"  Ref bonus updated: *{text} USDT*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid amount.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_refs" and message.from_user.id == ADMIN_ID:
        try:
            db["bot_settings"]["req_refs"] = int(text)
            save_db(db)
            bot.send_message(chat_id, f"  Required refs updated: *{text}*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid number.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_min_withdraw" and message.from_user.id == ADMIN_ID:
        try:
            val = float(text)
            db["bot_settings"]["min_withdraw"] = val
            save_db(db)
            bot.send_message(chat_id, f"  Min withdraw updated: *{val} USDT*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid amount.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_mining_reward" and message.from_user.id == ADMIN_ID:
        try:
            val = float(text)
            db["bot_settings"]["mining_reward"] = val
            save_db(db)
            bot.send_message(chat_id, f"  Mining reward updated: *{val} USDT*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid amount.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_mining_hours" and message.from_user.id == ADMIN_ID:
        try:
            val = float(text)
            if val <= 0:
                raise ValueError
            db["bot_settings"]["mining_hours"] = val
            save_db(db)
            bot.send_message(chat_id, f"  Mining duration updated: *{val} hour(s)*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid number.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

    elif step == "set_ref_mining_percent" and message.from_user.id == ADMIN_ID:
        try:
            val = int(text)
            if val < 0:
                raise ValueError
            db["bot_settings"]["ref_mining_percent"] = val
            save_db(db)
            bot.send_message(chat_id, f"  Referral Mining % updated: *{val}%*", parse_mode="Markdown")
        except ValueError:
            bot.send_message(chat_id, "   Invalid number. Send a valid integer percentage.", parse_mode="Markdown")
        user_steps.pop(user_id, None)

# ==========================================
#                             
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    data    = call.data

    # ÄÄ                   ÄÄ
    if data == "check_join":
        channel = db["bot_settings"]["channel_link"]
        try:
            status = bot.get_chat_member(channel, call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(KeyboardButton("  Balance"), KeyboardButton("  Mining"))
                markup.add(KeyboardButton("  Referral"), KeyboardButton("  Tasks"))
                markup.add(KeyboardButton("  Withdraw"))
                bot.send_message(
                    call.message.chat.id,
                    "  *Verification Successful!*\n\nWelcome to Mine Rocket!  ",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
                # --- FEATURE #1 MODIFICATION: Only increments referral count upon successful join ---
                referrer = db["users"][user_id].get("referrer")
                if referrer and referrer in db["users"] and not db["users"][user_id].get("rewarded"):
                    db["users"][referrer]["refs"]    += 1
                    db["users"][user_id]["rewarded"]  = True
                    save_db(db)
            else:
                bot.answer_callback_query(call.id, "  You haven't joined the channel yet!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "   Error! Make sure the bot is admin in the channel.", show_alert=True)

    # ÄÄ               ÄÄ
    elif data.startswith("check_task_"):
        tid  = data.replace("check_task_", "")
        task = db.get("tasks", {}).get(tid)
        if not task:
            bot.answer_callback_query(call.id, "   Task not found.", show_alert=True)
            return
        if not task.get("active", True):
            bot.answer_callback_query(call.id, "   This task is no longer active.", show_alert=True)
            return

        completed = db["users"][user_id].get("completed_tasks", [])
        if tid in completed:
            bot.answer_callback_query(call.id, "  You already completed this task!", show_alert=True)
            return

        try:
            status = bot.get_chat_member(task["channel"], call.from_user.id).status
            if status in ['member', 'administrator', 'creator']:
                reward = task["reward"]
                db["users"][user_id]["balance"] += reward
                if "completed_tasks" not in db["users"][user_id]:
                    db["users"][user_id]["completed_tasks"] = []
                db["users"][user_id]["completed_tasks"].append(tid)
                if "done_users" not in task:
                    task["done_users"] = []
                task["done_users"].append(user_id)
                save_db(db)
                bot.send_message(
                    call.message.chat.id,
                    f"  *Task Completed!*\n\nYou received *{reward} USDT* ",
                    parse_mode="Markdown"
                )
            else:
                bot.answer_callback_query(call.id, "  You haven't joined the task channel yet!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, "   Error! Make sure the bot is admin in the task channel.", show_alert=True)

    # ÄÄ Task Edit Menu ÄÄ
    elif data.startswith("task_edit_") and call.from_user.id == ADMIN_ID:
        tid  = data.replace("task_edit_", "")
        task = db.get("tasks", {}).get(tid)
        if not task:
            bot.answer_callback_query(call.id, "Task not found.", show_alert=True)
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("   Edit Title",   callback_data=f"tedit_title_{tid}"))
        markup.add(InlineKeyboardButton("  Edit Channel", callback_data=f"tedit_channel_{tid}"))
        markup.add(InlineKeyboardButton("  Edit Reward",  callback_data=f"tedit_reward_{tid}"))
        bot.send_message(
            call.message.chat.id,
            f"   *Edit Task #{tid}*\n\nWhat do you want to edit?",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data.startswith("tedit_") and call.from_user.id == ADMIN_ID:
        parts  = data.split("_", 2)  # tedit, field, tid
        field  = parts[1]
        tid    = parts[2]
        prompts = {
            "title":   "   Send new title:",
            "channel": "  Send new channel link (e.g. @Channel):",
            "reward":  "  Send new reward amount (e.g. 0.50):"
        }
        user_steps[user_id] = {"action": "edit_task", "tid": tid, "phase": f"edit_{field}"}
        bot.send_message(call.message.chat.id, prompts[field], parse_mode="Markdown")

    # ÄÄ Task Delete ÄÄ
    elif data.startswith("task_delete_") and call.from_user.id == ADMIN_ID:
        tid = data.replace("task_delete_", "")
        if tid in db.get("tasks", {}):
            title = db["tasks"][tid].get("title", f"Task #{tid}")
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("  Yes, Delete", callback_data=f"task_confirm_delete_{tid}"),
                InlineKeyboardButton("  Cancel",       callback_data="task_cancel")
            )
            bot.send_message(
                call.message.chat.id,
                f"  *Delete '{title}'?*\n\nThis cannot be undone.",
                reply_markup=markup,
                parse_mode="Markdown"
            )

    elif data.startswith("task_confirm_delete_") and call.from_user.id == ADMIN_ID:
        tid = data.replace("task_confirm_delete_", "")
        if tid in db.get("tasks", {}):
            del db["tasks"][tid]
            save_db(db)
            bot.send_message(call.message.chat.id, f"  *Task #{tid} deleted.*", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "Task not found.", show_alert=True)

    elif data == "task_cancel":
        bot.answer_callback_query(call.id, "Cancelled.", show_alert=False)

    # ÄÄ Task Toggle Active/Inactive ÄÄ
    elif data.startswith("task_toggle_") and call.from_user.id == ADMIN_ID:
        tid  = data.replace("task_toggle_", "")
        task = db.get("tasks", {}).get(tid)
        if task:
            task["active"] = not task.get("active", True)
            save_db(db)
            state = "  Activated" if task["active"] else "  Deactivated"
            bot.answer_callback_query(call.id, f"{state}", show_alert=True)

    # ÄÄ Task Stats ÄÄ
    elif data.startswith("task_stats_") and call.from_user.id == ADMIN_ID:
        tid  = data.replace("task_stats_", "")
        task = db.get("tasks", {}).get(tid)
        if task:
            done_users = task.get("done_users", [])
            count = len(done_users)
            bot.answer_callback_query(
                call.id,
                f"  Task #{tid}   {count} user(s) completed this task.",
                show_alert=True
            )

    # --- FEATURE #2: GROUP WITHDRAW CALLBACK HANDLERS ---
    elif data.startswith("wgrp_app_") or data.startswith("wgrp_rej_"):
        try:
            status = bot.get_chat_member(call.message.chat.id, call.from_user.id).status
            if status not in ['administrator', 'creator']:
                bot.answer_callback_query(call.id, "❌ Only group admins can manage withdrawals.", show_alert=True)
                return
        except:
            bot.answer_callback_query(call.id, "❌ Error verifying group admin security permissions.", show_alert=True)
            return

        msg_text = call.message.text or ""
        if "Status:\nApproved" in msg_text or "Status:\nRejected" in msg_text:
            bot.answer_callback_query(call.id, "❌ This transaction has already been resolved.", show_alert=True)
            return

        is_approve = data.startswith("wgrp_app_")
        parts = data.split("_")
        target_user = parts[2]
        try:
            amount = float(parts[3])
        except ValueError:
            amount = 0.0

        admin_name = call.from_user.first_name
        if call.from_user.last_name:
            admin_name += f" {call.from_user.last_name}"

        if is_approve:
            try:
                bot.send_message(
                    target_user,
                    f"✅ Withdrawal Approved!\n"
                    f"💰 Amount: {amount} USDT\n"
                    f"Your withdrawal request has been approved.",
                    parse_mode="Markdown"
                )
            except:
                pass

            new_msg = (
                f"✅ WITHDRAWAL APPROVED\n"
                f"👤 User ID: {target_user}\n"
                f"💰 Amount: {amount} USDT\n"
                f"👨‍💼 Approved By:\n{admin_name}\n"
                f"Status:\nApproved"
            )
            try:
                bot.edit_message_text(new_msg, call.message.chat.id, call.message.message_id, reply_markup=None)
            except:
                pass
            bot.answer_callback_query(call.id, "Withdrawal approved successfully.")

        else:
            db2 = load_db()
            tuid = str(target_user)
            if tuid in db2["users"]:
                db2["users"][tuid]["balance"] += amount
                save_db(db2)
                db.update(db2)

            try:
                bot.send_message(
                    target_user,
                    f"❌ Withdrawal Rejected\n"
                    f"💰 {amount} USDT returned to your balance.",
                    parse_mode="Markdown"
                )
            except:
                pass

            new_msg = (
                f"❌ WITHDRAWAL REJECTED\n"
                f"👤 User ID: {target_user}\n"
                f"💰 Amount: {amount} USDT\n"
                f"👨‍💼 Rejected By:\n{admin_name}\n"
                f"Status:\nRejected"
            )
            try:
                bot.edit_message_text(new_msg, call.message.chat.id, call.message.message_id, reply_markup=None)
            except:
                pass
            bot.answer_callback_query(call.id, "Withdrawal rejected successfully.")

    # Legacy Withdrawal Approve (Kept for backwards compatibility)
    elif data.startswith("app_") and call.from_user.id == ADMIN_ID:
        parts       = data.split("_")
        target_user = parts[1]
        amount      = parts[2]
        try:
            bot.send_message(target_user, f"  *Withdrawal Approved!*\n\n  *{amount} USDT* has been sent to your wallet.", parse_mode="Markdown")
        except:
            pass
        try:
            bot.edit_message_text(
                f"  *APPROVED*\n\nUser: `{target_user}`\nAmount: {amount} USDT",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown"
            )
        except:
            pass

    # Legacy Withdrawal Reject (Kept for backwards compatibility)
    elif data.startswith("rej_") and call.from_user.id == ADMIN_ID:
        parts       = data.split("_")
        target_user = parts[1]
        amount      = float(parts[2])
        if target_user in db["users"]:
            db["users"][target_user]["balance"] += amount
            save_db(db)
        try:
            bot.send_message(target_user, f"  *Withdrawal Rejected!*\n\n*{amount} USDT* has been returned to your balance.", parse_mode="Markdown")
        except:
            pass
        try:
            bot.edit_message_text(
                f"  *REJECTED*\n\nUser: `{target_user}`\nAmount: {amount} USDT",
                call.message.chat.id, call.message.message_id, parse_mode="Markdown"
            )
        except:
            pass

    # ÄÄ Admin Settings Callbacks ÄÄ
    elif data in ["set_channel", "set_admin_channel", "set_bonus", "set_refs",
                  "set_min_withdraw", "set_mining_reward", "set_mining_hours", "set_ref_mining_percent"] and call.from_user.id == ADMIN_ID:
        user_steps[user_id] = data
        prompts = {
            "set_channel":        "  Send the new Main Channel link:\n_(e.g. @MineRocket)_",
            "set_admin_channel":  "  Send Admin/Withdraw Channel link:\n_(e.g. @AdminChannel)_",
            "set_bonus":          "  Send the new referral bonus:\n_(e.g. 0.5)_",
            "set_refs":           "  Send required referral count:\n_(e.g. 3)_",
            "set_min_withdraw":   "  Send minimum withdrawal amount:\n_(e.g. 5.0)_",
            "set_mining_reward":  "  Send mining reward per session:\n_(e.g. 0.10)_",
            "set_mining_hours":   "  Send mining duration in hours:\n_(e.g. 1 or 0.5 for 30 minutes)_",
            "set_ref_mining_percent": "📈 Referral Mining %\n\nSend new referral mining percentage:\n_(e.g. 10)_",
        }
        bot.send_message(call.message.chat.id, prompts[data], parse_mode="Markdown")

# ==========================================
#   Render Web Service Integration & Bot Start
# ==========================================

# --- NEW CHANGE: Initialize Flask app ---
app = Flask(__name__)

# --- NEW CHANGE: Added root route for Render health checks ---
@app.route('/')
def health_check():
    return "  Mine Rocket Bot is running successfully!"

# --- NEW CHANGE: Wrapped polling in a resilient while-loop function ---
def run_bot():
    while True:
        try:
            print("  Starting Telegram bot polling...")
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"   Bot polling failed: {e}")
            time.sleep(5)  # Wait 5 seconds before attempting to restart

if __name__ == "__main__":
    # --- NEW CHANGE: Start Telegram bot in a background thread ---
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # --- NEW CHANGE: Start Flask server on 0.0.0.0 and dynamically bind PORT ---
    port = int(os.environ.get("PORT", 8080))
    print(f"  Starting web server on port {port}...")
    app.run(host="0.0.0.0", port=port)
