# bot.py
# Requirements: aiogram, asyncpg, aiohttp
# pip install aiogram asyncpg aiohttp python-dotenv

import os
import logging
from datetime import datetime, date
import asyncio
import json

from aiogram import Bot, Dispatcher, types, executor

# ---------------------------
# CONFIG (you provided values)
# ---------------------------
# NOTE: for production prefer reading from env vars or .env
BOT_TOKEN = "8456427902:AAFyU1cHLQtsc15zEUmXrWqvEdybjPETi20"
ADMIN_TELEGRAM_ID = 8193138896  # numeric
BOT_USERNAME = "tomato_earn_bot"

# Monetag / Webapp base (change to your domain)
WEBAPP_BASE = os.getenv("WEBAPP_BASE", "http://localhost:5000")

# Runtime settings (can be env vars)
REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "25"))   # per referral
AD_REWARD = float(os.getenv("AD_REWARD", "5"))               # per ad view
DAILY_AD_LIMIT = int(os.getenv("DAILY_AD_LIMIT", "10"))
MIN_WITHDRAWAL_AMOUNT = float(os.getenv("MIN_WITHDRAWAL_AMOUNT", "1000"))
MIN_REFERRALS_FOR_WITHDRAWAL = int(os.getenv("MIN_REFERRALS_FOR_WITHDRAWAL", "20"))

# Postgres DSN - change before running
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/tomato_db")

# ---------------------------
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Use asyncpg directly for simplicity
import asyncpg
pool = None

async def db_connect():
    return await asyncpg.create_pool(DATABASE_URL)

# Helpers
async def ensure_user(conn, user: types.User):
    uid = user.id
    row = await conn.fetchrow("SELECT id FROM users WHERE id=$1", uid)
    if not row:
        await conn.execute("""
            INSERT INTO users(id, username, first_name, last_name, created_at)
            VALUES($1,$2,$3,$4,$5)
        """, uid, user.username, user.first_name, user.last_name, datetime.utcnow())
    return uid

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()  # referral param if any
    user = message.from_user
    async with pool.acquire() as conn:
        await ensure_user(conn, user)
        # handle referral if present and valid integer
        if args:
            try:
                ref_id = int(args)
                if ref_id != user.id:
                    # check if referrer exists
                    ref_exists = await conn.fetchrow("SELECT id FROM users WHERE id=$1", ref_id)
                    if ref_exists:
                        # credit the referrer
                        await conn.execute("""
                            UPDATE users SET balance = balance + $1, referrals_count = referrals_count + 1, total_earned = total_earned + $1 WHERE id=$2
                        """, REFERRAL_REWARD, ref_id)
                        await conn.execute("""
                            INSERT INTO referrals(referrer_id, referred_id, reward_amount, created_at) VALUES($1,$2,$3,$4)
                        """, ref_id, user.id, REFERRAL_REWARD, datetime.utcnow())
                        await message.reply(f"আপনার রেফারারকে {REFERRAL_REWARD} টাকা ক্রেডিট করা হয়েছে।")
            except Exception as e:
                logging.exception("ref parse error: %s", e)

        # reply with welcome and referral link
        me = await bot.get_me()
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
        await message.reply(f"স্বাগতম {user.first_name}!\nআপনার রেফারেল লিংক:\n{ref_link}\n\nCommands:\n/balance\n/tasks\n/ads\n/withdraw\n/referrals")

@dp.message_handler(commands=['balance'])
async def cmd_balance(message: types.Message):
    uid = message.from_user.id
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance, pending_balance, total_earned FROM users WHERE id=$1", uid)
        if not row:
            await message.reply("রেজিস্টার করতে /start চালান।")
            return
        await message.reply(f"Available: {row['balance']} টাকা\nPending: {row['pending_balance']} টাকা\nTotal Earned: {row['total_earned']} টাকা")

@dp.message_handler(commands=['referrals'])
async def cmd_referrals(message: types.Message):
    uid = message.from_user.id
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT referrals_count FROM users WHERE id=$1", uid)
        if not row:
            await message.reply("রেজিস্টার করুন /start")
            return
        await message.reply(f"আপনার মোট রেফারাল: {row['referrals_count']}")

