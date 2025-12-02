import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TEXTRU_API_KEY = os.getenv("TEXTRU_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class EssayStates(StatesGroup):
    waiting_for_structure = State()
    waiting_for_text_to_check = State()

async def generate_essay_from_structure(structure: str) -> str:
    if not OPENAI_API_KEY:
        return "OpenAI API key is not configured. Set OPENAI_API_KEY environment variable."

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    system_prompt = (
        "Ты — ассистент, который пишет итоговые сочинения строго по заданной структуре. "
        "Следуй структуре, выделяй абзацы и пиши связный, академичный стиль."
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": structure},
        ],
        "temperature": 0.6,
        "max_tokens": 1200,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
            if resp.status != 200:
                txt = await resp.text()
                return f"OpenAI API error {resp.status}: {txt}"
            data = await resp.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except Exception:
                return "Ошибка обработки ответа OpenAI."

async def check_plagiarism_textru(text: str) -> str:
    if not TEXTRU_API_KEY:
        return "TEXTRU API key not configured. Set TEXTRU_API_KEY env variable."

    api_url = "https://api.text.ru/post"
    data = {"text": text, "userkey": TEXTRU_API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, data=data, timeout=60) as resp:
            if resp.status != 200:
                return f"Text.ru API error {resp.status}: {await resp.text()}"
            try:
                result = await resp.json()
                return str(result)
            except Exception:
                return await resp.text()

main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Сгенерировать сочинение", callback_data="generate")],
    [InlineKeyboardButton(text="Проверить текст на плагиат", callback_data="check")],
    [InlineKeyboardButton(text="Помощь", callback_data="help")],
])

@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для генерации итоговых сочинений и проверки уникальности.
Выбери действие:",
        reply_markup=main_kb,
    )

@dp.callback_query(F.data == "help")
async def cb_help(query: types.CallbackQuery):
    await query.message.answer(
        "Инструкция:

"
        "— Нажми 'Сгенерировать сочинение', затем отправь структуру.
"
        "— Получишь готовое сочинение.
"
        "— Можно проверить текст на плагиат через меню."
    )
    await query.answer()

@dp.callback_query(F.data == "generate")
async def cb_generate(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer(
        "Отправь структуру сочинения или тезисы."
    )
    await state.set_state(EssayStates.waiting_for_structure)
    await query.answer()

@dp.message(EssayStates.waiting_for_structure)
async def process_structure(message: types.Message, state: FSMContext):
    structure = message.text.strip()
    await message.answer("Генерирую сочинение...")
    essay = await generate_essay_from_structure(structure)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить это сочинение на плагиат", callback_data="check_text")],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu")],
    ])
    await message.answer(f"Готовое сочинение:

{essay}", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "menu")
async def cb_menu(query: types.CallbackQuery):
    await query.message.answer("Главное меню:", reply_markup=main_kb)
    await query.answer()

@dp.callback_query(F.data == "check")
async def cb_check(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer("Отправь текст для проверки.")
    await state.set_state(EssayStates.waiting_for_text_to_check)
    await query.answer()

@dp.message(EssayStates.waiting_for_text_to_check)
async def process_text_to_check(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await message.answer("Проверяю...")
    result = await check_plagiarism_textru(text)
    await message.answer(f"Результат проверки:
{result}")
    await state.clear()

@dp.callback_query(F.data == "check_text")
async def cb_check_text(query: types.CallbackQuery):
    await query.message.answer("Отправь текст, который нужно проверить.")
    await query.answer()

async def main():
    try:
        print("Bot is starting...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
