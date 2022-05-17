import operator
import os

import discord
import requests
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv

# This is added so that many files can reuse the function get_database()
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PRODUCTION = os.getenv("PRODUCTION")

bot = None
if int(PRODUCTION) == 1:
    intents = discord.Intents(messages=True, message_content=True, guilds=True, guild_messages=True)
    bot = commands.Bot(command_prefix="!", intents=intents)
else:
    bot = commands.Bot(command_prefix="!")

print(BOT_TOKEN)


def get_database():
    # Provide the MongoDB atlas url to connect Python to MongoDB using PyMongo
    CONNECTION_STRING = os.getenv("CONNECTION_STRING")

    # Create a connection using MongoClient.
    client = MongoClient(CONNECTION_STRING)

    # Create the database
    return client['users']


# Method to update all of the scores.
def update(accounts_reference=None):
    # file = open("accounts.csv", "r")

    # Key: leetcode username | Value: discord id
    accounts = {}

    database = get_database()
    users_collection = database["users"].find()
    users_list = list(users_collection)
    for user in users_list:
        accounts[user["leetcode_username"]] = user["discord_id"]
    print(users_list)
    print(accounts)

    # Pass reference of accounts (a dictionary from leetcode username to discord user id) to create a copy
    if accounts_reference is not None:
        for accountKeys in accounts.keys():
            accounts_reference[accountKeys] = accounts[accountKeys]

    accounts = accounts.keys()
    score_totals = {}
    for account in accounts:
        apiUrl = 'https://leetcode.com/graphql?query='
        query = """
            { matchedUser(username: """ + '"' + account + '"' + """) {
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
        a = dict(requests.get(apiUrl + query).json())
        user_data_parsed = a['data']['matchedUser']['submitStats']['acSubmissionNum']
        easy = user_data_parsed[1]['count']
        medium = user_data_parsed[2]['count']
        hard = user_data_parsed[3]['count']
        # (easySolved * 1) + (mediumSolved * 3) + (hardSolved * 5)
        total = easy + (3 * medium) + (5 * hard)
        score_totals[account] = total
        print(score_totals)

    return score_totals


@bot.command()
async def top(ctx):
    accounts = {}
    # Pass a reference to accounts
    score_totals = update(accounts)

    count = 1  # Leaderboard position
    leaderboard = ""
    # Sort data by the total score values, from greatest to least
    sorted_score_totals = sorted(score_totals.items(), reverse=True, key=operator.itemgetter(1))
    for element in sorted_score_totals:
        leaderboard += (str(count) + ". " + str(await bot.fetch_user(accounts[str(element[0])])) + ": " + str(
            element[1]) + " " + "\n")
        count += 1
    await ctx.send(leaderboard)


@bot.command()
async def link(ctx, new_account):
    new_account = str(new_account)
    database = get_database()
    # print("Current user in database: " + list(database["users"].find({"discord_id" : ctx.author.id})))
    # If the user exists in the database, then they have already linked an account
    if list(database["users"].find({"discord_id": ctx.author.id})):
        await ctx.send("You already linked an account")
    # If the status is "error," then the account does not exist (or some other issue has occurred)
    elif dict(requests.get("https://leetcode-stats-api.herokuapp.com/" + new_account).json())["status"] == "error":
        await ctx.send("Error while linking account")
    # If the status is not error, then the account has been successfully found in the database and is added to the file
    else:
        new_user = {
            "leetcode_username": new_account,
            "discord_id": ctx.author.id
        }
        database["users"].insert_one(new_user)
        await ctx.send("Set Leetcode account for " + str(ctx.author) + " to " + new_account)


@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


bot.run(BOT_TOKEN)
