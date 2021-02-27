# Rise and Grind

**Dependencies**

Requires python 3.9+
```
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Run:**

```shell
python bot.py
python bot.py --dev # dev mode (ie use test guild)
```

**Deploy:**

```
git push heroku master
heroku restart # if you need to restart the app
heroku config:set SOME_ENV_VAR=some_value # for setting env vars in the deployment
```
