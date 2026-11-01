import asyncio
import sqlite3
import re
import os
from datetime import datetime
from collections import Counter
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton

# Токен будет браться из настроек Railway (переменная TELEGRAM_BOT_TOKEN)
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Настройка базы данных
conn = sqlite3.connect('roulette.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number INTEGER,
        color TEXT,
        time TEXT
    )
''')
conn.commit()

# --- КЛАВИАТУРА С КНОПКАМИ ---
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📜 Последние")],
        [KeyboardButton(text="🔥 Серия"), KeyboardButton(text="🧮 Анализ")]
    ],
    resize_keyboard=True
)

async def start_handler(message: types.Message):
    await message.answer(
        "Бот-аналитик запущен!\n\nТеперь можешь пользоваться кнопками внизу экрана 👇",
        reply_markup=keyboard
    )

async def stats_handler(message: types.Message):
    cursor.execute("SELECT color, COUNT(*) FROM history GROUP BY color")
    stats = cursor.fetchall()
    text = "📊 Статистика цветов:\n"
    for color, count in stats:
        text += f"{color}: {count} раз\n"
    if not stats:
        text = "Пока нет данных."
    await message.answer(text)

async def last_handler(message: types.Message):
    cursor.execute("SELECT number, color FROM history ORDER BY id DESC LIMIT 15")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("База пуста.")
        return
    text = "📜 Последние 15 раундов:\n"
    for number, color in reversed(rows):
        emoji = "🔴" if color == "Красное" else ("⚫" if color == "Черное" else "🟢")
        text += f"{number} {emoji}\n"
    await message.answer(text)

async def streak_handler(message: types.Message):
    cursor.execute("SELECT color FROM history ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("База пуста.")
        return
    last_color = rows[0][0]
    streak_count = 0
    for row in rows:
        if row[0] == last_color:
            streak_count += 1
        else:
            break
    emoji = "🔴" if last_color == "Красное" else ("⚫" if last_color == "Черное" else "🟢")
    await message.answer(f"🔥 Текущая серия: {streak_count} раз подряд выпало {last_color} {emoji}")

async def analysis_handler(message: types.Message):
    cursor.execute("SELECT number, color FROM history")
    all_data = cursor.fetchall()
    
    if not all_data:
        await message.answer("База пуста.")
        return
        
    total_rounds = len(all_data)
    colors = [row[1] for row in all_data]
    red_count = colors.count("Красное")
    black_count = colors.count("Черное")
    green_count = colors.count("Зеленое")
    
    d1 = sum(1 for row in all_data if 1 <= row[0] <= 12)
    d2 = sum(1 for row in all_data if 13 <= row[0] <= 24)
    d3 = sum(1 for row in all_data if 25 <= row[0] <= 36)
    zero = sum(1 for row in all_data if row[0] == 0)
    
    number_counts = Counter([row[0] for row in all_data if row[0] != 0])
    most_common = number_counts.most_common(5)
    
    all_numbers = set(range(1, 37))
    dropped_numbers = set(number_counts.keys())
    never_dropped = list(all_numbers - dropped_numbers)
    
    text = f"🧮 АНАЛИЗ БАЗЫ (Всего бросков: {total_rounds})\n\n"
    text += "🎨 Цвета:\n"
    text += f"🔴 Красное: {red_count}\n"
    text += f"⚫ Черное: {black_count}\n"
    if green_count > 0: text += f"🟢 Зеро: {green_count}\n"
    
    text += "\n📦 Дюжины (диапазоны):\n"
    text += f"1-12: {d1} раз\n"
    text += f"13-24: {d2} раз\n"
    text += f"25-36: {d3} раз\n"
    if zero > 0: text += f"Зеро: {zero} раз\n"
    
    text += "\n🔥 Самые частые числа:\n"
    if most_common:
        for num, count in most_common:
            text += f"Число {num}: {count} раз\n"
    else:
        text += "Пока нет данных\n"
        
    text += "\n🧊 Числа, которые еще НЕ выпадали:\n"
    if never_dropped:
        text += ", ".join(map(str, never_dropped[:10]))
        if len(never_dropped) > 10:
            text += " и др."
        text += "\n"
    else:
        text += "Все числа уже выпадали!\n"
        
    text += "\n⚠️ Это статистика прошлого. Рулетка не имеет памяти!"
    await message.answer(text)

async def undo_handler(message: types.Message):
    cursor.execute("SELECT id, number, color FROM history ORDER BY id DESC LIMIT 1")
    last_entry = cursor.fetchone()
    if not last_entry:
        await message.answer("База пуста, нечего удалять.")
        return
    cursor.execute("DELETE FROM history WHERE id = ?", (last_entry[0],))
    conn.commit()
    await message.answer(f"🗑 Удалена последняя запись: {last_entry[1]} ({last_entry[2]})")

async def clear_handler(message: types.Message):
    cursor.execute("DELETE FROM history")
    conn.commit()
    await message.answer("🧹 База данных полностью очищена!")

async def all_messages_handler(message: types.Message):
    if message.text == "📊 Статистика":
        await stats_handler(message)
        return
    elif message.text == "📜 Последние":
        await last_handler(message)
        return
    elif message.text == "🔥 Серия":
        await streak_handler(message)
        return
    elif message.text == "🧮 Анализ":
        await analysis_handler(message)
        return

    if message.from_user.is_bot:
        text = message.text or message.caption or ""
        match = re.search(r'Рулетка:\s*(\d+)\s*([🔴⚫🟢])', text)
        
        if match:
            number = int(match.group(1))
            emoji = match.group(2)
            
            if emoji == '🔴': color = 'Красное'
            elif emoji == '⚫': color = 'Черное'
            else: color = 'Зеленое'
                
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO history (number, color, time) VALUES (?, ?, ?)", (number, color, now))
            conn.commit()
            
            await message.reply(f"✅ Записано: {number} ({color})")

async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="stats", description="Статистика цветов"),
        BotCommand(command="last", description="Последние 15 раундов"),
        BotCommand(command="streak", description="Текущая серия"),
        BotCommand(command="analysis", description="Анализ диапазонов и чисел"),
        BotCommand(command="undo", description="Удалить последнюю запись"),
        BotCommand(command="clear", description="Очистить базу")
    ]
    await bot.set_my_commands(commands)
    
    dp.message.register(start_handler, Command("start"))
    dp.message.register(stats_handler, Command("stats"))
    dp.message.register(last_handler, Command("last"))
    dp.message.register(streak_handler, Command("streak"))
    dp.message.register(analysis_handler, Command("analysis"))
    dp.message.register(undo_handler, Command("undo"))
    dp.message.register(clear_handler, Command("clear"))
    dp.message.register(all_messages_handler)
    
    print("Бот-аналитик запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
