import os, sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN=os.environ["BOT_TOKEN"]
OWNER_ID=int(os.environ["OWNER_ID"])
DB="bozor.db"

def db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chef TEXT, product TEXT, qty REAL, unit TEXT, note TEXT,
        status TEXT DEFAULT 'new', cost REAL DEFAULT 0)""")
    c.commit()
    return c

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    kb=[[InlineKeyboardButton("🛒 Yangi buyurtma",callback_data="new")],
        [InlineKeyboardButton("📋 Buyurtmalarim",callback_data="mine")]]
    await update.message.reply_text(
        "🛒 Bozor Buyurtma\n\nKerakli mahsulotni bot orqali yuboring.",
        reply_markup=InlineKeyboardMarkup(kb))

async def menu(update:Update, context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="new":
        context.user_data["step"]="product"
        await q.message.reply_text("Mahsulot nomini yozing:")
    elif q.data=="mine":
        c=db()
        rows=c.execute("SELECT id,product,qty,unit,status FROM orders WHERE chef=? ORDER BY id DESC LIMIT 10",(str(q.from_user.id),)).fetchall()
        c.close()
        if not rows:
            await q.message.reply_text("Hali buyurtma yo‘q.")
        else:
            await q.message.reply_text("\n".join(f"#{r[0]} {r[1]} — {r[2]} {r[3]} — {r[4]}" for r in rows))

async def buy_button(update:Update, context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.from_user.id != OWNER_ID: return
    oid=int(q.data.split(":")[1])
    context.user_data["buy_id"]=oid
    context.user_data["step"]="cost"
    await q.message.reply_text(f"#{oid} uchun to‘langan summani so‘mda yozing:")

async def message(update:Update, context:ContextTypes.DEFAULT_TYPE):
    step=context.user_data.get("step")
    if step=="cost" and update.effective_user.id==OWNER_ID:
        raw=update.message.text.replace(" ","").replace(",","")
        try: cost=float(raw)
        except ValueError:
            await update.message.reply_text("Summani faqat raqam bilan yozing. Masalan: 2400000")
            return
        oid=context.user_data["buy_id"]
        c=db()
        c.execute("UPDATE orders SET status='bought',cost=? WHERE id=?",(cost,oid))
        c.commit()
        total=c.execute("SELECT COALESCE(SUM(cost),0) FROM orders WHERE status='bought'").fetchone()[0]
        c.close()
        context.user_data.clear()
        await update.message.reply_text(f"✅ Xarid saqlandi.\n💰 Jami xarajat: {total:,.0f} so‘m")
        return

    if not step: return
    text=update.message.text.strip()
    if step=="product":
        context.user_data["product"]=text
        context.user_data["step"]="qty"
        await update.message.reply_text("Miqdorini yozing (masalan 20):")
    elif step=="qty":
        try: qty=float(text)
        except ValueError:
            await update.message.reply_text("Miqdorni raqam bilan yozing.")
            return
        context.user_data["qty"]=qty
        context.user_data["step"]="unit"
        await update.message.reply_text("Birlikni yozing: kg, litr, dona...")
    elif step=="unit":
        context.user_data["unit"]=text
        context.user_data["step"]="note"
        await update.message.reply_text("Izoh bo‘lsa yozing, bo‘lmasa '-' yozing:")
    elif step=="note":
        product=context.user_data["product"]; qty=context.user_data["qty"]; unit=context.user_data["unit"]
        note=text
        chef_name=update.effective_user.full_name
        c=db()
        c.execute("INSERT INTO orders(chef,product,qty,unit,note) VALUES(?,?,?,?,?)",
                  (str(update.effective_user.id),product,qty,unit,note))
        oid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit(); c.close()
        context.user_data.clear()
        await update.message.reply_text(f"✅ Buyurtma #{oid} yuborildi.")
        kb=[[InlineKeyboardButton("🛒 Olish",callback_data=f"buy:{oid}")]]
        await context.bot.send_message(
            OWNER_ID,
            f"🔔 Yangi buyurtma #{oid}\n👨‍🍳 {chef_name}\n📦 {product} — {qty} {unit}\n📝 {note}",
            reply_markup=InlineKeyboardMarkup(kb))

def main():
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(menu,pattern="^(new|mine)$"))
    app.add_handler(CallbackQueryHandler(buy_button,pattern=r"^buy:\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,message))
    app.run_polling()

if __name__=="__main__":
    main()
