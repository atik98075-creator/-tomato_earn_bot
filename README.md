Tomato 🍅 - Telegram rewards bot
--------------------------------

Prereqs:
- Python 3.10+
- PostgreSQL
- pip install -r requirements.txt (aiogram, asyncpg, Flask, python-dotenv)

Files:
- bot.py
- webapp.py
- schema.sql
- admin.html

Setup:
1. Create Postgres DB and run schema.sql:
   psql -h host -U user -d tomato_db -f schema.sql

2. Update DATABASE_URL in env or directly in files (not recommended):
   export DATABASE_URL="postgresql://user:pass@host:5432/tomato_db"

3. (Optional) update BOT_TOKEN in bot.py or set as env var.

4. Start webapp:
   python webapp.py

5. Start bot:
   python bot.py

Monetag integration:
- Currently watch_ad page includes your provided Monetag SDK snippet.
- Replace the simulated `setTimeout` in `/watch_ad` with actual Monetag SDK callback per Monetag docs.
- For production, configure Monetag server-side callbacks if available and verify signature.

bKash:
- Payout flow in admin is manual/placeholder. Integrate bKash API in `approve_withdrawal` route to trigger real payout.

Security notes:
- Move secrets to environment variables.
- Protect admin endpoints with stronger auth (JWT or admin login). Currently simple header check is used.
- Use HTTPS in production.

If you want, আমি এখন Dockerfile, requirements.txt, এবং একটি ZIP প্যাক তৈরী করে দিতে পারি — অথবা আমি এই কোডগুলোর জন্য `Dockerfile` এবং সম্পূর্ণ উদাহরণ প্রজেক্ট বানিয়ে দেব। কোনটা চান?
