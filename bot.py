import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import logging
from scraper import RTanksScraper
from utils import create_player_embed, create_leaderboard_embed, create_error_embed
from flask import Flask
from threading import Thread
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for health checks and self-pinging
app = Flask(__name__)

@app.route('/')
def health_check():
    return "RTanks Discord Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "bot_connected": bot.is_ready() if 'bot' in globals() else False}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize scraper
scraper = RTanksScraper()

# Available ranking categories
RANKING_CATEGORIES = {
    'experience': 'По опыту',
    'crystals': 'По кристаллам', 
    'gold_boxes': 'По золотым ящикам',
    'kills': 'По киллам',
    'efficiency': 'По эффективности'
}

# Self-pinging function to keep bot alive on Render
def self_ping():
    """Keep the bot alive by pinging itself every 5 minutes"""
    render_url = os.getenv('RENDER_URL')
    
    # If no RENDER_URL is set, skip self-ping (for initial deployment)
    if not render_url:
        logger.info("RENDER_URL not set, skipping self-ping")
        return
    
    while True:
        try:
            time.sleep(300)  # Wait 5 minutes
            response = requests.get(f"{render_url}/health")
            if response.status_code == 200:
                logger.info("Self-ping successful")
            else:
                logger.warning(f"Self-ping failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"Self-ping error: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

def run_flask():
    """Run Flask app in a separate thread"""
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    try:
        # Sync commands globally
        await bot.tree.sync()
        logger.info("Commands synced successfully!")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="RTanks Online ratings"
        )
    )

@bot.tree.command(name="player", description="Get RTanks Online player statistics")
async def player_stats(interaction: discord.Interaction, nickname: str):
    """Get player statistics from RTanks Online ratings website"""
    await interaction.response.defer(thinking=True)
    
    try:
        # Validate nickname
        if not nickname or len(nickname.strip()) == 0:
            embed = create_error_embed("Invalid nickname", "Please provide a valid player nickname.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Clean nickname
        nickname = nickname.strip()
        
        # Get player data
        player_data = await scraper.get_player_stats(nickname)
        
        if not player_data:
            embed = create_error_embed(
                "Player not found", 
                f"Could not find player '{nickname}' in RTanks Online ratings.\n"
                "Please check the spelling and try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embed with player data
        embed = create_player_embed(player_data)
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error fetching player stats for {nickname}: {e}")
        embed = create_error_embed(
            "Error fetching player data",
            "There was an error retrieving the player statistics. Please try again later."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = []
        for key, value in RANKING_CATEGORIES.items():
            options.append(discord.SelectOption(
                label=value,
                value=key,
                description=f"Top players by {value.lower()}"
            ))
        
        super().__init__(
            placeholder="Choose a ranking category...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        try:
            category = self.values[0]
            category_name = RANKING_CATEGORIES[category]
            
            # Get leaderboard data
            leaderboard_data = await scraper.get_leaderboard(category)
            
            if not leaderboard_data:
                embed = create_error_embed(
                    "Leaderboard unavailable",
                    f"Could not fetch {category_name} leaderboard. Please try again later."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Create embed with leaderboard data
            embed = create_leaderboard_embed(category_name, leaderboard_data)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching leaderboard for {category}: {e}")
            embed = create_error_embed(
                "Error fetching leaderboard",
                "There was an error retrieving the leaderboard data. Please try again later."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
        self.add_item(CategorySelect())
    
    async def on_timeout(self):
        # Disable all items when view times out
        for item in self.children:
            item.disabled = True

@bot.tree.command(name="top", description="View RTanks Online leaderboards by category")
async def top_players(interaction: discord.Interaction):
    """Show interactive category selection for leaderboards"""
    embed = discord.Embed(
        title="🏆 RTanks Online Leaderboards",
        description="Select a category to view the top 10 players:",
        color=0x00ff00
    )
    embed.add_field(
        name="Available Categories",
        value="\n".join([f"• {name}" for name in RANKING_CATEGORIES.values()]),
        inline=False
    )
    embed.set_footer(text="Select a category from the dropdown below")
    
    view = CategoryView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="about", description="Information about the RTanks Online bot")
async def about(interaction: discord.Interaction):
    """Show information about the bot"""
    embed = discord.Embed(
        title="🤖 RTanks Online Bot",
        description="A Discord bot for viewing RTanks Online player statistics and leaderboards",
        color=0x0099ff
    )
    embed.add_field(
        name="Commands",
        value="• `/player <nickname>` - View player statistics\n"
              "• `/top` - View leaderboards by category\n"
              "• `/about` - Show this information",
        inline=False
    )
    embed.add_field(
        name="Data Source",
        value="[RTanks Online Ratings](https://ratings.ranked-rtanks.online/)",
        inline=False
    )
    embed.add_field(
        name="Features",
        value="• Real-time player statistics\n"
              "• Interactive leaderboard categories\n"
              "• Support for Russian text\n"
              "• Cached data for performance",
        inline=False
    )
    embed.set_footer(text="RTanks Online - Nostalgic tank battles restored!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for slash commands"""
    logger.error(f"Command error: {error}")
    
    if isinstance(error, app_commands.CommandOnCooldown):
        embed = create_error_embed(
            "Command on cooldown",
            f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = create_error_embed(
            "Command error",
            "An unexpected error occurred while processing your command."
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

# Error handling for the bot
@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Bot error in {event}: {args}")

if __name__ == "__main__":
    # Get bot token from environment
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start self-ping in a separate thread
    ping_thread = Thread(target=self_ping)
    ping_thread.daemon = True
    ping_thread.start()
    
    logger.info("Starting Discord bot...")
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
