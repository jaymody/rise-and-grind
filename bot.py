import json
import asyncio
import logging
import datetime

import discord
from discord.ext import commands
from discord.utils import find

# logging
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
fh = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
sh = logging.StreamHandler()
fh.setFormatter(formatter)
sh.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(sh)

# config
with open("config.json") as fi:
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
    # TODO: better load config
    bot.morning_club = set(map(bot.get_user, config["morning_club"]))
    bot.guild = find(lambda x: x.id == config["guild"], bot.guilds)
    bot.voice = find(lambda x: x.id == config["voice"], bot.guild.channels)
    bot.chat = find(lambda x: x.id == config["chat"], bot.guild.channels)

    bot.start_time = datetime.time(12, 2, 30)
    bot.end_time = datetime.time(12, 9)

    logger.info("loop started")

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
                await bot.chat.send(f"{user.mention} lacked! For shame")


@bot.command(brief="Stop the bot")
async def stop(ctx):
    # TODO: save updated config
    config["morning_club"] = [user.id for user in bot.morning_club]
    config["guild"] = bot.guild.id
    config["voice"] = bot.voice.id
    config["chat"] = bot.chat.id
    with open("config.json", "w") as fo:
        json.dump(config, fo, indent=2)
    await bot.logout()


@bot.command(brief="Add users to the morning club")
async def add_users(ctx, users: commands.Greedy[discord.Member]):
    for user in users:
        bot.morning_club.add(user)


@bot.command(brief="Get morning club info")
async def info(ctx):
    # club members
    await ctx.channel.send(
        f"morning club members: {', '.join([x.display_name for x in bot.morning_club])}"
    )

    # voice and chat channels
    await ctx.channel.send(f"voice channel: {bot.voice.name}")
    await ctx.channel.send(f"chat channel: {bot.chat.name}")

    # start and end times
    await ctx.channel.send(f"start time: {bot.start_time}")
    await ctx.channel.send(f"end time: {bot.end_time}")


@bot.command(brief="Set start and end times HH:MM:SS (24 hour format)")
async def set_times(ctx, start_time: str, end_time: str):
    try:
        bot.start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
        bot.end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
        await ctx.channel.send(
            f"new start/end times set to: {bot.start_time} - {bot.end_time}"
        )
    except ValueError as e:
        await ctx.channel.send(e)


if __name__ == "__main__":
    bot.run(config["token"])
