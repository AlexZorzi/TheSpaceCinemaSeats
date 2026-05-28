import asyncio
import sqlite3
import logging
import re
import io
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from PIL import Image, ImageDraw, ImageFont
from TheSpaceCinema import TheSpaceCinema

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "bookings.db")


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            cinema_id TEXT NOT NULL,
            cinema_name TEXT NOT NULL,
            film_title TEXT NOT NULL,
            session_json TEXT NOT NULL,
            selected_seats_json TEXT NOT NULL,
            start_time TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    con.commit()
    con.close()


def add_booking(
    user_id,
    chat_id,
    cinema_data,
    cinema_name,
    film_title,
    session_data,
    seats_data,
    start_time,
):
    import json

    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT INTO bookings
            (user_id, chat_id, cinema_id, cinema_name, film_title,
             session_json, selected_seats_json, start_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            chat_id,
            json.dumps(cinema_data),
            cinema_name,
            film_title,
            json.dumps(session_data),
            json.dumps(seats_data),
            json.dumps(seats_data) if not isinstance(seats_data, str) else seats_data,
            start_time,
        ) if False else (
            user_id,
            chat_id,
            json.dumps(cinema_data),
            cinema_name,
            film_title,
            json.dumps(session_data),
            json.dumps(seats_data),
            start_time,
        ),
    )
    con.commit()
    con.close()


