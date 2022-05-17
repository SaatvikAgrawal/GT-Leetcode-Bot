import operator
import os

import discord
import requests
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PRODUCTION = os.getenv("PRODUCTION")
CONNECTION_STRING = os.getenv("CONNECTION_STRING")

print(CONNECTION_STRING)

bot = None
if int(PRODUCTION) == 1:
    intents = discord.Intents(messages=True, message_content=True, guilds=True, guild_messages=True)
    bot = commands.Bot(command_prefix="!", intents=intents)
else:
    bot = commands.Bot(command_prefix="!")


def get_database():
    # Create a connection using MongoClient
    client = MongoClient(CONNECTION_STRING)

    # Create the database
    return client['users']


def call_leetcode_api(username):
    api_url = 'https://leetcode.com/graphql?query='
    query = """
        { matchedUser(username: """ + '"' + username + '"' + """) {
        username
        submitStats: submitStatsGlobal {
        acSubmissionNum {
        difficulty
        count
        submissions
        }
        }
        }
        }
    """
    return dict(requests.get(api_url + query).json())


# Method to update all of the scores.
def update(accounts_reference=None):
    # Key: leetcode username | Value: discord id
    accounts = {}

    database = get_database()
    users_collection = database["users"].find()
    users_list = list(users_collection)
    for user in users_list:
        accounts[user["leetcode_username"]] = user["discord_id"]

    # Pass reference of accounts (a dictionary from leetcode username to discord user id) to create a copy
    if accounts_reference is not None:
        for accountKeys in accounts.keys():
            accounts_reference[accountKeys] = accounts[accountKeys]

    account_names = accounts.keys()
    # maps leetcode username to score
    score_totals = {}
    for account in account_names:

        response = call_leetcode_api(account)
        user_data_parsed = response['data']['matchedUser']['submitStats']['acSubmissionNum']
        easy = user_data_parsed[1]['count']
        medium = user_data_parsed[2]['count']
        hard = user_data_parsed[3]['count']

        total = easy + (3 * medium) + (5 * hard)
        score_totals[account] = total
        print(score_totals)

    return score_totals


@bot.command()
async def top(ctx):
    # Key: leetcode username | Value: discord id
    accounts = {}

    # Pass a reference to accounts
    score_totals = update(accounts)

    position_no = 1
    leaderboard = ""

    # Sort data by the total score values, from greatest to least
    sorted_score_totals = sorted(score_totals.items(), reverse=True, key=operator.itemgetter(1))

    for score in sorted_score_totals:
        leaderboard += (str(position_no) + ". " + str(await bot.fetch_user(accounts[str(score[0])])) + ": " + str(
            score[1]) + " " + "\n")
        position_no += 1
    await ctx.send(leaderboard)


@bot.command()
async def link(ctx, account_name):
    # Name of leetcode account to add to the database
    account_name = str(account_name)
    database = get_database()

    # If the user already exists
    if list(database["users"].find({"discord_id": ctx.author.id})):
        await ctx.send("You already linked an account")

    # If the status is "error," then the account does not exist (or some other issue has occurred)
    elif "errors" in call_leetcode_api(account_name):
        await ctx.send("Error while linking account")

    # If account is valid and not in database, add to database
    else:
        new_user = {
            "leetcode_username": account_name,
            "discord_id": ctx.author.id
        }
        database["users"].insert_one(new_user)
        await ctx.send(f"Set Leetcode account for {str(ctx.author)} to {account_name}")


@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


bot.run(BOT_TOKEN)
