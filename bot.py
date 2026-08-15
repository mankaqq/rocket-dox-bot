#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import urllib.parse
import json
import time
import datetime
import sqlite3
import os
import re
import socket
import hashlib
from flask import Flask, request, jsonify
from collections import defaultdict

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8905534019:AAFcWkZQsyq4147cFuYID5TuW65ssgmxmx4"
ADMIN_ID = 8171219348
PORT = int(os.environ.get("PORT", 5000))
DB_PATH = "phone_numbers.db"

# ==================== FLASK ====================
app = Flask(__name__)

# ==================== БАЗА ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ====================
def init_user_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        requests INTEGER DEFAULT 0,
        last_request TEXT,
        banned INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

init_user_db()

# ==================== ЛИМИТЫ ====================
def check_limit(chat_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT requests, last_request FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    today = datetime.date.today().isoformat()
    if row:
        requests, last = row
        if last != today:
            requests = 0
        if requests >= 5:
            conn.close()
            return False
        c.execute("UPDATE users SET requests = ?, last_request = ? WHERE chat_id = ?", (requests+1, today, chat_id))
    else:
        c.execute("INSERT INTO users (chat_id, requests, last_request) VALUES (?, 1, ?)", (chat_id, today))
    conn.commit()
    conn.close()
    return True

# ==================== МОДУЛИ ====================

# ---- BIN CHECKER ----
def bin_lookup(bin6):
    url = f"https://lookup.binlist.net/{bin6}"
    try:
        req = urllib.request.Request(url)
        req.add_header('Accept-Version', '3')
        response = urllib.request.urlopen(req, timeout=5)
        data = json.loads(response.read().decode())
        return {
            "scheme": data.get("scheme", "N/A"),
            "type": data.get("type", "N/A"),
            "brand": data.get("brand", "N/A"),
            "bank": data.get("bank", {}).get("name", "N/A"),
            "country": data.get("country", {}).get("name", "N/A")
        }
    except:
        return None

# ---- EMAIL VALID + HIBP ----
def check_email(email):
    # Валидация
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return {"valid": False, "breaches": []}
    # HIBP
    breaches = []
    try:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'ROCKET-DOX-Bot')
        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            breaches = [b["Name"] for b in data]
    except:
        pass
    return {"valid": True, "breaches": breaches}

# ---- USERNAME SEARCH ----
def search_username(username):
    sites = {
        "GitHub": f"https://github.com/{username}",
        "Instagram": f"https://instagram.com/{username}",
        "Twitter": f"https://twitter.com/{username}",
        "VK": f"https://vk.com/{username}",
        "Telegram": f"https://t.me/{username}",
        "YouTube": f"https://youtube.com/@{username}",
        "Reddit": f"https://reddit.com/user/{username}",
        "TikTok": f"https://tiktok.com/@{username}",
        "Discord": f"https://discord.com/users/{username}",
        "Twitch": f"https://twitch.tv/{username}",
        "Steam": f"https://steamcommunity.com/id/{username}",
        "Spotify": f"https://open.spotify.com/user/{username}",
        "SoundCloud": f"https://soundcloud.com/{username}",
        "Medium": f"https://medium.com/@{username}",
        "Quora": f"https://quora.com/profile/{username}",
        "GitLab": f"https://gitlab.com/{username}",
        "Pastebin": f"https://pastebin.com/u/{username}"
    }
    found = {}
    for site, url in sites.items():
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            response = urllib.request.urlopen(req, timeout=5)
            if response.getcode() == 200:
                found[site] = url
        except:
            pass
    return found

# ---- GEOIP ----
def geoip(ip):
    try:
        url = f"http://ip-api.com/json/{ip}"
        response = urllib.request.urlopen(url, timeout=5)
        data = json.loads(response.read().decode())
        if data.get("status") == "success":
            return {
                "country": data.get("country", "N/A"),
                "city": data.get("city", "N/A"),
                "region": data.get("regionName", "N/A"),
                "isp": data.get("isp", "N/A"),
                "lat": data.get("lat", 0),
                "lon": data.get("lon", 0)
            }
    except:
        pass
    return None

