# Rise and Grind

**Setup**

Install the dependencies (developed and tested with Python3.11):
```
pip install -r requirements.txt
```

We'll also need to make sure the discord bot and postgres server are set up. These will be used to fill `.env` (which should be copied from `.env.example`):

1. Create a postgres database server (using something like supabase or vercel). All the credentials needed to populate the `DB_XXX vars should be fetchable from the console.
2. Create the discord bot app in the discord developer console. Under the "Bot" tab, you should be able to copy the token for the bot. This should be set to `DISCORD_TOKEN`.
3. Add the bot to the discord which you should be able to do under "Bot > Url Generator". Set it with "Bot" and "Admin" priveleges. Add the bot to the desired server. Finally, in discord, get the ID of the desired server (right click it's icon and pick "Copy ID") and use that to populate `DISCORD_GUILD`.

**Run:**

```shell
python bot.py
```

**Docker:**

```shell
docker build -t rise-and-grind .
docker run -it --rm rise-and-grind
```

**Deploy:**
Using [fly.io](https://fly.io) to freely host the bot, we can run:

```shell
fly deploy
```
