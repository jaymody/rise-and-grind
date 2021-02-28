import os
import json
import asyncio
import argparse
import datetime

import asyncpg
import discord
from discord.ext import commands
from discord.utils import find

from utils import current_time, current_date, in_time_range, is_a_weekend


class RiseNGrind(commands.Cog):
    def __init__(self, bot, guild_id, db_name, db_user, db_pass, db_host, db_port):
        self.bot = bot
        self.guild_id = guild_id
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_port = db_port

        self.guild = None
        self.chat = None
        self.voice = None
        self.members = None
        self.db = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Loads guild, chat, and voice. Attempts to infer voice and chat channels."""
        # check if bot has already been initialized
        if self.guild:
            return

        # find the current guild
        self.guild = find(lambda x: x.id == self.guild_id, bot.guilds)
        self.chat = find(
            lambda x: isinstance(x, discord.TextChannel)
            and x.name.lower() == "morning-club",
            self.guild.channels,
        )
        self.voice = find(
            lambda x: isinstance(x, discord.VoiceChannel)
            and x.name.lower() == "morning-club",
            self.guild.channels,
        )
        self.members = {}

        # database connector
        self.db = await asyncpg.connect(
            database=self.db_name,
            user=self.db_user,
            password=self.db_pass,
            host=self.db_host,
            port=self.db_port,
        )

        # TODO: add logger for the db stuff
        # create tables if they don't exist
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS members (
            mid BIGINT NOT NULL,
            start_time TIME(0) NOT NULL,
            end_time TIME(0) NOT NULL,
            active BOOLEAN NOT NULL,
            weekends BOOLEAN NOT NULL,
            PRIMARY KEY (mid)
        );
        """
        )
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS mornings (
            mid BIGINT NOT NULL,
            date DATE NOT NULL,
            woke_up BOOLEAN NOT NULL DEFAULT false,
            FOREIGN KEY (mid) REFERENCES members ON DELETE CASCADE,
            PRIMARY KEY (mid, date)
        );
        """
        )
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS configs (
            cid INTEGER NOT NULL,
            text_channel BIGINT,
            voice_channel BIGINT,
            PRIMARY KEY (cid)
        );
        """
        )

        self.chat = None
        self.voice = None

        config = await self.db.fetchrow(f"SELECT * FROM configs WHERE cid = 0;")
        if not config:  # create blank config entry if it does not exists
            await self.db.execute("""INSERT INTO configs (cid) values (0);""")
        else:  # otherwise load from config
            if config["text_channel"]:
                self.chat = find(
                    lambda x: x.id == config["text_channel"], self.guild.channels
                )
            if config["voice_channel"]:
                self.voice = find(
                    lambda x: x.id == config["voice_channel"], self.guild.channels
                )

        print("ready!")

    async def close(self):
        """Closes bot stuff"""
        await self.db.close()

    @commands.command(brief="Shuts down the bot", pass_context=False)
    async def shutdown(self, ctx):
        """Shuts down the bot"""
        await self.close()
        await bot.close()

    @commands.command(brief="Temp test command for db.")
    async def query(self, ctx):
        result = await self.db.fetch("SELECT * FROM members")
        await ctx.channel.send(result)

    @commands.command(brief="Temp test command for db.")
    async def insert(self, ctx, i: int):
        async with self.db.transaction():
            await self.db.execute(
                "INSERT INTO members "
                "(mid, start_time, end_time, active, weekends) "
                f"VALUES ({i}, '06:00:00', '06:30:30', false, false);"
            )

            await ctx.channel.send("insert to table successful")

    @commands.command(brief="Activate tracking for a user")
    async def activate(self, ctx, user: discord.Member):
        """Activate tracking for a user

        Examples
        --------
        !activate @janedoe
        """
        if user not in self.members:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return

        if self.members[user]["active"]:
            await ctx.channel.send(f"{user.display_name} is already active")
            return

        self.members[user]["active"] = True
        await ctx.channel.send(f"{user.display_name} is now active")
        while True:
            #### CAUTION ####
            # TODO: this loop logic is eye bleach, it is very very bad
            # ideally, you wanna use something built into discord.py
            # like tasks.loop or something similar

            # wait for a valid interval to occur
            while (
                not in_time_range(
                    self.members[user]["start_time"],
                    current_time(),
                    self.members[user]["end_time"],
                )
                or (not self.members[user]["weekends"] and is_a_weekend(current_date()))
            ) and self.members[user]["active"]:
                await asyncio.sleep(20)

            # during a valid time interval, check if user joins the voice channel
            while (
                in_time_range(
                    self.members[user]["start_time"],
                    current_time(),
                    self.members[user]["end_time"],
                )
                and self.members[user]["active"]
            ):
                # say good morning if they've joined the voice channel (only do it once)
                if user in self.voice.members and not self.members[user]["woke_up"]:
                    self.members[user]["woke_up"] = True
                    await self.chat.send(f"Good morning {user.mention}!")
                await asyncio.sleep(20)

            # if deactivate was called stop the loop and reset vars
            if not self.members[user]["active"]:
                self.members[user]["active"] = False
                self.members[user]["woke_up"] = False
                return

            # if they never joined the voice channel, then send an passive aggressive message
            if not self.members[user]["woke_up"]:
                await self.chat.send(
                    f"{user.mention}, you didn't wake up today eh. Big lack."
                )

            # reset variable that tracks if they woke up (ie joined the voice channel)
            self.members[user]["woke_up"] = False

    @commands.command(brief="Deactivate tracking for a user")
    async def deactivate(self, ctx, user: discord.Member):
        """Deactivate tracking for a user

        Examples
        --------
        !deactivate @janedoe
        """
        if user not in self.members:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return

        if not self.members[user]["active"]:
            await ctx.channel.send(f"{user.display_name} is already inactive")
            return

        self.members[user]["active"] = False
        await ctx.channel.send(
            "deactivating may take up to a minute, "
            f"use '!info {user.display_name}' after a minute check if they were deactivated"
        )

    @commands.command(brief="Add user to the morning club")
    async def add(
        self,
        ctx,
        user: discord.Member,
        start_time: str,
        end_time: str,
        weekends: bool,
    ):
        """Adds user to the morning club

        Examples
        --------
        !add @janedoe 06:30:00 7:00:00 yes
        !add @janedoe 12:00:00 13:00:00 no
        """
        _exists = await self.db.fetch(f"SELECT * FROM members WHERE mid = $1;", user.id)
        if _exists:
            await ctx.channel.send(
                f"{user.display_name} is already in the club, please use the "
                "update command instead"
            )
            return

        try:
            start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
            end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
        except ValueError as e:
            await ctx.channel.send(e)
            return

        async with self.db.transaction():
            await self.db.execute(
                "INSERT INTO members "
                "(mid, start_time, end_time, active, weekends) "
                f"VALUES ($1, $2, $3, false, $4);",
                user.id,
                start_time,
                end_time,
                weekends,
            )
        await ctx.channel.send(f"Welcome to the club {user.display_name}!")

    @commands.command(brief="Remove user from the morning club")
    async def remove(self, ctx, user: discord.Member):
        """Remove user from the morning club

        Examples
        --------
        !remove @janedoe
        """
        _exists = await self.db.fetch(f"SELECT * FROM members WHERE mid = $1;", user.id)
        if not _exists:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return

        async with self.db.transaction():
            await self.db.execute(
                "DELETE FROM members WHERE mid = $1;",
                user.id,
            )

        await ctx.channel.send(f"{user.display_name} left the club ;(")

    @commands.command(brief="Get morning club info")
    async def info(self, ctx, user: discord.Member = None):
        """Get info about the morning club

        Examples
        --------
        !info

        !info @janedoe
        """
        if not user:
            message = (
                "**--- Morning Club Info ---**\n"
                f"**Voice Channel:** {self.voice.name}\n"
                f"**Chat Channel:** {self.chat.name}\n"
                f"**Members:** {', '.join([x.display_name for x in self.members])}\n"
            )
        else:
            if user not in self.members:
                await ctx.channel.send(f"{user.display_name} is not a member")
                return
            message = f"**--- {user.display_name} ---**\n{json.dumps(self.members[user], indent=2, default=str)}"
        await ctx.channel.send(message)

    @commands.command(brief="Set text channel")
    async def set_text_channel(self, ctx, chat: discord.TextChannel):
        """Set text channel

        Examples
        --------
        !set_text_channel #text-channel
        """
        self.chat = chat
        await ctx.channel.send(f"text channel set to {self.chat.name}")

    @commands.command(brief="Set voice channel")
    async def set_voice_channel(self, ctx, voice: discord.VoiceChannel):
        """Set voice channel

        Examples
        --------
        !set_voice_channel <#VOICE_CHANNEL_ID>
        """
        self.voice = voice
        await ctx.channel.send(f"text channel set to {self.voice.name}")


if __name__ == "__main__":
    # cli
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if args.dev:
        os.environ["DISCORD_GUILD"] = os.environ["TEST_DISCORD_GUILD"]

    # discord bot
    # TODO: only use necessary intents
    bot = commands.Bot(
        command_prefix="!",
        intents=discord.Intents().all(),
        description="Rise and grind!",
    )

    # register cog
    risengrind = RiseNGrind(
        bot=bot,
        guild_id=int(os.environ["DISCORD_GUILD"]),
        db_name=os.environ["DB_NAME"],
        db_user=os.environ["DB_USER"],
        db_pass=os.environ["DB_PASS"],
        db_host=os.environ["DB_HOST"],
        db_port=os.environ["DB_PORT"],
    )
    bot.add_cog(risengrind)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bot.start(os.environ["DISCORD_TOKEN"]))
    except KeyboardInterrupt:
        loop.run_until_complete(risengrind.close())
        loop.run_until_complete(bot.close())
        print("\n\ngraceful interrupt")
    finally:
        loop.close()
