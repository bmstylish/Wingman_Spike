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
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
app = web.Application()

pending_disconnects = {}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="plant_the_spike", description="Hold 4 to plant the spike")
async def join(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    channel = interaction.user.voice.channel
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message("Joined the voice channel and playing audio!")

    await play_audio_and_check_command(interaction.guild, interaction.user, channel, interaction)

@bot.tree.command(name="defuse", description="Hold 4 to defuse the spike")
async def defuse(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in pending_disconnects:
        pending_disconnects[guild_id].cancel()
        del pending_disconnects[guild_id]

        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()

        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()

        await interaction.response.send_message('Spike has been defused')
    else:
        await interaction.response.send_message('There is no spike to defuse')

async def handle_join_request(request):
    data = await request.json()

    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    user_id = data.get('user_id')  # Get user ID from the request data

    if not all([guild_id, channel_id, user_id]):
        return web.Response(status=400, text="Missing required parameters: guild_id, channel_id, or user_id.")

    guild = bot.get_guild(guild_id)
    user = guild.get_member(user_id)  # Get the user object
    if guild:
        channel = guild.get_channel(channel_id)
        if channel:
            if guild.voice_client is not None:
                await guild.voice_client.move_to(channel)
            else:
                await channel.connect()

            await play_audio_and_check_command(guild, user, channel)

            # Notify Bot1 to leave the voice channel
            async with aiohttp.ClientSession() as session:
                async with session.post('http://localhost:8000/leave', json={'guild_id': guild_id}) as resp:
                    if resp.status == 200:
                        print("Bot1 left the voice channel.")
                    else:
                        print("Failed to notify Bot1 to leave the voice channel.")

            return web.Response(text="Joined the voice channel!")
    return web.Response(status=400, text="Failed to join the voice channel.")

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message('Left the voice channel.')
    else:
        await interaction.response.send_message('I am not in a voice channel.')

async def handle_stop_disconnection(request):
    data = await request.json()
    guild_id = data.get('guild_id')

    if guild_id not in pending_disconnects:
        return web.Response(status=400, text="No pending disconnection task found.")

    disconnect_task = pending_disconnects[guild_id]
    disconnect_task.cancel()
    del pending_disconnects[guild_id]

    return web.Response(status=200, text="Disconnection task stopped.")

async def handle_leave_request(request):
    data = await request.json()
    guild_id = data.get('guild_id')

    guild = bot.get_guild(guild_id)
    if guild and guild.voice_client:
        await guild.voice_client.disconnect()
        return web.Response(text="Bot has left the voice channel.")
    return web.Response(status=400, text="Bot failed to leave the voice channel.")

async def handle_defuse_request(request):
    data = await request.json()
    guild_id = data.get('guild_id')

    guild = bot.get_guild(guild_id)
    if guild:
        if guild.id in pending_disconnects:
            pending_disconnects[guild.id].cancel()
            del pending_disconnects[guild.id]

            if guild.voice_client and guild.voice_client.is_playing():
                guild.voice_client.stop()

            if guild.voice_client:
                await guild.voice_client.disconnect()

            return web.Response(status=200, text="Spike has been defused")
    return web.Response(status=400, text="Failed to defuse the spike")

app.add_routes([web.post('/stop_disconnection', handle_stop_disconnection)])
app.add_routes([web.post('/join', handle_join_request)])
app.add_routes([web.post('/leave', handle_leave_request)])
app.add_routes([web.post('/defuse', handle_defuse_request)])

async def play_audio_and_check_command(guild, user, channel, interaction=None):
    mp3_path = 'resource/timer.mp3'
    voice_client = guild.voice_client
    voice_client.play(discord.FFmpegPCMAudio(mp3_path))

    def check(message):
        return message.content.lower() == '!specific_command' and message.author == user

    disconnect_task = asyncio.create_task(
        disconnect_users_after_timeout(guild, user, channel, interaction))
    pending_disconnects[guild.id] = disconnect_task

    try:
        await bot.wait_for('message', check=check, timeout=13)
        disconnect_task.cancel()
        del pending_disconnects[guild.id]
        if interaction:
            await interaction.followup.send('Command received in time, no one will be disconnected.')
    except asyncio.TimeoutError:
        pass


async def disconnect_users_after_timeout(guild, user, channel, interaction=None):
    await asyncio.sleep(13)
    for member in channel.members:
        if member.voice:
            await member.move_to(None)
    if interaction:
        await interaction.followup.send('Time is up! Everyone has been disconnected.')

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8000)
    await site.start()
    print("Web server started.")

async def main():
    await start_web_server()
    await bot.start(TOKEN)

asyncio.run(main())