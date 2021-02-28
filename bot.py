import os
import json
import asyncio
import argparse
import datetime

import discord
from discord.ext import commands
from discord.utils import find

from utils import current_time, in_time_range

# dev/test mode
parser = argparse.ArgumentParser()
parser.add_argument("--dev", action="store_true")
args = parser.parse_args()
if args.dev:
    os.environ["DISCORD_GUILD"] = os.environ["TEST_DISCORD_GUILD"]

# TODO: only use necessary intents
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Loads guild, chat, and voice. Attempts to infer voice and chat channels."""
    bot.guild = find(lambda x: x.id == int(os.environ["DISCORD_GUILD"]), bot.guilds)
    bot.chat = find(
        lambda x: isinstance(x, discord.TextChannel)
        and x.name.lower() == "morning-club",
        bot.guild.channels,
    )
    bot.voice = find(
        lambda x: isinstance(x, discord.VoiceChannel)
        and x.name.lower() == "morning-club",
        bot.guild.channels,
    )
    bot.members = {}
    print("ready!")


@bot.command(brief="Shuts down the bot")
async def shutdown(ctx):
    """Shuts down the bot"""
    await bot.logout()


@bot.command(brief="Activate tracking for a user")
async def activate(ctx, user: discord.Member):
    """Activate tracking for a user

    Examples
    --------
    !activate @janedoe
    """
    if user not in bot.members:
        await ctx.channel.send(f"{user.display_name} is not a member")
        return

    if bot.members[user]["active"]:
        await ctx.channel.send(f"{user.display_name} is already active")
        return

    bot.members[user]["active"] = True
    await ctx.channel.send(f"{user.display_name} is now active")
    while True:
        # TODO: this loop logic is eye bleach, I should replace it
        # ideally, you wanna use something built into discord.py
        # like tasks.loop or something similar
        # TODO: add logic for weekends

        # wait for time interval to occur
        while (
            not in_time_range(
                bot.members[user]["start_time"],
                current_time(),
                bot.members[user]["end_time"],
            )
            and bot.members[user]["active"]
        ):
            await asyncio.sleep(10)

        # during time interval, check if user joins the voice channel
        while (
            in_time_range(
                bot.members[user]["start_time"],
                current_time(),
                bot.members[user]["end_time"],
            )
            and bot.members[user]["active"]
        ):
            # say good morning if they've joined the voice channel (only do it once)
            if user in bot.voice.members and not bot.members[user]["woke_up"]:
                bot.members[user]["woke_up"] = True
                await bot.chat.send(f"Good morning {user.mention}!")
            await asyncio.sleep(10)

        # if deactivate was called stop the loop and reset vars
        if not bot.members[user]["active"]:
            bot.members[user]["active"] = False
            bot.members[user]["woke_up"] = False
            return

        # if they never joined the voice channel, then send an passive aggressive message
        if not bot.members[user]["woke_up"]:
            await bot.chat.send(
                f"{user.mention}, you didn't wake up today eh. Big lack."
            )

        # reset variable that tracks if they woke up (ie joined the voice channel)
        bot.members[user]["woke_up"] = False


@bot.command(brief="Deactivate tracking for a user")
async def deactivate(ctx, user: discord.Member):
    """Deactivate tracking for a user

    Examples
    --------
    !deactivate @janedoe
    """
    if user not in bot.members:
        await ctx.channel.send(f"{user.display_name} is not a member")
        return

    if not bot.members[user]["active"]:
        await ctx.channel.send(f"{user.display_name} is already inactive")
        return

    bot.members[user]["active"] = False
    await ctx.channel.send(
        "deactivating may take up to a minute, "
        f"use '!info {user.display_name}' after a minute check if they were deactivated"
    )


@bot.command(brief="Add user to the morning club")
async def add(
    ctx, user: discord.Member, start_time: str, end_time: str, weekends: bool
):
    """Adds user to the morning club

    Examples
    --------
    !add @janedoe 06:30:00 7:00:00 yes
    !add @janedoe 12:00:00 13:00:00 no
    """
    if user in bot.members:
        await ctx.channel.send(
            f"{user.display_name} is already in the club, please remove and "
            "re-add them if you want to change the settings"
        )
        return

    try:
        start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
        end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
    except ValueError as e:
        await ctx.channel.send(e)
        return

    bot.members[user] = {
        "weekends": weekends,
        "start_time": start_time,
        "end_time": end_time,
        "woke_up": False,
        "active": False,
    }
    await ctx.channel.send(f"Welcome to the club {user.display_name}!")


@bot.command(brief="Remove user from the morning club")
async def remove(ctx, user: discord.Member):
    """Remove user from the morning club

    Examples
    --------
    !remove @janedoe
    """
    if user not in bot.members:
        await ctx.channel.send(f"{user.display_name} is not a member")
        return

    if bot.members[user]["active"]:
        await ctx.channel.send(f"please deactivate {user.display_name} before removing")
        return

    del bot.members[user]
    await ctx.channel.send(f"{user.display_name} left the club ;(")


@bot.command(brief="Get morning club info")
async def info(ctx, user: discord.Member = None):
    """Get info about the morning club

    Examples
    --------
    !info

    !info @janedoe
    """
    if not user:
        message = (
            "**--- Morning Club Info ---**\n"
            f"**Voice Channel:** {bot.voice.name}\n"
            f"**Chat Channel:** {bot.chat.name}\n"
            f"**Members:** {', '.join([x.display_name for x in bot.members])}\n"
        )
    else:
        if user not in bot.members:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return
        message = f"**--- {user.display_name} ---**\n{json.dumps(bot.members[user], indent=2, default=str)}"
    await ctx.channel.send(message)


@bot.command(brief="Set text channel")
async def set_text_channel(ctx, chat: discord.TextChannel):
    """Set text channel

    Examples
    --------
    !set_text_channel #text-channel
    """
    bot.chat = chat
    await ctx.channel.send(f"text channel set to {bot.chat.name}")


@bot.command(brief="Set voice channel")
async def set_voice_channel(ctx, voice: discord.VoiceChannel):
    """Set voice channel

    Examples
    --------
    !set_voice_channel <#VOICE_CHANNEL_ID>
    """
    bot.voice = voice
    await ctx.channel.send(f"text channel set to {bot.voice.name}")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
