from datetime import datetime, timezone
from discord import Intents, Interaction, Embed, Colour, Message
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
import discord
import os
from dotenv import load_dotenv
from settings import Fields, ID, Emoji, Constant
import database
from database import Gambler, Bet
from embed_messages import EmbedMessages, BetButtons
from typing import List

# Initialize the bot
load_dotenv()
token = os.getenv("DC_BOT_TOKEN")
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()

        # Register persistent views
        all_bets = database.get_all_bets()  # Fetch all saved messages
        for bet in all_bets:
            if bet.deadline.astimezone(timezone.utc) > datetime.now(timezone.utc):
                view = BetButtons(bet)
                bot.add_view(view, message_id=bet.message_id)  # Attach persistent view to a message

        print(f"Bot is ready. Logged in as {bot.user}")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def reload_bet_message(bet: Bet):
    channel = bot.get_channel(ID.Channels.MAC_BILDIRIM)
    if bet.deadline.astimezone(timezone.utc) > datetime.now(timezone.utc):
        message = await channel.fetch_message(bet.message_id)
        # Add a persistent view for this message
        view = BetButtons(bet)
        bot.add_view(view, message_id=bet.message_id)



# ------------------------------- PLACE BET -------------------------------#
@bot.tree.command(name="bet", description="Place your guess on a bet from the given list.")
@app_commands.describe(
    bet_id="Select the match you want to bet on.",
    bet_on="Your guess: 1 for Home, 0 for Draw, 2 for Away, 3 for Withdraw",
)
async def place_bet(interaction: Interaction, bet_id: int, bet_on: int):
    if not await isRegisteredUser(interaction=interaction):
        return
    required_roles_id_list = [ID.Roles.ADMIN, ID.Roles.GAMBLER]
    if not await isAuthorisedUser(interaction=interaction, allowed_roles_id_list=required_roles_id_list):
        return
    required_channel_id_list = [ID.Channels.MAC_BILDIRIM, ID.Channels.ADMIN]
    if not await isAuthorisedChannel(interaction=interaction, allowed_channels_id_list=required_channel_id_list):
        return
        
    try:
        await process_bet(
            interaction=interaction,
            gambler_id=interaction.user.id,
            bet_id=bet_id,
            bet_on=bet_on,
        )
    except Exception as e:
        print(e)

@place_bet.autocomplete("bet_on")
async def place_bet_bet_on_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    bet_id = interaction.namespace.bet_id  # Access previously entered bet_id
    if bet_id is None:
        return []
    try:
        bet: Bet = database.get_bet(bet_id=bet_id)
        options = [
            app_commands.Choice(name=f"{bet.home_team} ({bet.odd_1})", value=1),
            app_commands.Choice(name=f"Draw ({bet.odd_0})", value=0),
            app_commands.Choice(name=f"{bet.away_team} ({bet.odd_2})", value=2),
            app_commands.Choice(name="Indecisive (1.00)", value=3),
        ]
        return options
    except Exception as e:
        print(f"Error in bet_on_autocomplete: {e}")
        return []

@place_bet.autocomplete("bet_id")
async def place_bet_bet_id_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    try:
        available_bets: List[Bet] = database.get_all_bets()
        filtered_bets = [
            app_commands.Choice(
                name=f"({bet.field})   --->   {bet.home_team} - {bet.away_team}",
                value=bet.id,
            )
            for bet in available_bets
            if current.lower() in f"{bet.home_team} {bet.away_team}".lower()
            and bet.winning_odd not in Constant.BET_OUTCOMES
            and bet.deadline > datetime.now()
        ]
        # Return up to 25 results (Discord limit)
        return filtered_bets[:25]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []


# ------------------------------- PLACE BET AS ANYONE (ADMIN)-------------------------------#
@bot.tree.command(name="bet_as", description="Place a bet on behalf of a gambler.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
@app_commands.describe(
    bet_as="Select the gambler to bet on behalf of.",
    bet_id="Enter the ID of the match to bet on.",
    bet_on="Your guess: 1 for Home, 0 for Draw, 2 for Away",
)
async def place_bet_admin(interaction: Interaction, bet_as: str, bet_id: int, bet_on: int):
    try:
        await process_bet(
            interaction=interaction,
            gambler_id=int(bet_as),
            bet_id=bet_id,
            bet_on=bet_on,
            skip_timecheck=True
        )
    except Exception as e:
        await interaction.response.send_message(str(e), ephemeral=True)

@place_bet_admin.autocomplete("bet_as")
async def place_bet_bet_as_autocomplete(interaction: Interaction, current: str):
    gamblers: List[Gambler] = database.get_all_gamblers()
    gamblers.sort(key=lambda gambler: gambler.name.lower())
    return [
        Choice(name=gambler.name, value=str(gambler.id))
        for gambler in gamblers
        if current.lower() in str(gambler.name).lower()
    ][:25]

@place_bet_admin.autocomplete("bet_id")
async def place_bet_as_bet_id_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    isAdmin = ID.Roles.ADMIN in [role.id for role in interaction.user.roles]
    try:
        available_bets: List[Bet] = database.get_all_bets()
        filtered_bets = [
            app_commands.Choice(
                name=f"({bet.field})   --->   {bet.home_team} - {bet.away_team}",
                value=bet.id,
            )
            for bet in available_bets
            if current.lower() in f"{bet.home_team} {bet.away_team}".lower()
            and bet.winning_odd not in Constant.BET_OUTCOMES
            and (bet.deadline > datetime.now() or isAdmin)
        ]
        # Return up to 25 results (Discord limit)
        return filtered_bets[:25]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []

@place_bet_admin.autocomplete("bet_on")
async def place_bet_as_bet_on_autocomplete(interaction: Interaction, current: str):
    return await place_bet_bet_on_autocomplete(interaction, current)


# ------------------------------- CREATE BET -------------------------------#
@bot.tree.command(name="create", description="Create a new bet in the channel.")
@app_commands.describe(
    field="Select the field of the game.",
    home_team="Name of the home team.",
    away_team="Name of the away team.",
    odd_1="The odd for home team victory. (x >= 1.0)",
    odd_0="The odd for draw. (x >= 1.0, type 1.0 in case of inavailability.)",
    odd_2="The odd for away team victory. (x >= 1.0)",
    week="Enter the gambling week.",
    matchdate="The date which the match will take place in. The format has to be YYYY-MM-DD HH:MM",
)
async def create_bet(
    interaction: Interaction,
    field: str = None,
    home_team: str = None,
    away_team: str = None,
    odd_1: str = None,
    odd_0: str = None,
    odd_2: str = None,
    matchdate: str = None,
    week: str = None,
):
    required_role_id = ID.Roles.ADMIN
    if not await isAuthorisedUser(interaction=interaction, allowed_roles_id_list=required_role_id):
        return

    required_channel_id = ID.Channels.ADMIN
    if not await isAuthorisedChannel(interaction=interaction, allowed_channels_id_list=required_channel_id):
        return

    if not (odd_1 := await isCorrectOdd(interaction=interaction, odd=odd_1)):
        return
    if not (odd_0 := await isCorrectOdd(interaction=interaction, odd=odd_0)):
        return
    if not (odd_2 := await isCorrectOdd(interaction=interaction, odd=odd_2)):
        return

    if not (field and home_team and away_team and odd_1 and odd_0 and odd_2):
        await interaction.response.send_message(
            "Please use the command as follows: `/create field home_team away_team odd_1 odd_0 odd_2`\n"
            "Example: `/create Football TeamA TeamB 2.5 3.0 2.8`",
            ephemeral=True,
        )
        return

    try:
        # Parse the match date
        deadline_datetime = datetime.strptime(matchdate, "%Y-%m-%d %H:%M").astimezone(timezone.utc)
    except ValueError:
        await interaction.response.send_message(
            "Invalid datetime format. Please use YYYY-MM-DD HH:MM.",
            ephemeral=True,
        )
        return

    try:
        # Prepare data for the new bet
        cols = [column.name for column in Bet.__table__.columns]
        values = [None,None,field,home_team,away_team,odd_1,odd_0,odd_2,deadline_datetime,week,None]
        bet = {column: val for column, val in zip(cols, values)}

        # Create the bet in the database
        created_bet = database.add_bet(bet)

        # Send confirmation message to the admin channel
        await interaction.response.send_message(embed=EmbedMessages.bet_created_confirmation(created_bet), ephemeral=True)

        # Send the fancy announcement message to the mac-bildirim channel
        mac_bildirim_kanal = interaction.guild.get_channel(ID.Channels.MAC_BILDIRIM)
        if mac_bildirim_kanal:
            bet_message:Message = await mac_bildirim_kanal.send(embed=EmbedMessages.bet_created_announcement(created_bet), view=BetButtons(created_bet))
            database.set_bet_message_id(created_bet.id, bet_message.id)
        else:
            await interaction.followup.send("Announcement channel not found. Please check the bot's configuration.", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred while creating the bet: {str(e)}", ephemeral=True)
        return

@create_bet.autocomplete("field")
async def create_bet_field_autocomplete(interaction: Interaction, current: str):
    return [
        Choice(name=field, value=field)
        for field in Fields.ALL_FIELDS
        if current.lower() in field.lower()
    ]


# ------------------------------- SET RESULT -------------------------------#
@bot.tree.command(name="result", description="Set the result of a bet.")
@app_commands.describe(
    bet_id="Select the bet you want to set the result for.",
    result="Bet result: 1 for Home, 0 for Draw, 2 for Away",
)
async def set_bet_result(interaction: Interaction, bet_id: int, result: int):
    required_role_id = ID.Roles.ADMIN
    if not await isAuthorisedUser(
        interaction=interaction, allowed_roles_id_list=required_role_id
    ):
        return

    required_channel_id = ID.Channels.ADMIN
    if not await isAuthorisedChannel(
        interaction=interaction, allowed_channels_id_list=required_channel_id
    ):
        return

    try:
        # Update the bet result
        bet: Bet = database.set_bet_result(bet_id=bet_id, result=result)
        results = database.update_gamblers_on_bet_result(bet_id=bet_id)

        # Prepare the match result announcement
        result_text = (
            f"🎉 **Match Result Announcement!** 🎉\n\n"
            f"🏟️ **Field:** {bet.field}\n"
            f"⚽ **Match:** `{bet.home_team}` vs `{bet.away_team}`\n"
        )
        result_text += (
            f"🏆 **Final Result:** `{bet.home_team}` Wins 🏠\n"
            if result == 1
            else "🏆 **Final Result:** `Draw` 🤝\n"
            if result == 0
            else f"🏆 **Final Result:** `{bet.away_team}` Wins 🚩\n"
        )

        # Add gamblers' outcomes
        result_text += "\n📊 **Gamblers Performance:**\n"
        for gambler_result in results:
            result_text += f"- {gambler_result}\n"

        # Send the match result notification to the general channel
        mac_sonuc_channel = interaction.guild.get_channel(ID.Channels.MAC_SONUC)
        if not mac_sonuc_channel:
            raise ValueError("General channel not found.")
        
        await send_split_message(mac_sonuc_channel, result_text)
        database.update_weekly_stats(week_number=bet.week)
        await update_leaderboard(interaction=interaction, week=bet.week)
        await interaction.response.send_message(
            f"{bet} has resulted successfully. Gambler statistics and the leaderboard has been updated.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(str(e), ephemeral=True)

@set_bet_result.autocomplete("result")
async def set_bet_result_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    bet_id = interaction.namespace.bet_id  # Access previously entered bet_id
    if bet_id is None:
        return []
    try:
        bet = database.get_bet(bet_id=bet_id)
        options = [
            app_commands.Choice(name=f"{bet.home_team} ({bet.odd_1})", value=1),
            app_commands.Choice(name=f"Draw ({bet.odd_0})", value=0),
            app_commands.Choice(name=f"{bet.away_team} ({bet.odd_2})", value=2),
        ]
        return options
    except Exception as e:
        print(f"Error in bet_on_autocomplete: {e}")
        return []

@set_bet_result.autocomplete("bet_id")
async def set_bet_bet_id_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    try:
        available_bets: List[Bet] = database.get_all_bets()
        filtered_bets = [
            app_commands.Choice(
                name=f"({bet.field})   --->   {bet.home_team} - {bet.away_team}",
                value=bet.id,
            )
            for bet in available_bets
            if current.lower() in f"{bet.home_team} {bet.away_team}".lower()
            and bet.winning_odd not in Constant.BET_OUTCOMES
        ]
        # Return up to 25 results (Discord limit)
        return filtered_bets[:25]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []

# ------------------------------- GET STATS OF A BET -------------------------------#
@bot.tree.command(name="bet_stats", description="Get bet statistics.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
@app_commands.describe(
    bet_id="Enter the ID of the match to bet on.",
)
async def bet_stats(interaction: Interaction, bet_id: int):
    bet = database.get_bet(bet_id=bet_id)
    msg = [gambler.name for gambler in bet.gamblers]
    await interaction.response.send_message("\n".join(msg))
@bet_stats.autocomplete("bet_id")
async def bet_stats_bet_id_autocomplete(
    interaction: Interaction, current: str
) -> List[app_commands.Choice]:
    try:
        available_bets: List[Bet] = database.get_all_bets()
        filtered_bets = [
            app_commands.Choice(
                name=f"({bet.field})   --->   {bet.home_team} - {bet.away_team}",
                value=bet.id,
            )
            for bet in available_bets
            if current.lower() in f"{bet.home_team} {bet.away_team}".lower()
        ]
        # Return up to 25 results (Discord limit)
        return filtered_bets[:25]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []
    
# ------------------------------- GET MY BETS -------------------------------#
@bot.tree.command(name="me", description="Get your statistics.")
async def get_me(interaction: Interaction):
    if not await isRegisteredUser(interaction=interaction):
        return
    required_role_id = ID.Roles.GAMBLER
    if not await isAuthorisedUser(interaction=interaction, allowed_roles_id_list=required_role_id):
        return
    required_channel_id = ID.Channels.MAC_BILDIRIM
    if not await isAuthorisedChannel(interaction=interaction, allowed_channels_id_list=required_channel_id):
        return

    try:
        # Fetch gambler from the database
        gambler = database.get_gambler(gambler_dc_id=interaction.user.id)
        bets = database.get_gambler_bet_details(gambler_dc_id=interaction.user.id)

        if not bets:
            await interaction.response.send_message(
                embed=Embed(
                    title="No Bets Found",
                    description="You have not placed any bets yet. Start betting to see your statistics here!",
                    colour=Colour.orange()
                ),
                ephemeral=True
            )
            return

        # Create an embed for the gambler's stats and recent bets
        embed = Embed(
            title="Your Betting Stats",
            description=f"{gambler}",
            colour=Colour.blue()
        )
        embed.add_field(
            name="Recent Bets",
            value="\n".join(bets[-10:]) if bets else "No recent bets.",
            inline=False
        )
        embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.set_footer(text="Keep betting to scratch Ibu's GÖT more!")

        # Send the embed
        await interaction.response.send_message(embed=embed)

    except KeyError as e:
        # Handle cases where the gambler does not exist
        await interaction.response.send_message(
            embed=Embed(
                title="Error",
                description=f"Error: {str(e)}. Are you registered?",
                colour=Colour.red()
            ),
            ephemeral=True
        )
    except Exception as e:
        # Handle unexpected errors
        await interaction.response.send_message(
            embed=Embed(
                title="Unexpected Error",
                description=f"An unexpected error occurred: {str(e)}",
                colour=Colour.red()
            ),
            ephemeral=True
        )

# ------------------------------- GET ANY GAMBLER'S BETS -------------------------------#
@bot.tree.command(name="gambler", description="Get any gambler's statistics.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
@app_commands.describe(
    gambler_id="Select the gambler you want to see the statistics of."
)
async def get_gambler(interaction: Interaction, gambler_id: str):
    gambler_id = int(gambler_id)
    
    try:
        gambler: Gambler = database.get_gambler(gambler_dc_id=gambler_id)
        bets = database.get_gambler_bet_details(gambler_dc_id=gambler_id)

        if not bets:
            await interaction.response.send_message(
                f"{gambler.name} has not placed any bets yet.", ephemeral=True
            )
            return

        # Send the gambler's stats and recent bets
        await interaction.response.send_message(
            f"{gambler}\n\n" + "**Last Bets Placed**\n||" + "\n".join(bets[-10:]) + "||"
        )
    except Exception as e:
        await interaction.response.send_message(str(e), ephemeral=True)

@get_gambler.autocomplete("gambler_id")
async def get_gambler_gambler_autocomplete(
    interaction: Interaction, current: str
    ) -> List[app_commands.Choice]:
    try:
        all_gamblers: List[Gambler] = database.get_all_gamblers()
        filtered_gamblers = [
            app_commands.Choice(name=f"{gambler.name}", value=str(gambler.id))
            for gambler in all_gamblers
            if current.lower() in f"{gambler.name}".lower()
        ]
        # Return up to 25 results (Discord limit)
        return filtered_gamblers[:25]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []


# ------------------------------- REGISTER AS A GAMBLER (COMMAND BASED FOR ADMINS)-------------------------------#
@bot.tree.command(name="register", description="Register a gambler to Team NicePros!")
@app_commands.describe(
    discord_id="Discord ID of the new gambler.",
    name="You can set a special gambler name if you want. Default is the gambler's Discord name.",
)
async def register(interaction: Interaction, discord_id: str = None, name: str = ""):
    required_role_id = ID.Roles.ADMIN
    if not await isAuthorisedUser(
        interaction=interaction, allowed_roles_id_list=required_role_id
    ):
        return

    required_channel_id = ID.Channels.ADMIN
    if not await isAuthorisedChannel(
        interaction=interaction, allowed_channels_id_list=required_channel_id
    ):
        return

    try:
        # Fetch the user using the provided Discord ID
        user = await bot.fetch_user(discord_id)
        if user is None:
            raise ValueError("Invalid Discord ID. User not found.")

        # Set the name to the global username of the user
        name = user.global_name if name == "" else name
        gambler: Gambler = database.add_gambler(discord_id=discord_id, name=name)
        await interaction.response.send_message(
            f"`{gambler.name} has been registered successfully.`"
        )
    except Exception as e:
        await interaction.response.send_message(str(e), ephemeral=True)


# ------------------------------- REGISTER AS A GAMBLER (EMOJI REACTION)-------------------------------#
@bot.tree.command(name="setup_register", description="Have the bot send the template message for users to register as gamblers.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
async def setup_register(interaction: Interaction):
    """
    Sends an embedded message for users to react and gain roles.
    """
    # Acknowledge the interaction
    await interaction.response.send_message("Setting up the registration message...", ephemeral=True)
    
    # Create the embed
    embed = Embed(
        title="🎲 Register as a Gambler 🎲",
        description=(
            "React with the following emojis to register:\n\n"
            "🎲 - **Gambler**\n"
        ),
        color=Colour.green()
    )
    embed.set_footer(text="React below to get your role!")

    # Send the embed message
    message = await interaction.followup.send(embed=embed)

    # Add reactions to the message
    emojis = list(Emoji.REACTION_ROLES.keys())
    for emoji in emojis:
        await message.add_reaction(emoji)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.member.bot:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    # Fetch the role based on the emoji used
    role_id = Emoji.REACTION_ROLES.get(payload.emoji.name)
    if not role_id:
        return

    # Get the role and member
    role = guild.get_role(role_id)
    member = payload.member

    if not role or not member:
        return

    # Add the role to the member
    await member.add_roles(role)

    # Register the user in the database
    try:
        database.add_gambler(
            discord_id=payload.user_id, name=member.global_name
        )  # Add user to database
        await member.send(f"`You have been registered successfully as {member.name}.`")
    except ValueError as e:
        await member.send(str(e))
    except Exception as e:
        await member.send(str(e) + "Please contact the admins with this error message.")


# ------------------------------- UPDATE THE LEADERBOARD -------------------------------#
@bot.tree.command(name="update_leaderboard", description="Update the leaderboard with the current standings.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
async def update_leaderboard_command(interaction: Interaction, week: int):
    try:
        await update_leaderboard(interaction=interaction, week=week)
        await interaction.response.send_message(f"Leaderboard has been updated for Week#{week}.")
    except Exception:
        await interaction.response.send_message(f"Leaderboard update has failed for Week#{week}.")


# ------------------------------- UPDATE THE WEEKLY STATS -------------------------------#
@bot.tree.command(name="update_weekly_stats", description="Update the statistics of gamblers for the given week. This command is to use in case of ambiguities.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
async def update_weekly_stats(interaction: Interaction, week: int):
    try:
        database.update_weekly_stats(week_number=week)
        await interaction.response.send_message(f"Weekly stats has been updated for Week#{week}.")
    except Exception as e:
        await interaction.response.send_message(f"Weekly stats has failed for Week#{week}. {e}")


# ------------------------------- START A NEW WEEK -------------------------------#
@bot.tree.command(name="new_week", description="Update the statistics of gamblers for the given week. This command is to use in case of ambiguities.")
@app_commands.default_permissions(administrator=True)  # Restricts visibility to admins
async def new_week(interaction: Interaction, week: int):
    try:
        database.update_weekly_stats(week_number=week)
        await update_leaderboard(interaction=interaction, week=week)
        await interaction.response.send_message(f"A new week has just started as Week#{week}.")
    except Exception as e:
        await interaction.response.send_message(f"New week cannot be started for Week#{week}: {e}")


# ------------------------------- SIDE METHODS FOR SLASH COMMANDS -------------------------------#

async def process_bet(interaction: Interaction, gambler_id: int, bet_id: int, bet_on: int, skip_timecheck: bool=False):
    try:
        gambler: Gambler = database.get_gambler(gambler_dc_id=gambler_id)
        bet: Bet = database.get_bet(bet_id=bet_id)

        # Place or update the bet on behalf of the gambler
        betcomment = database.link_gambler_to_bet(gambler_id=gambler_id, bet_id=bet_id, bet_on=bet_on, skip_timecheck=skip_timecheck)

        # Prepare the fancy response
        bet_placed = (
            f"🏠 **{bet.home_team}** ({bet.odd_1})" if bet_on == 1 else
            f"🤝 **Draw** ({bet.odd_0})" if bet_on == 0 else
            f"🚩 **{bet.away_team}** ({bet.odd_2})" if bet_on == 2 else
            "🏳️‍🌈 **Indecisive** (1.00)"
        )

        embed = Embed(
            title="🎲 Bet Placed Successfully 🎲",
            description=(
                f"**Gambler:** {interaction.user.mention}\n"
                f"**Match:** {bet.home_team} vs {bet.away_team}\n\n"
                f"✅ **{gambler.name}'s Bet:** {bet_placed}"
            ),
            color=Colour.green()
            
        )
        embed.set_footer(text="Developed by @talhatasova")
        embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.add_field(name="Comment", value=f"{gambler.name} says: {betcomment}", inline=False)

        # Respond publicly in the channel
        await interaction.response.send_message(embed=embed)

        # Send a private message to the gambler
        user = await interaction.client.fetch_user(gambler_id)
        if user:
            dm_embed = Embed(
                title="📩 Bet Confirmation",
                description=(
                    f"Hi {gambler.name}, your bet has been placed successfully!\n\n"
                    f"**Match:** {bet.home_team} vs {bet.away_team}\n"
                    f"✅ **Your Bet:** {bet_placed}\n\n"
                    "Good luck and stay tuned for the results!"
                ),
                color=Colour.blue()
            )
            await user.send(embed=dm_embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


async def update_leaderboard(interaction: Interaction, week: int):
    gamblers: List[Gambler] = database.get_all_gamblers()

    # Sort gamblers globally based on total payoff
    gamblers.sort(key=lambda g: g.payoff, reverse=True)
    global_ranks = {gambler.id: rank + 1 for rank, gambler in enumerate(gamblers)}

    # Retrieve weekly stats for the specified week
    weekly_stats = database.get_weekly_stats(week_number=week)

    # Prepare leaderboard channel
    leaderboard_channel = interaction.guild.get_channel(ID.Channels.LEADERBOARD)
    if not leaderboard_channel:
        raise ValueError("Leaderboard channel not found.")

    # Generate leaderboard content
    leaderboard_content = (
        "```diff\n"
        f"+-------------------------- LEADERBOARD (Week #{week}) --------------------------+\n"
    )
    leaderboard_content += "{:<7}{:<13}{:<8}{:<8}{:<10} | {:<8}{:<8}{:<10}\n".format(
        "W_Rank", "Name", "W_Pay", "W_%", "W_Stat",  # Weekly stats
        "G_Rank", "G_Pay", "G_Stat"                 # Global stats
    )
    leaderboard_content += "+---------------------------------------------------------------------------+\n"

    # Populate leaderboard with weekly and global stats
    for weekly_rank, stat in enumerate(weekly_stats, start=1):
        gambler = next((g for g in gamblers if g.id == stat.gambler_id), None)
        if not gambler:
            continue

        global_rank = global_ranks.get(gambler.id, "-")
        weekly_win_rate = (
            f"{round(stat.correct / stat.total * 100, 1):.1f}%" if stat.total > 0 else "0.0%"
        )
        weekly_stats = f"{stat.total}|{stat.correct}-{stat.total - stat.correct}"
        global_stats = f"{gambler.total}|{gambler.correct}-{gambler.total - gambler.correct}"

        # Weekly and global parts
        leaderboard_row = f"{weekly_rank:<7}{stat.name[:13]:<13}{stat.payoff:<8.2f}{weekly_win_rate:<8}{weekly_stats:<10} | {global_rank:<8}{gambler.payoff:<8.2f}{global_stats:<10}\n"

        # Add row to content
        leaderboard_content += leaderboard_row

    leaderboard_content += "+---------------------------------------------------------------------------+\n```"

    # Check for an existing leaderboard message
    async for message in leaderboard_channel.history(limit=100):  # Adjust limit as needed
        if (
            message.author == interaction.client.user
            and f"LEADERBOARD (Week #{week})" in message.content
        ):
            # Update the existing message
            await message.edit(content=leaderboard_content)
            return

    # If no message exists for the current week, create a new one
    await leaderboard_channel.send(leaderboard_content)


async def send_split_message(channel, content):
    MAX_CONTENT_LENGTH = 2000
    for i in range(0, len(content), MAX_CONTENT_LENGTH):
        await channel.send(content[i : i + MAX_CONTENT_LENGTH])


async def isRegisteredUser(interaction: Interaction) -> bool:
    try:
        gambler = database.get_gambler(gambler_dc_id=interaction.user.id)
        return True
    except KeyError:
        await interaction.response.send_message(
            "You have not registered to gambling. Please use #kayit channel and claim your role first.",
            ephemeral=True,
        )
        return False


async def isAuthorisedUser(interaction: Interaction, allowed_roles_id_list: List[int] | int) -> bool:
    if isinstance(allowed_roles_id_list, int):
        allowed_roles_id_list = [allowed_roles_id_list]

    if not any(role.id in allowed_roles_id_list for role in interaction.user.roles):
        await interaction.response.send_message(
            "You don't have the required role to use this command!", ephemeral=True
        )
        return False
    return True


async def isAuthorisedChannel(interaction: Interaction, allowed_channels_id_list: List[int] | int) -> bool:
    if isinstance(allowed_channels_id_list, int):
        allowed_channels_id_list = [allowed_channels_id_list]

    if not any(
        allowed_channels == interaction.channel.id
        for allowed_channels in allowed_channels_id_list
    ):
        await interaction.response.send_message(
            "This command cannot be used in this channel!", ephemeral=True
        )
        return False
    return True


async def isCorrectOdd(interaction: Interaction, odd: str) -> bool | float:
    if not isinstance(odd, str):
        return False

    try:
        odd = float(odd.replace(",", "."))
    except ValueError:
        await interaction.response.send_message(
            "`Odds must be valid numbers. Use '.' for decimal points, e.g., 2.5 instead of 2,5.`",
            ephemeral=True,
        )
        return False
    if odd < 1:
        await interaction.response.send_message(
            "`Odds must be larger than or equal to 1.0`", ephemeral=True
        )
        return False

    return odd


# Run the bot
bot.run(token)