@dp.message_handler(commands=['tasks'])
async def cmd_tasks(message: types.Message):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, reward FROM tasks WHERE active=TRUE ORDER BY id")
        if not rows:
            await message.reply("কোন টাস্ক নেই।")
            return
        for r in rows:
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Claim (send proof)", callback_data=f"claim_task:{r['id']}")
            )
            await message.answer(f"{r['name']}\nReward: {r['reward']} টাকা", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("claim_task:"))
async def cb_claim_task(callback: types.CallbackQuery):
    _, task_id = callback.data.split(":")
    user_id = callback.from_user.id
    async with pool.acquire() as conn:
        # insert pending completion; admin will verify via admin panel
        await conn.execute("""
            INSERT INTO task_completions(user_id, task_id, status, proof, reward, created_at)
            VALUES($1,$2,$3,$4,$5,$6)
        """, user_id, int(task_id), 'pending', None, 0, datetime.utcnow())
    await bot.answer_callback_query(callback.id, "টাস্ক ক্লেইম করা হয়েছে — অ্যাডমিন যাচাই করবেন।")

@dp.message_handler(commands=['ads'])
async def cmd_ads(message: types.Message):
    uid = message.from_user.id
    today = date.today()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(1) FROM ads_viewed WHERE user_id=$1 AND viewed_at::date = $2", uid, today)
    remain = max(0, DAILY_AD_LIMIT - (count or 0))
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Watch Ad", url=f"{WEBAPP_BASE}/watch_ad?user_id={uid}")
    )
    await message.reply(f"আজকের বাকি Ads: {remain}\nপ্রতি অ্যাডে {AD_REWARD} টাকা পেয়ে যাবেন।", reply_markup=kb)

@dp.message_handler(commands=['withdraw'])
async def cmd_withdraw(message: types.Message):
    uid = message.from_user.id
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance, referrals_count FROM users WHERE id=$1", uid)
        if not row:
            await message.reply("রেজিস্টার করুন /start")
            return
        if row['balance'] < MIN_WITHDRAWAL_AMOUNT:
            await message.reply(f"নূন্যতম উত্তোলন মানি {MIN_WITHDRAWAL_AMOUNT} টাকা লাগবে। আপনার ব্যালেন্স {row['balance']}।")
            return
        if row['referrals_count'] < MIN_REFERRALS_FOR_WITHDRAWAL:
            await message.reply(f"উত্তোলনের জন্য ন্যূনতম রেফারাল প্রয়োজন: {MIN_REFERRALS_FOR_WITHDRAWAL}। আপনি: {row['referrals_count']}")
            return
        # ask user for bkash number as plain message: handle with next message handler
        await message.reply("উত্তোলনের জন্য আপনার bKash নম্বর লিখুন (উদাহরণ: 01XXXXXXXXX)।")
        # set per-user state by storing a pending withdrawal request record with account_info null and status 'awaiting_account'
        await conn.execute("INSERT INTO withdrawals(user_id, amount, method, account_info, status, created_at) VALUES($1,$2,$3,$4,$5,$6)",
                           uid, row['balance'], 'bkash', None, 'awaiting_account', datetime.utcnow())
        # do not deduct balance yet; admin will approve and then you (admin) will call payout.

@dp.message_handler()
async def catch_all_message(message: types.Message):
    # Used for capturing a bKash number after /withdraw: we check last pending withdrawal in awaiting_account
    text = message.text.strip()
    uid = message.from_user.id
    if text.startswith("01") or text.startswith("+8801"):  # simple heuristic for bKash phone
        async with pool.acquire() as conn:
            w = await conn.fetchrow("SELECT id, status, amount FROM withdrawals WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1", uid)
            if w and w['status'] == 'awaiting_account':
                # store account_info and mark pending for admin
                account_info = {'bkash_phone': text}
                await conn.execute("UPDATE withdrawals SET account_info=$1, status='pending' WHERE id=$2", json.dumps(account_info), w['id'])
                # move user's available balance to pending_balance
                await conn.execute("UPDATE users SET balance = 0, pending_balance = pending_balance + $1 WHERE id=$2", w['amount'], uid)
                await message.reply("আপনার উইথড্র রিকোয়েস্ট সাবমিট হয়েছে — অ্যাডমিন যাচাই করে অনুমোদন/প্রত্যাখ্যান করবেন।")
                return

    # default help
    await message.reply("এই বটে ব্যবহারের কমান্ড: /start, /balance, /tasks, /ads, /withdraw, /referrals")

# Startup
async def on_startup(dp):
    global pool
    pool = await db_connect()
    logging.info("Connected to DB")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
