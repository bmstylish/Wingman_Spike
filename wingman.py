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
MP3_FILE_PATH = 'resource/planting.mp3'

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

@bot.tree.command(name="wingman_plant_the_spike", description="Join the voice channel and play MP3")
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
        async with session.post(SECOND_BOT_COMMAND_URL, json={'guild_id': interaction.guild.id, 'channel_id': channel.id}) as resp:
            if resp.status == 200:
                await interaction.followup.send("Wingman bot joined the voice channel!")
            else:
                await interaction.followup.send("Failed to get Wingman bot to join the voice channel.")

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel.")

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