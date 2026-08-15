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
from flask import Flask, request, jsonify

TOKEN = "8905534019:AAFcWkZQsyq4147cFuYID5TuW65ssgmxmx4"
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)

# ===== БАЗА ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ =====
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        requests INTEGER DEFAULT 0,
        last_request TEXT
    )''')
    conn.commit()
    conn.close()
init_db()

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

# ===== ОПРЕДЕЛЕНИЕ ОПЕРАТОРА =====
def get_operator(phone):
    cleaned = ''.join(filter(str.isdigit, phone))
    if not cleaned.startswith('7') or len(cleaned) < 11:
        return "❌ Неверный номер"
    
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
    code = cleaned[1:4]
    return codes.get(code, "❌ Неизвестно")

# ===== ПРОВЕРКА EMAIL =====
def check_email(email):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "❌ Неверный email"
    breaches = []
    try:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'ROCKET-Bot')
        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            breaches = [b["Name"] for b in data]
    except:
        pass
    if breaches:
        return f"✅ Найден в утечках: {', '.join(breaches[:3])}"
    return "✅ Не найден в утечках"

# ===== ПОИСК USERNAME =====
def search_username(username):
    sites = {
        "GitHub": f"https://github.com/{username}",
        "Instagram": f"https://instagram.com/{username}",
        "Twitter": f"https://twitter.com/{username}",
        "VK": f"https://vk.com/{username}",
        "Telegram": f"https://t.me/{username}",
        "YouTube": f"https://youtube.com/@{username}"
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

# ===== BIN CHECKER =====
def bin_lookup(bin6):
    try:
        url = f"https://lookup.binlist.net/{bin6}"
        req = urllib.request.Request(url)
        req.add_header('Accept-Version', '3')
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
        return {
            "Банк": data.get("bank", {}).get("name", "N/A"),
            "Страна": data.get("country", {}).get("name", "N/A"),
            "Тип": data.get("type", "N/A"),
            "Бренд": data.get("brand", "N/A")
        }
    except:
        return None

# ===== GEOIP =====
def geoip(ip):
    try:
        url = f"http://ip-api.com/json/{ip}"
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read().decode())
        if data.get("status") == "success":
            return {
                "Страна": data.get("country", "N/A"),
                "Город": data.get("city", "N/A"),
                "Провайдер": data.get("isp", "N/A")
            }
    except:
        pass
    return None

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def process_message(text, first_name="Друг"):
    text = text.strip()
    
    if text == "/start":
        return f"👋 Привет, {first_name}!\nОтправь номер, email, username или используй команды:\n/dox номер\n/email email\n/user username\n/bin 6 цифр\n/ip адрес"
    
    if text.startswith("/dox"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            phone = parts[1].strip()
            operator = get_operator(phone)
            return f"📱 Номер: {phone}\n📊 Оператор: {operator}\n🇷🇺 Страна: Россия"
        return "📱 Пример: /dox 79001234567"
    
    if text.startswith("/email"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            return check_email(parts[1].strip())
        return "📧 Пример: /email test@mail.ru"
    
    if text.startswith("/user"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            found = search_username(parts[1].strip())
            if found:
                result = f"👤 {parts[1]} найден:\n"
                for site, url in found.items():
                    result += f"├ {site}: {url}\n"
                return result
            return f"❌ {parts[1]} не найден"
        return "👤 Пример: /user john_doe"
    
    if text.startswith("/bin"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and len(parts[1]) == 6 and parts[1].isdigit():
            data = bin_lookup(parts[1])
            if data:
                return f"💳 BIN: {parts[1]}\n🏦 Банк: {data['Банк']}\n🌍 Страна: {data['Страна']}\n📌 Тип: {data['Тип']}\n🏷️ Бренд: {data['Бренд']}"
            return "❌ BIN не найден"
        return "💳 Пример: /bin 411111"
    
    if text.startswith("/ip"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            ip = parts[1].strip()
            if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
                data = geoip(ip)
                if data:
                    return f"🌍 IP: {ip}\n📍 Страна: {data['Страна']}\n🏙️ Город: {data['Город']}\n📡 Провайдер: {data['Провайдер']}"
            return "❌ Неверный IP"
        return "🌍 Пример: /ip 8.8.8.8"
    
    # Если просто номер
    if re.match(r'^[78]\d{10}$', text):
        operator = get_operator(text)
        return f"📱 Номер: {text}\n📊 Оператор: {operator}\n🇷🇺 Страна: Россия"
    
    # Если просто email
    if re.match(r"[^@]+@[^@]+\.[^@]+", text):
        return check_email(text)
    
    # Если просто username
    if re.match(r'^[a-zA-Z0-9_]{3,20}$', text):
        found = search_username(text)
        if found:
            result = f"👤 {text} найден:\n"
            for site, url in found.items():
                result += f"├ {site}: {url}\n"
            return result
        return f"❌ {text} не найден"
    
    # Если просто BIN
    if re.match(r'^\d{6}$', text):
        data = bin_lookup(text)
        if data:
            return f"💳 BIN: {text}\n🏦 Банк: {data['Банк']}\n🌍 Страна: {data['Страна']}\n📌 Тип: {data['Тип']}\n🏷️ Бренд: {data['Бренд']}"
        return "❌ BIN не найден"
    
    return "❌ Неизвестная команда. Используй /start"

# ===== TELEGRAM API =====
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    post_data = urllib.parse.urlencode(data).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=post_data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

# ===== POLLING =====
def get_updates(offset=0):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 30}
    try:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
        response = urllib.request.urlopen(req, timeout=35)
        data = json.loads(response.read().decode('utf-8'))
        return data.get("result", []) if data.get("ok") else []
    except Exception as e:
        print(f"Ошибка получения: {e}")
        return []

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("=" * 40)
    print("🚀 ROCKET DOX ЗАПУЩЕН!")
    print("🤖 Бот работает в режиме POLLING")
    print("=" * 40)
    
    last_update_id = 0
    while True:
        try:
            updates = get_updates(last_update_id + 1)
            for update in updates:
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    first_name = msg["from"].get("first_name", "Друг")
                    
                    # Проверка лимита
                    if not check_limit(chat_id):
                        send_message(chat_id, "⚠️ Лимит 5 запросов в день. Попробуй завтра!")
                        continue
                    
                    response = process_message(text, first_name)
                    send_message(chat_id, response)
                    
                last_update_id = update["update_id"]
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        time.sleep(1)

