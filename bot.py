import os
import time
import asyncio
import argparse
import datetime

import asyncpg
import discord
from discord.ext import commands, tasks
from discord.utils import find

from utils import current_time, current_datetime, in_time_range, is_a_weekend

# TODO
def check():
    # check that text and voice channels are set and valid
    # check that on_ready has run
    pass


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
        self.db = None
        self.loops = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Loads guild, chat, and voice. Attempts to infer voice and chat channels."""
        # check if bot has already been initialized
        if self.guild:
            return

        # find the current guild
        self.guild = find(lambda x: x.id == self.guild_id, bot.guilds)

        # database connector
        self.db = await asyncpg.create_pool(
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
            weekends BOOLEAN NOT NULL,
            active BOOLEAN NOT NULL DEFAULT false,
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
            notified BOOLEAN NOT NULL DEFAULT false,
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

        config = await self.db.fetchrow("SELECT * FROM configs WHERE cid = 0;")
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

        self.loops = {}
        members = await self.db.fetch("SELECT * FROM members;")
        for member in members:
            if member["active"]:
                user = self.bot.get_user(member["mid"])
                task = tasks.loop(count=1)(self.notify)
                self.loops[user] = task
                task.start(user, member)

        print(f"ready {current_datetime()}")

    async def close(self):
        """Closes bot stuff"""
        for l in self.loops.values():
            l.cancel()
        await self.db.close()

    @commands.command(brief="Shuts down the bot")
    async def shutdown(self, ctx):
        """Shuts down the bot"""
        await self.close()
        await bot.close()

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, before, after):
        today = current_datetime()
        # if not a voice join event
        if not (before.channel is None and after.channel is not None):
            return
        # if not the voice channel we care about
        if after.channel != self.voice:
            return
        # if user has not been activated
        if user not in self.loops:
            return

        async with self.db.acquire() as con:
            data = await con.fetchrow("SELECT * FROM members WHERE mid = $1;", user.id)
            if not data:
                return

            morning = await con.fetchrow(
                "SELECT * FROM mornings WHERE mid=$1 AND date=$2",
                user.id,
                today,
            )
            if not morning:
                async with con.transaction():
                    await con.execute(
                        "INSERT INTO mornings (mid, date) VALUES ($1, $2);",
                        user.id,
                        today,
                    )
                    morning = await con.fetchrow(
                        "SELECT * FROM mornings WHERE mid=$1 AND date=$2",
                        user.id,
                        today,
                    )

            if (
                in_time_range(data["start_time"], current_time(), data["end_time"])
                and not morning["notified"]
                and not morning["woke_up"]
            ):
                async with con.transaction():
                    await con.execute(
                        "UPDATE mornings SET woke_up=true, notified=true "
                        "WHERE mid=$1 AND date=$2;",
                        user.id,
                        today,
                    )
                    await self.chat.send(f"Good morning {user.mention}!")

    async def notify(self, user, data):
        """Main notify logic."""
        # TODO: add weekend logic
        while True:
            today = current_datetime()
            # wait until tomorrow at end time, I should probably unit test this ...
            # number of seconds from midnight to end time
            diff = (
                datetime.datetime.combine(datetime.date.min, data["end_time"])
                - datetime.datetime.min
            )
            # datetime of tomorrow at end_time (+ 10 seconds for good measure)
            tmrw = (
                today.replace(hour=0, minute=0, second=0, microsecond=0)
                + diff
                + datetime.timedelta(days=1, seconds=10)
            )
            # number of seconds between tmrw and today
            seconds = (tmrw - today).total_seconds()
            if seconds > 0:
                await asyncio.sleep(seconds)

            # NOTE: since the process has been slept for about a day, tmrw is going to be
            # the current date most likely, unless end_time is very close to midnight
            # in which case tmrw may be the previous day in which case we have to
            # use that date when updating mornings
            async with self.db.acquire() as con:
                morning = await con.fetchrow(
                    "SELECT * FROM mornings WHERE mid=$1 AND date=$2",
                    user.id,
                    tmrw,
                )
                if not morning:
                    async with con.transaction():
                        await con.execute(
                            "INSERT INTO mornings (mid, date) VALUES ($1, $2);",
                            user.id,
                            tmrw,
                        )
                        morning = await con.fetchrow(
                            "SELECT * FROM mornings WHERE mid=$1 AND date=$2",
                            user.id,
                            tmrw,
                        )

                # if they haven't woke up, send a passive aggressive message
                if not morning["notified"]:
                    async with con.transaction():
                        await con.execute(
                            "UPDATE mornings SET notified=true WHERE mid=$1 AND date=$2;",
                            user.id,
                            tmrw,
                        )
                    await self.chat.send(
                        f"{user.mention}, you didn't wake up today eh. Big lack."
                    )

    @commands.command(brief="Activate tracking for a user")
    async def activate(self, ctx, user: discord.Member):
        """Activate tracking for a user

        Examples
        --------
        !activate @janedoe
        """
        async with self.db.acquire() as con:
            data = await con.fetchrow("SELECT * FROM members WHERE mid = $1;", user.id)

        if not data:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return

        if user in self.loops:
            await ctx.channel.send(f"{user.display_name} is already active")
            return

        task = tasks.loop(count=1)(self.notify)
        self.loops[user] = task
        task.start(user, data)

        async with self.db.acquire() as con:
            async with con.transaction():
                await con.execute(
                    "UPDATE members SET active=true WHERE mid=$1;",
                    user.id,
                )

        await ctx.channel.send(f"{user.display_name} is now active")

    @commands.command(brief="Deactivate tracking for a user")
    async def deactivate(self, ctx, user: discord.Member):
        """Deactivate tracking for a user

        Examples
        --------
        !deactivate @janedoe
        """
        async with self.db.acquire() as con:
            data = await con.fetchrow("SELECT * FROM members WHERE mid = $1;", user.id)

        if not data:
            await ctx.channel.send(f"{user.display_name} is not a member")
            return

        if user not in self.loops:
            await ctx.channel.send(f"{user.display_name} is already inactive")
            return

        self.loops[user].cancel()
        del self.loops[user]

        async with self.db.acquire() as con:
            async with con.transaction():
                await con.execute(
                    "UPDATE members SET active=false WHERE mid=$1;",
                    user.id,
                )

        await ctx.channel.send(f"{user.display_name} has been deactivated")

    @commands.command(brief="Fetch mornings data")
    async def data(self, ctx, verbose: bool = None):
        """Fetch mornings data
        Usage
        -----
        !data <send_as_message (optional)>

        If send as message is set, (yes/t/y/true), then the data is sent as a
        message

        If it is not set, the data is sent as a csv file

        Examples
        --------
        !data

        !data yes
        """
        async with self.db.acquire() as con:
            await con.copy_from_query(
                "SELECT * FROM mornings",
                output="data.csv",
                format="csv",
                header=True,
            )
        if verbose:
            with open("data.csv") as fi:
                await ctx.channel.send(fi.read())
        else:
            await ctx.channel.send(file=discord.File("data.csv"))

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
        async with self.db.acquire() as con:
            _exists = await con.fetchrow(
                "SELECT * FROM members WHERE mid = $1;", user.id
            )
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

            async with con.transaction():
                await con.execute(
                    "INSERT INTO members "
                    "(mid, start_time, end_time, weekends) "
                    "VALUES ($1, $2, $3, $4);",
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
        async with self.db.acquire() as con:
            _exists = await con.fetchrow(
                "SELECT * FROM members WHERE mid = $1;", user.id
            )
            if not _exists:
                await ctx.channel.send(f"{user.display_name} is not a member")
                return

            if user in self.loops:
                await ctx.channel.send(
                    f"please deactivate {user.display_name}  before removing"
                )
                return

            async with con.transaction():
                await con.execute(
                    "DELETE FROM members WHERE mid = $1;",
                    user.id,
                )

        await ctx.channel.send(f"{user.display_name} left the club ;(")

    @commands.command(brief="Update user settings")
    async def update(
        self,
        ctx,
        user: discord.Member,
        start_time: str,
        end_time: str,
        weekends: bool,
    ):
        """Update user settings

        Examples
        --------
        !update @janedoe 06:30:00 7:00:00 yes
        !update @janedoe 12:00:00 13:00:00 no
        """
        async with self.db.acquire() as con:
            _exists = await con.fetchrow(
                "SELECT * FROM members WHERE mid = $1;", user.id
            )
            if not _exists:
                await ctx.channel.send(f"{user.display_name} is not a member")
                return

            if user in self.loops:
                await ctx.channel.send(
                    f"please deactivate {user.display_name} before updating"
                )
                return

            try:
                start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
                end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
            except ValueError as e:
                await ctx.channel.send(e)
                return

            async with con.transaction():
                await con.execute(
                    "UPDATE members "
                    "SET start_time=$1, end_time=$2, weekends=$3 "
                    "WHERE mid = $4;",
                    start_time,
                    end_time,
                    weekends,
                    user.id,
                )

        await ctx.channel.send(f"settings have been updated for {user.display_name}")

    @commands.command(brief="Get morning club info")
    async def info(self, ctx, user: discord.Member = None):
        """Get info about the morning club

        Examples
        --------
        !info

        !info @janedoe
        """
        # TODO: prettier info stuff
        async with self.db.acquire() as con:
            if not user:
                message = "Config: "
                message += str(await con.fetchrow("SELECT * FROM configs WHERE cid=0;"))
                message += "\n\nActive Members: "
                message += str([k.display_name for k in self.loops])
                message += "\n\nMembers: "
                message += str(await con.fetch("SELECT * FROM members;"))
            else:
                data = await con.fetchrow(
                    "SELECT * FROM members WHERE mid = $1;", user.id
                )
                if not data:
                    await ctx.channel.send(f"{user.display_name} is not a member")
                    return
                message = str(data)
        await ctx.channel.send(message)

    @commands.command(brief="Set text channel")
    async def set_text_channel(self, ctx, chat: discord.TextChannel):
        """Set text channel

        Examples
        --------
        !set_text_channel #text-channel
        """
        async with self.db.acquire() as con:
            async with con.transaction():
                await con.execute(
                    "UPDATE configs SET text_channel=$1 WHERE cid=0;", chat.id
                )
        self.chat = chat
        await ctx.channel.send(f"text channel set to {self.chat.name}")

    @commands.command(brief="Set voice channel")
    async def set_voice_channel(self, ctx, voice: discord.VoiceChannel):
        """Set voice channel

        Examples
        --------
        !set_voice_channel <#VOICE_CHANNEL_ID>
        """
        async with self.db.acquire() as con:
            async with con.transaction():
                await con.execute(
                    "UPDATE configs SET voice_channel=$1 WHERE cid=0;", voice.id
                )
        self.voice = voice
        await ctx.channel.send(f"voice channel set to {self.voice.name}")


if __name__ == "__main__":
    # cli
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if args.dev:
        os.environ["DISCORD_GUILD"] = os.environ["TEST_DISCORD_GUILD"]

    # set timezone
    if "TZ" not in os.environ:
        os.environ["TZ"] = "UTC"
    time.tzset()

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
