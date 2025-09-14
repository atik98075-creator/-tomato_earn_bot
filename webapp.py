# webapp.py
# Requirements: Flask, asyncpg, python-dotenv
# pip install Flask asyncpg python-dotenv

import os
import json
from flask import Flask, request, jsonify, render_template_string, abort
import asyncpg
import asyncio
from datetime import datetime, date

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/tomato_db")
ADMIN_TELEGRAM_ID = 8193138896  # provided
AD_REWARD = float(os.getenv("AD_REWARD", "5"))
DAILY_AD_LIMIT = int(os.getenv("DAILY_AD_LIMIT", "10"))

loop = asyncio.get_event_loop()
pool = loop.run_until_complete(asyncio.get_event_loop().run_until_complete(asyncpg.create_pool(DATABASE_URL)))

# Monetag SDK snippet (you provided)
MONETAG_SDK_SNIPPET = "<script src='//libtl.com/sdk.js' data-zone='9875165' data-sdk='show_9875165'></script>"

@app.route("/watch_ad")
def watch_ad():
    user_id = request.args.get("user_id", "")
    if not user_id:
        abort(400, "user_id required")
    # very simple page embedding Monetag SDK - NOTE: Monetag docs need to be followed to get real callbacks/events
    html = f"""
    <!doctype html>
    <html>
    <head><meta charset="utf-8"><title>Watch Ad</title></head>
    <body>
      <h3>Watch the rewarded ad — আপনি পুরো_ads দেখা হলে রিবোর্ড পাবেন।</h3>
      {MONETAG_SDK_SNIPPET}
      <p id="status">Loading ad...</p>
      <script>
        // THIS IS A PLACEHOLDER: Integrate based on Monetag SDK docs.
        // We'll simulate that the SDK emits window.onMonetagAdComplete or similar.
        // Replace with actual Monetag event handler.
        function creditServer() {{
          fetch('/monetag_reward', {{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{user_id: {user_id}}})
          }}).then(r=>r.json()).then(d=>{
            document.getElementById('status').innerText = "Credit result: " + JSON.stringify(d);
          });
        }}

        // Simulate user watching an ad after 5 seconds (for demo). Replace with real callback.
        setTimeout(function(){{
          document.getElementById('status').innerText = "Ad finished. Crediting...";
          creditServer();
        }}, 5000);
      </script>
    </body>
    </html>
    """
    return html

@app.route("/monetag_reward", methods=["POST"])
def monetag_reward():
    data = request.get_json(force=True)
    user_id = int(data.get("user_id"))
    # basic daily limit check
    today = date.today()
    async def do_credit():
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT count(1) FROM ads_viewed WHERE user_id=$1 AND viewed_at::date = $2", user_id, today)
            if count is None:
                count = 0
            if count >= DAILY_AD_LIMIT:
                return {"status":"limit_reached", "message":"daily limit reached"}
            # credit user
            await conn.execute("INSERT INTO ads_viewed(user_id, ad_id, reward, viewed_at) VALUES($1,$2,$3,$4)",
                               user_id, None, AD_REWARD, datetime.utcnow())
            await conn.execute("UPDATE users SET balance = balance + $1, total_earned = total_earned + $1 WHERE id=$2", AD_REWARD, user_id)
            return {"status":"ok", "credited": AD_REWARD}
    res = loop.run_until_complete(do_credit())
    return jsonify(res)

# Admin API: list pending withdrawals, approve, reject
def check_admin_key():
    # For simplicity, request must provide X-Admin-Id header equal to ADMIN_TELEGRAM_ID
    admin_header = request.headers.get("X-Admin-Id")
    if not admin_header:
        abort(403)
    try:
        if int(admin_header) != ADMIN_TELEGRAM_ID:
            abort(403)
    except:
        abort(403)

@app.route("/api/withdrawals")
def api_withdrawals():
    check_admin_key()
    async def fetch():
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, user_id, amount, method, account_info, status, created_at FROM withdrawals ORDER BY created_at DESC LIMIT 200")
            return [dict(r) for r in rows]
    data = loop.run_until_complete(fetch())
    return jsonify(data)

@app.route("/api/withdrawals/<int:w_id>/approve", methods=["POST"])
def approve_withdrawal(w_id):
    check_admin_key()
    async def do_approve():
        async with pool.acquire() as conn:
            w = await conn.fetchrow("SELECT * FROM withdrawals WHERE id=$1", w_id)
            if not w:
                return {"error":"not found"}
            # Mark as approved and paid - in production you would call bKash api here and upon success mark paid
            await conn.execute("UPDATE withdrawals SET status='approved' WHERE id=$1", w_id)
            # deduct pending_balance appropriately (we previously moved to pending_balance)
            await conn.execute("UPDATE users SET pending_balance = pending_balance - $1 WHERE id=$2", w['amount'], w['user_id'])
            return {"status":"approved"}
    res = loop.run_until_complete(do_approve())
    return jsonify(res)

@app.route("/api/withdrawals/<int:w_id>/reject", methods=["POST"])
def reject_withdrawal(w_id):
    check_admin_key()
    async def do_reject():
        async with pool.acquire() as conn:
            w = await conn.fetchrow("SELECT * FROM withdrawals WHERE id=$1", w_id)
            if not w:
                return {"error":"not found"}
            # move money back to available balance
            await conn.execute("UPDATE users SET balance = balance + $1, pending_balance = pending_balance - $1 WHERE id=$2", w['amount'], w['user_id'])
            await conn.execute("UPDATE withdrawals SET status='rejected' WHERE id=$1", w_id)
            return {"status":"rejected"}
    res = loop.run_until_complete(do_reject())
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