# ---- TELEGRAM OSINT ----
def telegram_osint(username):
    # Простая проверка существования канала/бота
    try:
        url = f"https://t.me/{username}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        response = urllib.request.urlopen(req, timeout=5)
        if response.getcode() == 200:
            return {"exists": True, "url": url}
    except:
        pass
    return {"exists": False}

# ---- DOX (ОПЕРАТОР, РЕГИОН) ----
def analyze_phone(phone):
    cleaned = ''.join(filter(str.isdigit, phone))
    result = {"country": "❌ Неизвестно", "operator": "❌ Неизвестно"}
    if cleaned.startswith('7') and len(cleaned) >= 11:
        result["country"] = "🇷🇺 Россия"
        codes = {
            "900": "МТС", "901": "МТС", "902": "МТС", "903": "МТС",
            "904": "МТС", "905": "МТС", "906": "МТС", "909": "МТС",
            "910": "МТС", "911": "МТС", "912": "МТС", "913": "МТС",
            "914": "МТС", "915": "МТС", "916": "МТС", "917": "МТС",
            "918": "МТС", "919": "МТС",
            "920": "МТС", "921": "МТС", "922": "МТС", "923": "МТС",
            "924": "МТС", "925": "МТС", "926": "МТС", "927": "МТС",
            "928": "МТС", "929": "МТС",
            "930": "Мегафон", "931": "Мегафон", "932": "Мегафон",
            "933": "Мегафон", "934": "Мегафон", "935": "Мегафон",
            "936": "Мегафон", "937": "Мегафон", "938": "Мегафон",
            "939": "Мегафон",
            "950": "Tele2", "951": "Tele2", "952": "Tele2",
            "953": "Tele2", "954": "Tele2", "955": "Tele2",
            "956": "Tele2", "958": "Tele2",
            "960": "Билайн", "961": "Билайн", "962": "Билайн",
            "963": "Билайн", "964": "Билайн", "965": "Билайн",
            "966": "Билайн", "967": "Билайн", "968": "Билайн",
            "969": "Билайн",
            "980": "Билайн", "981": "Билайн", "982": "Билайн",
            "983": "Билайн", "984": "Билайн", "985": "Билайн",
            "986": "Билайн", "987": "Билайн", "988": "Билайн",
            "989": "Билайн",
            "999": "Yota"
        }
        code = cleaned[1:4] if len(cleaned) >= 11 else cleaned[0:3]
        result["operator"] = codes.get(code, "❌ Неизвестно")
    elif cleaned.startswith('380') and len(cleaned) >= 12:
        result["country"] = "🇺🇦 Украина"
        codes = {
            "50": "Vodafone", "66": "Vodafone", "67": "Vodafone",
            "95": "Vodafone", "99": "Vodafone",
            "68": "Kyivstar", "96": "Kyivstar", "97": "Kyivstar",
            "98": "Kyivstar",
            "63": "lifecell", "73": "lifecell", "93": "lifecell"
        }
        code = cleaned[3:5] if len(cleaned) >= 12 else cleaned[0:2]
        result["operator"] = codes.get(code, "❌ Неизвестно")
    return result

# ---- ФОРМАТИРОВЩИК ОТВЕТА ----
def format_response(title, data):
    out = f"╔══════════════════════════════════╗\n"
    out += f"║  {title:<30} ║\n"
    out += f"╚══════════════════════════════════╝\n"
    for k, v in data.items():
        out += f"├ {k}: {v}\n"
    return out

# ==================== TELEGRAM API ====================
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    post_data = urllib.parse.urlencode(data).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=post_data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def get_keyboard():
    return {
        "keyboard": [
            [{"text": "🔍 DOX"}, {"text": "📧 EMAIL"}],
            [{"text": "👤 USERNAME"}, {"text": "💳 BIN"}],
            [{"text": "🌍 GEOIP"}, {"text": "📱 TG OSINT"}],
            [{"text": "ℹ️ ПОМОЩЬ"}, {"text": "💎 DONATE"}]
        ],
        "resize_keyboard": True
    }

# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================
def process_message(chat_id, text, first_name="Друг"):
    if not check_limit(chat_id):
        return "⚠️ Лимит 5 запросов в день. Попробуй завтра или задонать 💎"

    text = text.strip().lower()

    if text == "/start":
        return f"👋 Привет, {first_name}!\nВыбери команду на клавиатуре."

    if text in ["/help", "ℹ️ помощь", "помощь"]:
        return "🔍 DOX — оператор/регион\n📧 EMAIL — проверка утечек\n👤 USERNAME — поиск в соцсетях\n💳 BIN — банк по карте\n🌍 GEOIP — город/страна по IP\n📱 TG OSINT — проверка Telegram"

    if text == "💎 donate":
        return "💎 Поддержать проект:\nBTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\nUSDT TRC20: T..."

    # DOX
    if text == "🔍 dox":
        return "📱 Введи номер (пример: 79001234567)"

    # EMAIL
    if text == "📧 email":
        return "📧 Введи email (пример: test@mail.ru)"

    # USERNAME
    if text == "👤 username":
        return "👤 Введи username (пример: john_doe)"

    # BIN
    if text == "💳 bin":
        return "💳 Введи первые 6 цифр карты (пример: 411111)"

    # GEOIP
    if text == "🌍 geoip":
        return "🌍 Введи IP (пример: 8.8.8.8) или домен"

    # TG OSINT
    if text == "📱 tg osint":
        return "📱 Введи username Telegram (пример: durov)"

    # ---- ОБРАБОТКА ВВОДА ----
    # DOX
    if re.match(r'^[78]\d{10}$', text):
        phone = "+" + text if not text.startswith('+') else text
        info = analyze_phone(phone)
        return format_response("📱 DOX", {"Телефон": phone, "Оператор": info["operator"], "Страна": info["country"]})

    # EMAIL
    if re.match(r"[^@]+@[^@]+\.[^@]+", text):
        res = check_email(text)
        if res["valid"]:
            breaches = ", ".join(res["breaches"][:5]) if res["breaches"] else "✅ Не найден в утечках"
            return format_response("📧 EMAIL", {"Email": text, "Утечки": breaches})
        return "❌ Неверный email"

    # USERNAME
    if not re.search(r'[^a-zA-Z0-9_]', text) and len(text) > 2:
        found = search_username(text)
        if found:
            out = f"👤 {text} найден:\n"
            for site, url in found.items():
                out += f"├ {site}: {url}\n"
            return out
        return f"❌ {text} не найден"

    # BIN
    if re.match(r'^\d{6}$', text):
        bin_data = bin_lookup(text)
        if bin_data:
            return format_response("💳 BIN", {
                "Схема": bin_data["scheme"],
                "Тип": bin_data["type"],
                "Бренд": bin_data["brand"],
                "Банк": bin_data["bank"],
                "Страна": bin_data["country"]
            })
        return "❌ BIN не найден"

    # GEOIP
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text) or re.match(r'^[a-zA-Z0-9.-]+\.[a-z]{2,}$', text):
        ip = socket.gethostbyname(text) if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text) else text
        geo = geoip(ip)
        if geo:
            return format_response("🌍 GEOIP", {
                "IP": ip,
                "Страна": geo["country"],
                "Город": geo["city"],
                "Регион": geo["region"],
                "Провайдер": geo["isp"],
                "Координаты": f"{geo['lat']}, {geo['lon']}"
            })
        return "❌ IP не найден"

    # TG OSINT
    if text.startswith("@") or re.match(r'^[a-zA-Z0-9_]{3,}$', text):
        username = text.lstrip('@')
        res = telegram_osint(username)
        if res["exists"]:
            return f"📱 Telegram: @{username}\n✅ Аккаунт существует\n🔗 {res['url']}"
        return f"❌ @{username} не найден"

    return "❌ Неизвестная команда. Используй /help"

# ==================== FLASK ====================
@app.route('/')
def index():
    return "<h1>🚀 ROCKET DOX</h1><p>Бот работает 24/7</p>"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if data and 'message' in data:
            msg = data['message']
            chat_id = msg['chat']['id']
            text = msg.get('text', '')
            first_name = msg['from'].get('first_name', 'Друг')
            response = process_message(chat_id, text, first_name)
            send_message(chat_id, response)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "online"})

if __name__ == "__main__":
    print("🚀 ROCKET DOX — ВСЕ МОДУЛИ АКТИВИРОВАНЫ")
    app.run(host="0.0.0.0", port=PORT, debug=False)

