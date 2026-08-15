#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
import urllib.request
import urllib.parse
import json
import time
import datetime
import sqlite3
import os
import re

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8905534019:AAFcWkZQsyq4147cFuYID5TuW65ssgmxmx4"
ADMIN_ID = 8171219348
PORT = int(os.environ.get("PORT", 5000))
DB_PATH = "phone_numbers.db"

# ==================== СОЗДАЁМ FLASK ПРИЛОЖЕНИЕ ====================
app = Flask(__name__)

# ==================== БАЗА ДАННЫХ С ДОП. ИНФОРМАЦИЕЙ ====================
EXTRA_DATA = {
    "+79890840009": {
        "name": "Marlboro",
        "source": "арика, Ариэтта Владимировна Д., Ильгар Гурбанов",
        "social": {"Telegram": "#8673072764", "MAX": "Marlboro"},
        "banks": ["Озон Счёт Еком Банк", "Сбербанк"],
        "email": "rafael.arzumanyan@bk.ru"
    },
    "+79001234567": {
        "name": "Иванов Иван Петрович",
        "source": "арика, Ариэтта Владимировна Д.",
        "social": {"Telegram": "@ivan_ivanov", "MAX": "Marlboro"},
        "banks": ["Сбербанк", "Тинькофф", "Озон Счёт"],
        "email": "ivan.ivanov@example.com"
    },
}

# ==================== ФУНКЦИИ БОТА ====================

def analyze_phone(phone):
    """Определяет оператора и страну по номеру"""
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
            "999": "Yota",
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
            "63": "lifecell", "73": "lifecell", "93": "lifecell",
        }
        code = cleaned[3:5] if len(cleaned) >= 12 else cleaned[0:2]
        result["operator"] = codes.get(code, "❌ Неизвестно")
    
    return result

def format_dox_result(phone, operator, region, country, extra_data=None):
    """Форматирует DOX-результат в красивый вид"""
    result = "╔══════════════════════════════════╗\n"
    result += "║  📱 DOX РЕЗУЛЬТАТ                ║\n"
    result += "╚══════════════════════════════════╝\n\n"
    result += f"📱 ▸ Телефон: {phone}\n"
    result += f"▸ Оператор: {operator}\n"
    result += f"▸ Регион: {region}\n"
    result += f"▸ Страна: {country}\n"
    
    if extra_data:
        if extra_data.get('name'):
            result += f"\n👤 ФИО: {extra_data['name']}\n"
        if extra_data.get('source'):
            result += f"\n🔎 Телефонные книги: {extra_data['source']}\n"
        if extra_data.get('social'):
            result += "\n🟣 Соцсети:\n"
            for platform, handle in extra_data['social'].items():
                result += f"   ├ {platform}: {handle}\n"
        if extra_data.get('banks'):
            result += "\n🏦 Банки:\n"
            for bank in extra_data['banks']:
                result += f"   ├ {bank}\n"
        if extra_data.get('email'):
            result += f"\n📧 E-mail: {extra_data['email']}\n"
    
    result += "\n╔══════════════════════════════════╗\n"
    result += "║  💾 Данные из открытых источников ║\n"
    result += "╚══════════════════════════════════╝"
    return result

def process_dox(query):
    """Обрабатывает DOX-запрос"""
    cleaned = ''.join(filter(str.isdigit, query))
    if cleaned.startswith('7') and len(cleaned) >= 10:
        formatted = f"+{cleaned}" if len(cleaned) == 11 else f"+7{cleaned}"
        analysis = analyze_phone(formatted)
        extra = EXTRA_DATA.get(formatted)
        
        # Определяем регион (для демонстрации)
        region = "Москва" if formatted.startswith("+790") else "Краснодарский край"
        
        return format_dox_result(
            phone=formatted,
            operator=analysis.get('operator', 'Неизвестно'),
            region=region,
            country=analysis.get('country', '❌ Неизвестно'),
            extra_data=extra
        )
    else:
        return "❌ Неверный формат номера. Пример: 79001234567"

def send_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
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

def process_message(chat_id, text, first_name="Друг"):
    """Обрабатывает входящее сообщение"""
    if text == "/start":
        return f"👋 Привет, {first_name}!\n🚀 ROCKET DOX работает 24/7!\n📱 Отправь номер для DOX-поиска\n\nПример: 79001234567"
    
    elif text.startswith("/dox"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            return process_dox(parts[1].strip())
        else:
            return "🔍 /dox 79001234567"
    
    else:
        # Проверяем, может быть это номер
        cleaned = ''.join(filter(str.isdigit, text))
        if cleaned.startswith('7') and len(cleaned) >= 10:
            return process_dox(text)
        else:
            return f"💬 Ты написал: {text}\n📖 Отправь /start для помощи"

# ==================== FLASK МАРШРУТЫ ====================

@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>🚀 ROCKET DOX BOT</title>
        <style>
            body { background: #0a0a0f; color: #00ff41; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; }
            h1 { font-size: 48px; text-shadow: 0 0 40px rgba(0,255,65,0.3); }
            .status { color: #00ff41; animation: blink 1s infinite; }
            @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
            .info { color: #e0e0e0; font-size: 14px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>🚀 ROCKET DOX</h1>
        <div class="status">🟢 SYSTEM ONLINE</div>
        <div class="info">⚡ Бот работает 24/7 на хостинге</div>
        <div class="info">📱 Отправь номер в Telegram</div>
    </body>
    </html>
    """

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
    return jsonify({"status": "online", "time": datetime.datetime.now().isoformat()})

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("=" * 40)
    print("🚀 ROCKET DOX БОТ ЗАПУЩЕН!")
    print("=" * 40)
    print(f"🌐 Сервер на порту: {PORT}")
    print(f"🔗 Открой в браузере: http://localhost:{PORT}")
    print("=" * 40)
    app.run(host="0.0.0.0", port=PORT, debug=False)

