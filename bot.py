import telebot
from telebot import types
import asyncio
import os
import sqlite3
from datetime import datetime
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioFile, AudioParameters
import yt_dlp as ydl
from config import BOT_TOKEN, OWNER_ID, OWNER_NAME, BOT_NAME, BOT_USERNAME, DATABASE_NAME, MAX_QUEUE_SIZE, MAX_SONG_DURATION, AUTO_DELETE_AFTER_PLAY

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
pytgcalls = PyTgCalls(bot)

queue = {}
current_song = {}
is_playing = {}

def get_db():
    conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        added_by INTEGER,
        added_at TEXT,
        bot_active INTEGER DEFAULT 1,
        dj_mode INTEGER DEFAULT 0
    );
    """)
    db.commit()
    db.close()

init_db()

def get_group(chat_id):
    db = get_db()
    g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    if not g:
        db.execute("INSERT INTO groups (chat_id, added_at) VALUES (?,?)", 
                   (chat_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        db.commit()
        g = db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
    db.close()
    return dict(g) if g else None

def can_play(chat_id, user_id):
    g = get_group(chat_id)
    if g and g['dj_mode'] == 0:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def download_audio(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True
    }
    os.makedirs('downloads', exist_ok=True)
    with ydl.YoutubeDL(ydl_opts) as y:
        result = y.extract_info(f"ytsearch:{query}", download=True)
        if result and 'entries' in result:
            video = result['entries'][0]
            filename = f"downloads/{video['id']}.mp3"
            return filename, video['title'], video['duration']
    return None, None, None

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = message.from_user
    if message.chat.type == 'private':
        text = f"""💔 <b>{BOT_NAME}</b> 🎶\n\nWelcome {user.first_name}!\nType /play <song> to play music in voice chat!"""
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, f"💔 <b>{BOT_NAME}</b> is ready! Type /play <song>")

@bot.message_handler(commands=['play'])
def cmd_play(message):
    chat_id = message.chat.id
    if len(message.text.split()) < 2:
        return bot.reply_to(message, "⚠️ Use: /play <song_name>")
    
    query = message.text.split(" ", 1)[1]
    search_msg = bot.reply_to(message, f"🔍 Searching... 🎵 {query}")
    
    try:
        filename, title, duration = download_audio(query)
        if not filename:
            return bot.edit_message_text("❌ Gaana nahi mila!", chat_id, search_msg.message_id)
        
        # --- DURATION CHECK (Yahan update kiya hai) ---
        if duration and duration > MAX_SONG_DURATION:
            if os.path.exists(filename):
                os.remove(filename)
            max_mins = MAX_SONG_DURATION // 60
            return bot.edit_message_text(f"❌ Ye gaana bahut lamba hai! Max limit {max_mins} minutes ki hai.", chat_id, search_msg.message_id)
        
        if chat_id not in queue:
            queue[chat_id] = []
        
        queue[chat_id].append({
            'file': filename,
            'title': title,
            'duration': duration,
            'requested_by': message.from_user.first_name
        })
        
        if chat_id not in is_playing or not is_playing[chat_id]:
            asyncio.run(play_next(chat_id))
        
        bot.edit_message_text(f"✅ <b>Added:</b> {title}", chat_id, search_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)}", chat_id, search_msg.message_id)

async def play_next(chat_id):
    global is_playing
    if chat_id not in queue or not queue[chat_id]:
        is_playing[chat_id] = False
        return
    
    is_playing[chat_id] = True
    song = queue[chat_id].pop(0)
    
    try:
        await pytgcalls.start(chat_id)
        await pytgcalls.play(AudioFile(song['file'], AudioParameters(bitrate=192000, sample_rate=48000)))
        bot.send_message(chat_id, f"🎶 <b>Now Playing:</b> {song['title']}")
        
        await asyncio.sleep(song['duration'] + 2)
        await play_next(chat_id)
    except Exception as e:
        print(f"Play error: {e}")
        is_playing[chat_id] = False

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    chat_id = message.chat.id
    asyncio.run(pytgcalls.stop())
    is_playing[chat_id] = False
    queue[chat_id] = []
    bot.reply_to(message, "🛑 Stopped.")

print(f"🎵 {BOT_NAME} is running...")
bot.infinity_polling()
