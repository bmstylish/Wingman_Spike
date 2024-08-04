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
DEFUSE_SOUND_PATH = 'resource/defuse.mp3'  # Path to the defuse sound

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
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    channel = interaction.user.voice.channel
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    # Ensure the MP3 file exists
    if not os.path.isfile(MP3_FILE_PATH):
        await interaction.response.send_message(f"MP3 file not found at {MP3_FILE_PATH}.")
        return

    # Play the MP3 file
    try:
        interaction.guild.voice_client.stop()
        audio_source = discord.FFmpegPCMAudio(MP3_FILE_PATH)
        interaction.guild.voice_client.play(audio_source)
        await interaction.response.send_message("Playing the MP3 file!")
    except Exception as e:
        await interaction.response.send_message(f"Failed to play MP3 file: {e}")
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

@bot.tree.command(name="defuse", description="Hold 4 to defuse the spike")
async def defuse(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Path to the mp3 file
    mp3_path = 'resource/defuse.mp3'
    
    # Check if the bot is in a voice channel
    if interaction.guild.voice_client is None:
        if interaction.user.voice is None:
            await interaction.response.send_message("You are not connected to a voice channel.")
            return
        else:
            channel = interaction.user.voice.channel
            await channel.connect()

    # Play the audio file
    voice_client = interaction.guild.voice_client
    voice_client.play(discord.FFmpegPCMAudio(mp3_path))

    # Wait until the audio finishes playing
    while voice_client.is_playing():
        await asyncio.sleep(1)

    # Notify Bot2 to defuse using application command
    async with aiohttp.ClientSession() as session:
        async with session.post('http://localhost:8000/defuse', json={'guild_id': guild_id}) as resp:
            if resp.status == 200:
                print("Bot2 defused the spike.")
            else:
                print("Failed to notify Bot2 to defuse the spike.")

    await interaction.response.send_message('Spike defuse initiated and Bot2 notified')

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