def get_active_bookings():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM bookings WHERE active = 1").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_user_bookings(user_id):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM bookings WHERE user_id = ? AND active = 1", (user_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def deactivate_booking(booking_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE bookings SET active = 0 WHERE id = ?", (booking_id,))
    con.commit()
    con.close()


def get_analytics():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    total_bookings = con.execute("SELECT COUNT(*) as count FROM bookings").fetchone()["count"]
    active_bookings = con.execute("SELECT COUNT(*) as count FROM bookings WHERE active = 1").fetchone()["count"]
    total_users = con.execute("SELECT COUNT(DISTINCT user_id) as count FROM bookings").fetchone()["count"]

    top_cinemas = con.execute("""
        SELECT cinema_name, COUNT(*) as count
        FROM bookings
        GROUP BY cinema_name
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()

    top_films = con.execute("""
        SELECT film_title, COUNT(*) as count
        FROM bookings
        GROUP BY film_title
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()

    recent_activity = con.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM bookings
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """).fetchall()

    con.close()

    return {
        "total_bookings": total_bookings,
        "active_bookings": active_bookings,
        "total_users": total_users,
        "top_cinemas": [dict(r) for r in top_cinemas],
        "top_films": [dict(r) for r in top_films],
        "recent_activity": [dict(r) for r in recent_activity]
    }


user_states = {}


def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {}
    return user_states[user_id]


def clear_state(user_id):
    user_states.pop(user_id, None)


space = TheSpaceCinema()

PAGE_SIZE = 8


def paginated_keyboard(items, label_key, prefix, page=0):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = items[start:end]
    keyboard = []
    for idx, item in enumerate(page_items):
        global_idx = start + idx
        keyboard.append(
            [
                InlineKeyboardButton(
                    item[label_key], callback_data=f"{prefix}:{global_idx}"
                )
            ]
        )
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_page:{page - 1}")
        )
    if end < len(items):
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_page:{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append(
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    )
    return InlineKeyboardMarkup(keyboard)


# Standard ANSI 16 colors (we use the bright variants 90-97)
ANSI_COLORS = {
    30: (0, 0, 0),
    31: (205, 49, 49),
    32: (13, 188, 121),
    33: (229, 229, 16),
    34: (36, 114, 200),
    35: (188, 63, 188),
    36: (17, 168, 205),
    37: (229, 229, 229),
    90: (102, 102, 102),
    91: (241, 76, 76),    # bright red
    92: (35, 209, 139),   # bright green
    93: (245, 245, 67),
    94: (59, 142, 234),   # bright blue
    95: (214, 112, 214),
    96: (41, 184, 219),
    97: (255, 255, 255),
}


def ansi_256_to_rgb(n):
    """Convert xterm 256-color code to RGB."""
    if n < 16:
        return ANSI_COLORS.get(n if n < 8 else 90 + (n - 8), (255, 255, 255))
    if n >= 232:
        v = 8 + (n - 232) * 10
        return (v, v, v)
    n -= 16
    r = n // 36
    g = (n % 36) // 6
    b = n % 6
    table = [0, 95, 135, 175, 215, 255]
    return (table[r], table[g], table[b])


def parse_ansi(text):
    """Parse ANSI escape codes and return list of (char, fg_rgb, underline) tuples."""
    ansi_re = re.compile(r"\x1b\[([0-9;]*)m")
    result = []
    fg = (220, 220, 220)
    underline = False

    pos = 0
    for m in ansi_re.finditer(text):
        # Add text before this escape
        for ch in text[pos:m.start()]:
            result.append((ch, fg, underline))
        codes = m.group(1)
        if codes == "":
            codes_list = [0]
        else:
            codes_list = [int(c) for c in codes.split(";")]

        i = 0
        while i < len(codes_list):
            c = codes_list[i]
            if c == 0:
                fg = (220, 220, 220)
                underline = False
            elif c == 4:
                underline = True
            elif c == 24:
                underline = False
            elif 30 <= c <= 37 or 90 <= c <= 97:
                fg = ANSI_COLORS.get(c, (220, 220, 220))
            elif c == 38:
                # 38;5;N (256 color) or 38;2;R;G;B (truecolor)
                if i + 1 < len(codes_list) and codes_list[i + 1] == 5:
                    if i + 2 < len(codes_list):
                        fg = ansi_256_to_rgb(codes_list[i + 2])
                        i += 2
                elif i + 1 < len(codes_list) and codes_list[i + 1] == 2:
                    if i + 4 < len(codes_list):
                        fg = (codes_list[i + 2], codes_list[i + 3], codes_list[i + 4])
                        i += 4
            elif c == 39:
                fg = (220, 220, 220)
            i += 1
        pos = m.end()

    for ch in text[pos:]:
        result.append((ch, fg, underline))

    return result


def ansi_to_image(text, font_path=None, font_size=18, bg=(20, 20, 25)):
    """Render ANSI-colored text into a PIL Image."""
    # Try to find a monospace font
    if font_path is None:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/Menlo.ttc",
            "C:\\Windows\\Fonts\\consola.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        ]
        for p in candidates:
            if os.path.exists(p):
                font_path = p
                break

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Measure character size with a representative char
    tmp_img = Image.new("RGB", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp_img)
    bbox = tmp_draw.textbbox((0, 0), "M", font=font)
    ch_w = bbox[2] - bbox[0]
    ch_h = bbox[3] - bbox[1]
    # Add a little spacing
    line_h = int(ch_h * 1.6)
    ch_w = max(ch_w, font_size // 2)

    # Parse and split into lines
    parsed = parse_ansi(text)
    lines = [[]]
    for ch, fg, ul in parsed:
        if ch == "\n":
            lines.append([])
        elif ch == "\r":
            continue
        else:
            lines[-1].append((ch, fg, ul))

    # Trim trailing empty lines
    while lines and not lines[-1]:
        lines.pop()

    max_chars = max((len(l) for l in lines), default=1)
    padding = 20
    img_w = max_chars * ch_w + padding * 2
    img_h = len(lines) * line_h + padding * 2

    img = Image.new("RGB", (img_w, img_h), bg)
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        x = padding
        for ch, fg, ul in line:
            draw.text((x, y), ch, font=font, fill=fg)
            if ul:
                draw.line((x, y + line_h - 4, x + ch_w, y + line_h - 4), fill=fg, width=1)
            x += ch_w
        y += line_h

    return img


def seat_map_image_bytes(seats):
    """Build PNG image of the seat map."""
    text = _build_seat_map_text(seats)
    img = ansi_to_image(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _build_seat_map_text(seats):
    """Generate seat map text with ANSI codes."""
    try:
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        space.printSeats(seats)
        sys.stdout = old_stdout
        return buffer.getvalue()
    except Exception:
        return str(seats)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *TheSpaceCinema Seat Keeper Bot*\n\n"
        "Commands:\n"
        "/book – Start a new seat reservation flow\n"
        "/mybookings – List your active bookings\n"
        "/cancel\\_booking – Cancel an active booking\n"
        "/analytics – View usage statistics\n"
        "/help – Show this message",
        parse_mode="Markdown",
    )


async def cmd_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_state(user_id)
    state = get_state(user_id)

    await update.message.reply_text("⏳ Loading cinemas…")
    cinemas = space.getCinemas()
    state["cinemas"] = cinemas
    state["step"] = "cinema"

    kb = paginated_keyboard(cinemas, "cinemaName", "cinema", page=0)
    await update.message.reply_text("🏢 Pick a cinema:", reply_markup=kb)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    state = get_state(user_id)

    if data == "cancel":
        clear_state(user_id)
        await query.edit_message_text("❌ Cancelled.")
        return

    if "_page:" in data:
        prefix, page_str = data.rsplit("_page:", 1)
        page = int(page_str)
        if prefix == "cinema":
            kb = paginated_keyboard(state["cinemas"], "cinemaName", "cinema", page)
            await query.edit_message_reply_markup(reply_markup=kb)
        elif prefix == "film":
            kb = paginated_keyboard(state["films"], "filmTitle", "film", page)
            await query.edit_message_reply_markup(reply_markup=kb)
        elif prefix == "day":
            kb = paginated_keyboard(state["showingGroups"], "_label", "day", page)
            await query.edit_message_reply_markup(reply_markup=kb)
        elif prefix == "time":
            kb = paginated_keyboard(state["session_items"], "label", "time", page)
            await query.edit_message_reply_markup(reply_markup=kb)
        return

    prefix, idx_str = data.split(":", 1)
    idx = int(idx_str)

    if prefix == "cinema":
        selected_cinema = state["cinemas"][idx]
        state["selected_cinema"] = selected_cinema
        await query.edit_message_text(
            f"✅ Cinema: *{selected_cinema['cinemaName']}*\n⏳ Loading films…",
            parse_mode="Markdown",
        )
        films = space.getFilms(selected_cinema)
        state["films"] = films
        state["step"] = "film"
        kb = paginated_keyboard(films, "filmTitle", "film", 0)
        await query.message.reply_text("🎥 Pick a film:", reply_markup=kb)

    elif prefix == "film":
        selected_film = state["films"][idx]
        state["selected_film"] = selected_film
        await query.edit_message_text(
            f"✅ Film: *{selected_film['filmTitle']}*\n⏳ Loading dates…",
            parse_mode="Markdown",
        )
        showingGroups = space.getShowingGroups(
            state["selected_cinema"], selected_film
        )
        state["showingGroups"] = showingGroups
        state["step"] = "day"
        for sg in showingGroups:
            raw = sg["date"]
            try:
                dt = datetime.fromisoformat(raw)
                sg["_label"] = dt.strftime("%A %d %B %Y")
            except Exception:
                sg["_label"] = raw
        kb = paginated_keyboard(showingGroups, "_label", "day", 0)
        await query.message.reply_text("📅 Pick a day:", reply_markup=kb)

    elif prefix == "day":
        selected_day = state["showingGroups"][idx]
        state["selected_day"] = selected_day
        await query.edit_message_text(
            f"✅ Day: *{selected_day.get('_label', selected_day['date'])}*",
            parse_mode="Markdown",
        )
        sessions = selected_day["sessions"]
        items = []
        for s in sessions:
            try:
                dt = datetime.fromisoformat(s["startTime"])
                label = dt.strftime("%H:%M")
            except Exception:
                label = s["startTime"]
            items.append({"label": label, **s})
        state["session_items"] = items
        kb = paginated_keyboard(items, "label", "time", 0)
        await query.message.reply_text("🕐 Pick a showtime:", reply_markup=kb)

    elif prefix == "time":
        sessions = state["selected_day"]["sessions"]
        selected_showing = sessions[idx]
        state["selected_showing"] = selected_showing
        try:
            dt = datetime.fromisoformat(selected_showing["startTime"])
            label = dt.strftime("%H:%M")
        except Exception:
            label = selected_showing["startTime"]
        await query.edit_message_text(
            f"✅ Showtime: *{label}*\n⏳ Loading seat map…",
            parse_mode="Markdown",
        )
        seats = space.getSeats(state["selected_cinema"], selected_showing)
        state["seats"] = seats

        state["step"] = "seats"

        # Send the seat map as an image
        try:
            img_buf = seat_map_image_bytes(seats)
            await query.message.reply_photo(
                photo=img_buf,
                caption="💺 Send the seats you want separated by spaces.\n"
                        "Example: `G4 G5 H11`",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to render seat map image: {e}")
            # Fallback: send raw text without ANSI codes
            text = _build_seat_map_text(seats)
            clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
            await query.message.reply_text(
                f"```\n{clean}\n```\n\n"
                "💺 Send the seats you want separated by spaces.\n"
                "Example: `G4 G5 H11`",
                parse_mode="Markdown",
            )

    elif prefix == "confirm":
        if idx == 1:
            cinema = state["selected_cinema"]
            showing = state["selected_showing"]
            selected_seats = state["selected_seats_objects"]
            film = state["selected_film"]
            start_time = showing["startTime"]

            add_booking(
                user_id=user_id,
                chat_id=update.effective_chat.id,
                cinema_data=cinema,
                cinema_name=cinema["cinemaName"],
                film_title=film["filmTitle"],
                session_data=showing,
                seats_data=selected_seats,
                start_time=start_time,
            )

            try:
                space.postOrder(cinema, showing, selected_seats)
            except Exception as e:
                logger.error(f"First postOrder failed: {e}")

            await query.edit_message_text(
                "✅ *Booking saved!*\n"
                f"🏢 {cinema['cinemaName']}\n"
                f"🎥 {film['filmTitle']}\n"
                f"🕐 {start_time}\n"
                f"💺 {', '.join(state['selected_seat_labels'])}\n\n"
                "The bot will keep refreshing the seats every 60 seconds "
                "until the movie starts.",
                parse_mode="Markdown",
            )
            clear_state(user_id)
        else:
            clear_state(user_id)
            await query.edit_message_text("❌ Booking cancelled.")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)

    if state.get("step") != "seats":
        return

    raw = update.message.text.strip()
    seat_labels = raw.split()
    state["selected_seat_labels"] = [s.upper() for s in seat_labels]

    try:
        selected_seats = space.selectSeats(state["seats"], seat_labels)
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Could not select those seats: `{e}`\nTry again.",
            parse_mode="Markdown",
        )
        return

    state["selected_seats_objects"] = selected_seats
    state["step"] = "confirm"

    cinema = state["selected_cinema"]
    film = state["selected_film"]
    showing = state["selected_showing"]

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm:1"),
                InlineKeyboardButton("❌ Cancel", callback_data="confirm:0"),
            ]
        ]
    )
    await update.message.reply_text(
        f"*Confirm booking?*\n\n"
        f"🏢 {cinema['cinemaName']}\n"
        f"🎥 {film['filmTitle']}\n"
        f"🕐 {showing['startTime']}\n"
        f"💺 {', '.join(state['selected_seat_labels'])}",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def cmd_mybookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bookings = get_user_bookings(user_id)
    if not bookings:
        await update.message.reply_text("You have no active bookings.")
        return
    lines = []
    for b in bookings:
        lines.append(
            f"🆔 `{b['id']}` | 🏢 {b['cinema_name']} | 🎥 {b['film_title']}\n"
            f"   🕐 {b['start_time']}"
        )
    await update.message.reply_text(
        "*Your active bookings:*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bookings = get_user_bookings(user_id)
    if not bookings:
        await update.message.reply_text("You have no active bookings to cancel.")
        return
    kb = []
    for b in bookings:
        label = f"🆔{b['id']} {b['cinema_name']} – {b['film_title']} @ {b['start_time']}"
        kb.append(
            [InlineKeyboardButton(label, callback_data=f"delbooking:{b['id']}")]
        )
    kb.append([InlineKeyboardButton("❌ Nevermind", callback_data="cancel")])
    await update.message.reply_text(
        "Which booking do you want to cancel?",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def delbooking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("delbooking:"):
        return
    booking_id = int(data.split(":")[1])
    user_id = update.effective_user.id

    bookings = get_user_bookings(user_id)
    ids = [b["id"] for b in bookings]
    if booking_id not in ids:
        await query.edit_message_text("⚠️ Booking not found or not yours.")
        return

    deactivate_booking(booking_id)
    await query.edit_message_text(f"✅ Booking `{booking_id}` cancelled.", parse_mode="Markdown")


async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_analytics()

    message = "📊 *Bot Analytics*\n\n"
    message += f"📈 *Overview*\n"
    message += f"• Total Bookings: {stats['total_bookings']}\n"
    message += f"• Active Bookings: {stats['active_bookings']}\n"
    message += f"• Total Users: {stats['total_users']}\n\n"

    if stats['top_cinemas']:
        message += f"🏢 *Top Cinemas*\n"
        for cinema in stats['top_cinemas']:
            message += f"• {cinema['cinema_name']}: {cinema['count']} bookings\n"
        message += "\n"

    if stats['top_films']:
        message += f"🎥 *Top Films*\n"
        for film in stats['top_films']:
            message += f"• {film['film_title']}: {film['count']} bookings\n"
        message += "\n"

    if stats['recent_activity']:
        message += f"📅 *Activity (Last 7 Days)*\n"
        for activity in stats['recent_activity']:
            message += f"• {activity['date']}: {activity['count']} bookings\n"

    await update.message.reply_text(message, parse_mode="Markdown")


async def keep_alive_loop(app: Application):
    import json
    while True:
        await asyncio.sleep(60)
        try:
            bookings = get_active_bookings()
            now = datetime.now()
            for b in bookings:
                start_time_str = b["start_time"]
                try:
                    start_dt = datetime.fromisoformat(start_time_str)
                except Exception:
                    deactivate_booking(b["id"])
                    continue

                if now >= start_dt:
                    deactivate_booking(b["id"])
                    try:
                        await app.bot.send_message(
                            chat_id=b["chat_id"],
                            text=f"🎬 Booking `{b['id']}` for *{b['film_title']}* "
                            f"has been stopped — the movie has started!",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
                    continue

                try:
                    cinema = json.loads(b["cinema_id"])
                    session = json.loads(b["session_json"])
                    seats = json.loads(b["selected_seats_json"])
                    space.postOrder(cinema, session, seats)
                    logger.info(f"Refreshed booking {b['id']}")
                except Exception as e:
                    logger.error(f"postOrder failed for booking {b['id']}: {e}")
                    try:
                        await app.bot.send_message(
                            chat_id=b["chat_id"],
                            text=f"⚠️ Refresh failed for booking `{b['id']}` "
                            f"({b['film_title']}): {e}",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"keep_alive_loop error: {e}")


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("book", cmd_book))
    app.add_handler(CommandHandler("mybookings", cmd_mybookings))
    app.add_handler(CommandHandler("cancel_booking", cmd_cancel_booking))
    app.add_handler(CommandHandler("analytics", cmd_analytics))

    app.add_handler(CallbackQueryHandler(delbooking_handler, pattern=r"^delbooking:"))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    async def post_init(application: Application):
        application._keep_alive_task = asyncio.create_task(
            keep_alive_loop(application)
        )

    app.post_init = post_init

    logger.info("Bot starting…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()