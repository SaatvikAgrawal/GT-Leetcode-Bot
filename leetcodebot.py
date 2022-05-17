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
CLIENT = MongoClient(CONNECTION_STRING)

bot = None
if int(PRODUCTION) == 1:
    intents = discord.Intents(
        messages=True, message_content=True, guilds=True, guild_messages=True
    )
    bot = commands.Bot(command_prefix="!", intents=intents)
else:
    bot = commands.Bot(command_prefix="!")


def get_database():
    return CLIENT["users"]


def call_leetcode_api(username):
    api_url = "https://leetcode.com/graphql?query="
    query = """
        {{ 
            matchedUser(username: "{0}") {{
                username
                submitStats: submitStatsGlobal {{
                    acSubmissionNum {{
                        difficulty
                        count
                        submissions
                    }}
                }}
            }}
        }}
    """.format(username)

    return dict(requests.get(api_url + query).json())


# Method to get scores.
def get_scores():
    # Key: discord id, Value: score
    score_totals = {}

    database = get_database()
    users_collection = database["users"].find()
    users_list = list(users_collection)

    for user in users_list:

        response = call_leetcode_api(user["leetcode_username"])

        user_submissions_data = response["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
        easy = user_submissions_data[1]["count"]
        medium = user_submissions_data[2]["count"]
        hard = user_submissions_data[3]["count"]

        score = easy + (3 * medium) + (5 * hard)

        score_totals[user["discord_id"]] = score

    return score_totals


@bot.command()
async def top(ctx):
    score_totals = get_scores()

    position_no = 1
    leaderboard = ""

    # Sort data by the total score values, from greatest to least
    sorted_score_totals = sorted(score_totals.items(), reverse=True, key=operator.itemgetter(1))

    for score in sorted_score_totals:
        leaderboard += f"{str(position_no)}. {str(await bot.fetch_user(score[0]))}: {str(score[1])} \n"
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
        new_user = {"leetcode_username": account_name, "discord_id": ctx.author.id}
        database["users"].insert_one(new_user)
        await ctx.send(f"Set Leetcode account for {str(ctx.author)} to {account_name}")


@bot.event
async def on_ready():
    print("We have logged in as {0.user}".format(bot))


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


bot.run(BOT_TOKEN)
