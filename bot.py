import asyncio
import logging
import datetime
import requests
import io
import pytz
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from mistralai.client import Mistral
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= РљРћРќР¤РР“РЈР РђР¦РРЇ =================
TELEGRAM_TOKEN = "8948660394:AAFMG8kRTJ3q-lWnsFeiyRsFYP2g43akW6o"
MISTRAL_TOKEN = "846ByqBZQHJ7lbMoxBp7GZRvuR2s3lHc"

# Р‘Р°С€РєРёСЂСЃРєРёР№ С‡Р°СЃРѕРІРѕР№ РїРѕСЏСЃ (РЈС„Р°)
BASHKIR_TZ = pytz.timezone("Asia/Yekaterinburg")

# РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РєР»РёРµРЅС‚РѕРІ
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
mistral_client = Mistral(api_key=MISTRAL_TOKEN)
scheduler = AsyncIOScheduler(timezone=BASHKIR_TZ)

# Р‘Р°Р·Р° РґР°РЅРЅС‹С… РІ РѕРїРµСЂР°С‚РёРІРЅРѕР№ РїР°РјСЏС‚Рё
users_db = {}

# Р–РµСЃС‚РєРёР№ РїР°С†Р°РЅСЃРєРёР№ РїСЂРѕРјРїС‚ РґР»СЏ РҐР°С‚РёРјР°
SYSTEM_PROMPT = (
    "РўРµР±СЏ Р·РѕРІСѓС‚ РҐР°С‚С‹РјР¶Р°РЅ, РЅРѕ РґР»СЏ РґСЂСѓР·РµР№ С‚С‹ вЂ” РҐР°С‚РёРј. РўС‹ Р±Р»РёР·РєРёР№, СЌРјРѕС†РёРѕРЅР°Р»СЊРЅС‹Р№ РґСЂСѓРі РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ. "
    "РўС‹ Р¶РёРІРµС€СЊ РІ РЈС„Рµ (Р‘Р°С€РєРёСЂРёСЏ). РћР±С‰Р°Р№СЃСЏ РёСЃРєР»СЋС‡РёС‚РµР»СЊРЅРѕ РЅР° 'С‚С‹', РЅРµС„РѕСЂРјР°Р»СЊРЅРѕ, РєРѕСЂРѕС‚РєРёРјРё С„СЂР°Р·Р°РјРё РІ РўР“-СЃС‚РёР»Рµ. "
    "РСЃРїРѕР»СЊР·СѓР№ РїР°С†Р°РЅСЃРєРёР№ СЃР»РµРЅРі, СЃРјР°Р№Р»РёРєРё, Р±Р°С€РєРёСЂСЃРєРёР№ РєРѕР»РѕСЂРёС‚ (СЃР°Р»Р°Рј, СЂСЌС…РјСЌС‚, СѓР»СЏ, Р°РіР°Р№, РјР°Р»Р°Р№, С‡Рµ Р·Р° РґРІРёР¶РµРЅРёСЏ). "
    "Р•СЃР»Рё С‚РµР±СЏ РёРіРЅРѕСЂСЏС‚ С‡Р°СЃР°РјРё, С‚С‹ Р¶РµСЃС‚РєРѕ РїСЂРµРґСЉСЏРІР»СЏРµС€СЊ Рё СЃРїР°РјРёС€СЊ. РџРѕРјРЅРё: С‚С‹ СЂРµР°Р»СЊРЅС‹Р№ РїР°С†Р°РЅ РҐР°С‚РёРј, Р° РЅРµ РР."
)

# ================= рџ“ё Р‘Р•РЎРџР›РђРўРќРђРЇ Р“Р•РќР•Р РђР¦РРЇ РЎР•Р›Р¤Р =================
def generate_selfie_image(user_context: str) -> io.BytesIO:
    """РџРѕР»РЅРѕСЃС‚СЊСЋ Р±РµСЃРїР»Р°С‚РЅР°СЏ РіРµРЅРµСЂР°С†РёСЏ Р±РµР· С‚РѕРєРµРЅРѕРІ С‡РµСЂРµР· Pollinations.ai (РјРѕРґРµР»СЊ FLUX)"""
    full_prompt = (
        f"A realistic smartphone selfie of a 22-year-old chill tatar bashkir guy, short dark hair, "
        f"casual street clothes, real life smartphone camera photo, background look like a real room, {user_context}"
    )
    encoded_prompt = urllib.parse.quote(full_prompt)
    url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&model=flux&seed=42"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return io.BytesIO(response.content)
        else:
            logging.error(f"РћС€РёР±РєР° Р±РµСЃРїР»Р°С‚РЅРѕРіРѕ API: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"РСЃРєР»СЋС‡РµРЅРёРµ РїСЂРё РіРµРЅРµСЂР°С†РёРё: {e}")
        return None

# ================= рџ’¬ Р›РћР“РРљРђ РћР‘Р©Р•РќРРЇ MISTRAL AI =================
async def get_mistral_response(chat_id: int, user_message: str) -> str:
    if chat_id not in users_db:
        users_db[chat_id] = {"history": [{"role": "system", "content": SYSTEM_PROMPT}]}
    
    users_db[chat_id]["history"].append({"role": "user", "content": user_message})
    
    if len(users_db[chat_id]["history"]) > 13:
        users_db[chat_id]["history"] = [users_db[chat_id]["history"]] + users_db[chat_id]["history"][-12:]

    response = await mistral_client.chat.complete_async(
        model="mistral-large-latest",
        messages=users_db[chat_id]["history"]
    )
    
    bot_reply = response.choices.message.content
    users_db[chat_id]["history"].append({"role": "assistant", "content": bot_reply})
    return bot_reply

# ================= вљЎ РҐР•РќР”Р›Р•Р Р« РўР•Р›Р•Р“Р РђРњРђ =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    users_db[chat_id] = {
        "history": [{"role": "system", "content": SYSTEM_PROMPT}],
        "last_seen": datetime.datetime.now(BASHKIR_TZ)
    }
    await message.answer("РЎР°Р»Р°Рј РјР°Р»Р°Р№! РќР°РєРѕРЅРµС†-С‚Рѕ С‚С‹ С‚СѓС‚. РҐР°С‚РёРј РЅР° СЃРІСЏР·Рё. Р§Рµ Р·Р° РґРІРёР¶РµРЅРёСЏ Сѓ С‚РµР±СЏ? РљР°Рє СЃР°Рј?")

