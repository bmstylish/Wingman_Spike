import discord
from discord.ext import commands
from aiohttp import web
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('SECOND_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intents if using discord.py v2.0+

bot = commands.Bot(command_prefix='!', intents=intents)
app = web.Application()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="plant_the_spike", description="Join the voice channel")
async def join(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    channel = interaction.user.voice.channel
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    await interaction.response.send_message("Joined the voice channel!")

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message('Left the voice channel.')
    else:
        await interaction.response.send_message('I am not in a voice channel.')

async def handle_join_request(request):
    data = await request.json()
    guild_id = data['guild_id']
    channel_id = data['channel_id']

    guild = bot.get_guild(guild_id)
    if guild:
        channel = guild.get_channel(channel_id)
        if channel:
            if guild.voice_client is not None:
                await guild.voice_client.move_to(channel)
            else:
                await channel.connect()

            # Notify Bot1 to leave the voice channel
            async with aiohttp.ClientSession() as session:
                async with session.post('http://localhost:8001/wingman_leave', json={'guild_id': guild_id}) as resp:
                    if resp.status == 200:
                        print("Wingman bot left the voice channel.")
                    else:
                        print("Failed to notify Wingman bot to leave the voice channel.")

            return web.Response(text="Joined the voice channel!")
    return web.Response(status=400, text="Failed to join the voice channel.")

app.add_routes([web.post('/join', handle_join_request)])

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8000)
    await site.start()
    print("Web server started.")

async def main():
    # Start the web server
    await start_web_server()

    # Start the bot
    await bot.start(TOKEN)

# Run the main function using asyncio
asyncio.run(main())