import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
SECOND_BOT_COMMAND_URL = 'http://localhost:8000/join'
WINGMAN_LEAVE_URL = 'http://localhost:8001/wingman_leave'
SECOND_BOT_LEAVE_URL = 'http://localhost:8000/leave'
MP3_FILE_PATH = 'resource/planting.mp3'
DEFUSE_SOUND_PATH = 'resource/defuse.mp3'

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot 1 is ready. Logged in as {bot.user}.')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="wingman_plant_the_spike", description="Wingman plant the spike")
async def wingman_plant_the_spike(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not onsite.")
        return

    channel = interaction.user.voice.channel
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    # Ensure the MP3 file exists
    if not os.path.isfile(MP3_FILE_PATH):
        await interaction.response.send_message(f"You do not have the spike... {MP3_FILE_PATH}.")
        return

    # Play the MP3 file
    try:
        interaction.guild.voice_client.stop()
        audio_source = discord.FFmpegPCMAudio(MP3_FILE_PATH)
        interaction.guild.voice_client.play(audio_source)
        await interaction.response.send_message("Wingman is planting the spike!")
    except Exception as e:
        await interaction.response.send_message(f"Wingman cannot plant the spike... {e}")
        return

    # Wait until the audio is done playing
    while interaction.guild.voice_client.is_playing():
        await asyncio.sleep(1)

    # Send a request to the second bot to join the voice channel
    async with aiohttp.ClientSession() as session:
        async with session.post(SECOND_BOT_COMMAND_URL, json={'guild_id': interaction.guild.id, 'channel_id': channel.id, 'user_id': interaction.user.id}) as resp:
            if resp.status == 200:
                await interaction.followup.send("Wingman bot joined the voice channel!")
                # Make the first bot leave the voice channel after the MP3 is done playing and Wingman joins
                if interaction.guild.voice_client is not None:
                    await interaction.guild.voice_client.disconnect()
            else:
                await interaction.followup.send("Failed to get Wingman bot to join the voice channel.")

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel.")

@bot.tree.command(name="defuse", description="Defuse the spike")
async def defuse(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    # Join the voice channel if not already connected
    if voice_client is None or voice_client.channel != channel:
        await channel.connect()

    # Play the defuse sound
    if os.path.isfile(DEFUSE_SOUND_PATH):
        defuse_audio_source = discord.FFmpegPCMAudio(DEFUSE_SOUND_PATH)
        if voice_client and not voice_client.is_playing():
            voice_client.play(defuse_audio_source, after=lambda e: print(f"Error playing defuse sound: {e}") if e else None)
        else:
            await interaction.response.send_message("The bot is not connected to a voice channel or already playing audio.")
            return
    else:
        await interaction.response.send_message(f"Defuse sound file not found at {DEFUSE_SOUND_PATH}.")
        return
    
    # Disconnect Bot2 from the voice channel
    async with aiohttp.ClientSession() as session:
        async with session.post(SECOND_BOT_LEAVE_URL, json={'guild_id': interaction.guild.id}) as resp:
            if resp.status == 200:
                await interaction.followup.send("Bot2 has been disconnected from the voice channel.")
            else:
                await interaction.followup.send("Failed to disconnect Bot2 from the voice channel.")

async def handle_wingman_leave(request):
    data = await request.json()
    guild_id = data['guild_id']

    guild = bot.get_guild(guild_id)
    if guild and guild.voice_client:
        await guild.voice_client.disconnect()
        return web.Response(text="Wingman bot left the voice channel.")
    return web.Response(status=400, text="Wingman bot failed to leave the voice channel.")

app = web.Application()
app.router.add_post('/wingman_leave', handle_wingman_leave)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8001)
    await site.start()
    print("Web server started.")

async def main():
    # Start the web server
    await start_web_server()

    # Start the bot
    await bot.start(TOKEN)

# Run the main function using asyncio
asyncio.run(main())