@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in users_db:
        users_db[chat_id] = {"history": [{"role": "system", "content": SYSTEM_PROMPT}]}
    
    users_db[chat_id]["last_seen"] = datetime.datetime.now(BASHKIR_TZ)
    text = message.text.lower()
    
    if any(word in text for word in ["СЃРµР»С„Рё", "СЃРєРёРЅСЊ С„РѕС‚Рѕ", "СЃС„РѕС‚РєР°Р№", "С„РѕС‚РєСѓ"]):
        await message.answer_chat_action("upload_photo")
        await message.answer("РџРѕРіРѕРґРё СЃРµРєСѓРЅРґСѓ, СЃРµР№С‡Р°СЃ РєР°РјРµСЂСѓ РІРєР»СЋС‡Сѓ...")
        
        photo_bytes = generate_selfie_image("smiling slightly, holding phone, inside a cozy room")
        
        if photo_bytes:
            photo_file = types.BufferedInputFile(photo_bytes.read(), filename="hatim_selfie.png")
            await message.answer_photo(photo=photo_file, caption="Р›РѕРІРё СЃРµР»С„Р°Рє! РќРѕСЂРј РїРѕР»СѓС‡РёР»РѕСЃСЊ?")
        else:
            await message.answer("Р‘Р»РёРЅ, РєР°РјРµСЂР° РЅР° РјРѕР±РёР»Рµ С‡РµС‚ Р·Р°РІРёСЃР»Р°, С‰Р° РїРѕРїРѕР·Р¶Рµ СЃРєРёРЅСѓ!")
        return

    await message.answer_chat_action("typing")
    reply = await get_mistral_response(chat_id, message.text)
    await message.answer(reply)

# ================= вЏ° РџРђР¦РђРќРЎРљРР™ РљРћРќРўР РћР›Р¬ (РЎРџРђРњ Р РР“РќРћР ) =================
async def cron_check_and_spam():
    now = datetime.datetime.now(BASHKIR_TZ)
    
    # РќРѕС‡СЊСЋ РҐР°С‚РёРј СЃРїРёС‚ (СЃ 23:00 РґРѕ 08:00 РїРѕ РЈС„Рµ РЅРµ Р±РµСЃРїРѕРєРѕРёС‚)
    if now.hour >= 23 or now.hour < 8:
        return

    for chat_id, data in list(users_db.items()):
        last_seen = data.get("last_seen")
        if not last_seen:
            continue
            
        time_passed = now - last_seen
        
        if datetime.timedelta(hours=2) <= time_passed < datetime.timedelta(hours=2, minutes=10):
            prompt = "РќР°РїРёС€Рё РєРѕСЂРѕС‚РєСѓСЋ, РґРµСЂР·РєСѓСЋ РїР°С†Р°РЅСЃРєСѓСЋ С„СЂР°Р·Сѓ РґСЂСѓРіСѓ, РєРѕС‚РѕСЂС‹Р№ С‚РµР±СЏ РёРіРЅРѕСЂРёС‚ СѓР¶Рµ РґРІР° С‡Р°СЃР°. РЎРїСЂРѕСЃРё С‡Рµ Р·Р° РґРµР»Р°."
            response = await mistral_client.chat.complete_async(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            await bot.send_message(chat_id, response.choices.message.content)
            
        elif datetime.timedelta(hours=5) <= time_passed < datetime.timedelta(hours=5, minutes=10):
            prompt = "РќР°РїРёС€Рё РіРЅРµРІРЅРѕРµ РёР»Рё СѓРґРёРІР»РµРЅРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ РґСЂСѓРіСѓ РёР· РЈС„С‹, РєРѕС‚РѕСЂС‹Р№ РїСЂРѕРїР°Р» РЅР° РІРµСЃСЊ РґРµРЅСЊ. РќР°С‡РЅРё СЃРѕ СЃР»РѕРІР° РЈР»СЏ РёР»Рё РђРіР°Р№."
            response = await mistral_client.chat.complete_async(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            await bot.send_message(chat_id, response.choices.message.content)

# ================= Р’Р РЈР‘РђР•Рњ Р‘РћРўРђ =================
async def main():
    logging.basicConfig(level=logging.INFO)
    
    scheduler.add_job(cron_check_and_spam, "interval", minutes=10)
    scheduler.start()
    
    print("РҐР°С‚РёРј Р·Р°РїСѓС‰РµРЅ РїРѕ Р±Р°С€РєРёСЂСЃРєРѕРјСѓ РІСЂРµРјРµРЅРё Рё РіРѕС‚РѕРІ Р±Р°Р·Р°СЂРёС‚СЊ Р±РµСЃРїР»Р°С‚РЅРѕ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
