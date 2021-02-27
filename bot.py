import os
import sys
import json
import time
import logging

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


@bot.event
async def on_ready():
    # TODO: better load config
    bot.morning_club = set(map(bot.get_user, config["morning_club"]))
    bot.guild = find(lambda x: x.id == config["guild"], bot.guilds)
    bot.voice = find(lambda x: x.id == config["voice"], bot.guild.channels)
    bot.chat = find(lambda x: x.id == config["chat"], bot.guild.channels)
    logger.info("ready!")


@bot.command(brief="Add users to the morning club")
async def add_users(ctx, users: commands.Greedy[discord.Member]):
    for user in users:
        bot.morning_club.add(user)


@bot.command(brief="List users in the morning club")
async def list_users(ctx):
    if bot.morning_club:
        await ctx.channel.send(", ".join([x.display_name for x in bot.morning_club]))
    else:
        await ctx.channel.send("no members")


@bot.command(brief="Stop the bot")
async def stop(ctx):
    # TODO: save updated config
    await bot.logout()


@bot.event
async def on_voice_state_update(member, before, after):
    # TODO: only add during set time
    bot.morning_club.add(member)


if __name__ == "__main__":
    bot.run(config["token"])
