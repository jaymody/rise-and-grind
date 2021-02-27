import json
import asyncio
import argparse
import datetime

import discord
from discord.ext import commands
from discord.utils import find

# config
parser = argparse.ArgumentParser()
parser.add_argument("--dev", type=bool, default=False)
args = parser.parse_args()

config_file = "test_config.json" if args.dev else "config.json"
with open(config_file) as fi:
    config = json.load(fi)

# TODO: only use necessary intents
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="!", intents=intents)


def current_time():
    return datetime.datetime.now().time()


def in_time_range(start, now, end):
    if start < end:
        return now >= start and now <= end
    else:  # time interval crosses midnight
        return now >= start or now <= end


@bot.event
async def on_ready():
    bot.morning_club = set(map(bot.get_user, config["morning_club"]))
    bot.guild = find(lambda x: x.id == config["guild"], bot.guilds)
    bot.voice = find(lambda x: x.id == config["voice"], bot.guild.channels)
    bot.chat = find(lambda x: x.id == config["chat"], bot.guild.channels)

    print("loop started")

    # run main loop
    while True:
        attended = {k: False for k in bot.morning_club}
        while not in_time_range(bot.start_time, current_time(), bot.end_time):
            await asyncio.sleep(5)

        while in_time_range(bot.start_time, current_time(), bot.end_time):
            for member in bot.voice.members:
                attended[member] = True
            await bot.chat.send(f"{attended}")
            await asyncio.sleep(5)

        for user, is_awake in attended.items():
            if not is_awake:
                await bot.chat.send(
                    f"{user.mention}, you didn't wake up today eh. Big lack."
                )


@bot.command(brief="Stop the bot")
async def stop(ctx):
    """
    Example:
    !stop
    """
    config["morning_club"] = [user.id for user in bot.morning_club]
    config["guild"] = bot.guild.id
    config["voice"] = bot.voice.id
    config["chat"] = bot.chat.id
    with open(config_file, "w") as fo:
        json.dump(config, fo, indent=2)
    await bot.logout()


@bot.command(brief="Add users to the morning club")
async def add_users(ctx, users: commands.Greedy[discord.Member]):
    """
    Example 1:
    !add_users @Some_user

    Example 2:
    !add_users @some_user @another_user
    """
    for user in users:
        bot.morning_club.add(user)
        await ctx.channel.send(f"{user.display_name} welcome to the club!")


@bot.command(brief="Remove users from the morning club")
async def remove_users(ctx, users: commands.Greedy[discord.Member]):
    """
    Example 1:
    !remove_users @Some_user

    Example 2:
    !remove_users @some_user @another_user
    """
    for user in users:
        if user in bot.morning_club:
            bot.morning_club.remove(user)
            await ctx.channel.send(f"{user.display_name} left the club ;(")


@bot.command(brief="Get morning club info")
async def info(ctx):
    """
    Example:
    !info
    """
    message = (
        "--- info ---\n"
        f"morning club members: {', '.join([x.display_name for x in bot.morning_club])}\n\n"
        f"voice channel: {bot.voice.name}\n"
        f"chat channel: {bot.chat.name}\n\n"
        f"start time: {bot.start_time}\n"
        f"end time: {bot.end_time}\n"
    )
    # club members
    await ctx.channel.send(message)


@bot.command(brief="Set start and end times HH:MM:SS (24 hour format)")
async def set_times(ctx, start_time: str, end_time: str):
    """
    Example 1:
    !set_times 06:30:00 - 07:00:00

    Example 2:
    !set_times 18:30:00 - 18:45:00
    """
    try:
        bot.start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
        bot.end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
        await ctx.channel.send(
            f"new start/end times set to: {bot.start_time} - {bot.end_time}"
        )
    except ValueError as e:
        await ctx.channel.send(e)


@bot.command(brief="Set text channel")
async def set_text_channel(ctx, chat: discord.TextChannel):
    """
    !set_text_channel #some_text_channel
    """
    bot.chat = chat
    await ctx.channel.send(f"text channel set to {bot.chat.name}")


@bot.command(brief="Set voice channel")
async def set_voice_channel(ctx, voice: discord.VoiceChannel):
    """
    !set_voice_channel <#ID_OF_VOICE_CHANNEL>
    """
    bot.voice = voice
    await ctx.channel.send(f"text channel set to {bot.voice.name}")


if __name__ == "__main__":
    bot.run(config["token"])
