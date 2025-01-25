from datetime import datetime, timezone
from discord import Interaction, Embed, Colour, ButtonStyle
from discord.ui import Button, View
from database import Gambler, Bet
import database
from settings import Emoji

class EmbedMessages:
    @classmethod
    def bet_created_confirmation(cls, bet: Bet):
        embed = Embed(
            title=f"{Emoji.CHECK} Bet Created - ID: {bet.id}",
            description=(
                f"**Match:** {bet.home_team} vs {bet.away_team}\n\n"
                f"**Odds:**\n"
                f"- {bet.home_team}: {bet.odd_1}\n"
                f"- Draw: {bet.odd_0}\n"
                f"- {bet.away_team}: {bet.odd_2}\n\n"
                f"**Date:** {bet.deadline} (Week {bet.week})"
            ),
            colour=Colour.green()
        )
        return embed
    
    @classmethod
    def bet_created_announcement(cls, bet: Bet) -> Embed:
        embed = Embed(
            title="⚽ New Match Announcement ⚽",
            description=(
                f"**`{bet.home_team} vs {bet.away_team}`**\n\n"
                f"{Emoji.HOME} **{bet.home_team}**: {bet.odd_1}\n"
                f"{Emoji.DRAW} **Draw**: {bet.odd_0}\n"
                f"{Emoji.AWAY} **{bet.away_team}**: {bet.odd_2}\n\n"
                f"{Emoji.DATE} **Match Date**: `{bet.deadline}`"
            ),
            color=Colour.blue(),
        )
        embed.set_footer(text="Use the buttons below to place your bet!")
        return embed
    
    @classmethod
    def bet_deadline_passed(cls, bet:Bet) -> Embed:
        embed = Embed(
            title="⚽ Match is Over ⚽",
            description=(
                f"**`{bet.home_team} vs {bet.away_team}`**\n\n"
                f"{Emoji.HOME} **{bet.home_team}**: {bet.odd_1} {Emoji.CHECK if bet.winning_odd == 1 else ''}\n"
                f"{Emoji.DRAW} **Draw**: {bet.odd_0} {Emoji.CHECK if bet.winning_odd == 0 else ''}\n"
                f"{Emoji.AWAY} **{bet.away_team}**: {bet.odd_2} {Emoji.CHECK if bet.winning_odd == 2 else ''}\n\n"
                f"{Emoji.DATE} **Match Date**: `{bet.deadline}`"
            ),
            color=Colour.light_grey(),
        )
        embed.set_footer(text="Keep in touch to get notified for the future matchs!")
        return embed

class BetButtons(View):
    def __init__(self, bet: Bet):
        super().__init__(timeout=None)
        self.bet = bet
        
        # Check if the deadline has passed
        self.is_disabled = datetime.now(timezone.utc) >= bet.deadline.astimezone(timezone.utc)

        self.home_button = Button(label=bet.home_team, style=ButtonStyle.primary, custom_id=f"{bet.id}_1", emoji=Emoji.HOME, disabled=self.is_disabled)
        self.draw_button = Button(label="Draw", style=ButtonStyle.primary, custom_id=f"{bet.id}_0", emoji=Emoji.DRAW, disabled=self.is_disabled)
        self.away_button = Button(label=bet.away_team, style=ButtonStyle.primary, custom_id=f"{bet.id}_2", emoji=Emoji.AWAY, disabled=self.is_disabled)
        self.withdraw_button = Button(label="Withdraw", style=ButtonStyle.danger, custom_id=f"{bet.id}_3", emoji=Emoji.WITHDRAW, disabled=self.is_disabled)

        self.add_item(self.home_button)
        self.add_item(self.draw_button)
        self.add_item(self.away_button)
        self.add_item(self.withdraw_button)

        self.home_button.callback = self.on_bet_button_click
        self.draw_button.callback = self.on_bet_button_click
        self.away_button.callback = self.on_bet_button_click
        self.withdraw_button.callback = self.on_bet_button_click

    async def on_bet_button_click(self, interaction: Interaction):
        # Acknowledge interaction early
        await interaction.response.defer(ephemeral=True)

        gambler_id = interaction.user.id
        gambler = database.get_gambler(gambler_id)
        bet_id, button_label = interaction.data['custom_id'].split('_')
        bet_id = int(bet_id)
        bet_on = int(button_label)
        try:
            # Link gambler to the bet
            database.link_gambler_to_bet(gambler_id=gambler_id, bet_id=bet_id, bet_on=bet_on)
            print(f"{gambler.name} | {self.bet.home_team} vs {self.bet.away_team} | {bet_on}")
            # Construct bet details
            bet_placed = (
                f"🏠 **{self.bet.home_team}** ({self.bet.odd_1})" if bet_on == 1 else
                f"🤝 **Draw** ({self.bet.odd_0})" if bet_on == 0 else
                f"🚩 **{self.bet.away_team}** ({self.bet.odd_2})" if bet_on == 2 else
                "🏳️‍🌈 **Indecisive** (1.00)"
            )

            # Send DM confirmation
            user = await interaction.client.fetch_user(gambler_id)
            dm_embed = Embed(
                title="📩 Bet Confirmation",
                description=(
                    f"Hi {gambler.name}, your bet has been placed successfully!\n\n"
                    f"**Match:** {self.bet.home_team} vs {self.bet.away_team}\n"
                    f"{Emoji.CHECK} **Your Bet:** {bet_placed}\n\n"
                    "Good luck and stay tuned for the results!"
                ),
                color=Colour.green()
            )
            try:
                await user.send(embed=dm_embed)
                await interaction.followup.send(embed=dm_embed, ephemeral=True)
            except Exception as e:
                print(f"Failed to send DM to {user.name}: {e}")
                await interaction.followup.send("The BOT could not send you a DM. Please check your settings.", ephemeral=True)

        except ValueError as e:
            # Handle specific errors
            error_embed = Embed(
                title="📩 Bet Confirmation",
                description=(
                    f"{Emoji.X} Hi {gambler.name}, your bet has failed because {e}\n\n"
                    f"**Match:** {self.bet.home_team} vs {self.bet.away_team}\n"
                ),
                color=Colour.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

        except Exception as e:
            # Handle unexpected errors
            print(f"Unexpected error while placing bet: {e}")
            await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)