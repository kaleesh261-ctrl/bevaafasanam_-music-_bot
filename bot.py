import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
import yt_dlp as ydl
from config import API_ID, API_HASH, STRING_SESSION, OWNER_NAME, BOT_NAME, MAX_SONG_DURATION

print(f"🎵 Starting {BOT_NAME} on Render...")

app = Client(
    "bevafasanam_music",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION
)

call_py = PyTgCalls(app)
queue = {}
is_playing = {}

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
            return filename, video['title'], video.get('duration', 180)
    return None, None, None

@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    text = f"💔 <b>{BOT_NAME}</b> 🎶\n\nMain Render par 24/7 chalne wala Music Bot hoon! Group me VC on karke /play [song name] likhein."
    await message.reply_text(text)

@app.on_message(filters.command("play"))
async def play_cmd(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Use: <code>/play [song_name]</code>")
    
    query = " ".join(message.command[1:])
    search_msg = await message.reply_text(f"🔍 Searching for <b>{query}</b>...")
    
    try:
        filename, title, duration = await asyncio.to_thread(download_audio, query)
        if not filename:
            return await search_msg.edit_text("❌ Gaana nahi mila!")
        
        if duration and duration > MAX_SONG_DURATION:
            if os.path.exists(filename):
                os.remove(filename)
            return await search_msg.edit_text("❌ Ye gaana bahut lamba hai!")
        
        if chat_id not in queue:
            queue[chat_id] = []
        
        queue[chat_id].append({
            'file': filename,
            'title': title,
            'duration': duration,
            'user': message.from_user.first_name
        })
        
        if chat_id not in is_playing or not is_playing[chat_id]:
            asyncio.create_task(play_next(client, chat_id))
            
        await search_msg.edit_text(f"✅ Added to queue: <b>{title}</b>")
    except Exception as e:
        await search_msg.edit_text(f"❌ Error: {str(e)}")

async def play_next(client, chat_id):
    global is_playing
    if chat_id not in queue or not queue[chat_id]:
        is_playing[chat_id] = False
        return
    
    is_playing[chat_id] = True
    song = queue[chat_id].pop(0)
    
    try:
        await call_py.play(chat_id, AudioPiped(song['file']))
        await client.send_message(
            chat_id,
            f"🎶 <b>Now Playing:</b> <code>{song['title']}</code>\n👤 Requested by: {song['user']}"
        )
        await asyncio.sleep(song['duration'] + 2)
        await play_next(client, chat_id)
    except Exception as e:
        print(f"Play error: {e}")
        is_playing[chat_id] = False

@app.on_message(filters.command("stop"))
async def stop_cmd(client, message: Message):
    chat_id = message.chat.id
    try:
        await call_py.leave_call(chat_id)
    except:
        pass
    is_playing[chat_id] = False
    queue[chat_id] = []
    await message.reply_text("🛑 Music stopped.")

async def main():
    await app.start()
    await call_py.start()
    print(f"🎵 {BOT_NAME} is fully online on Render!")
    await idle()
    await call_py.stop()
    await app.stop()

if __name__ == "__main__":
    app.loop.run_until_complete(main())
