import discord
from typing import Dict, List, Optional
import re

def create_player_embed(player_data: Dict) -> discord.Embed:
    """Create a Discord embed for player statistics with activity status"""
    nickname = player_data.get('nickname', 'Unknown')
    
    embed = discord.Embed(
        title=f"🎮 {nickname}",
        description=f"RTanks Online Player Statistics",
        color=0x00ff00
    )
    
    # Add rank and experience
    rank = player_data.get('rank')
    experience = player_data.get('experience')
    
    if rank:
        embed.add_field(name="🪖 Rank", value=rank, inline=True)
    
    if experience:
        embed.add_field(name="⭐ Experience", value=f"{experience:,}", inline=True)
    
    # Add activity status (online/offline)
    activity = player_data.get('activity', 'Unknown')
    if activity == 'Online':
        activity_value = "🟢 Online"
    elif activity == 'Offline':
        activity_value = "⚪ Offline"
    else:
        activity_value = "❔ Unknown"
    
    embed.add_field(name="🟣 Activity", value=activity_value, inline=True)
    
    # Add combat statistics
    kills = player_data.get('kills')
    deaths = player_data.get('deaths')
    kd_ratio = player_data.get('kd_ratio')
    
    if kills is not None:
        embed.add_field(name="💀 Kills", value=f"{kills:,}", inline=True)
    
    if deaths is not None:
        embed.add_field(name="☠️ Deaths", value=f"{deaths:,}", inline=True)
    
    if kd_ratio is not None:
        embed.add_field(name="📊 K/D Ratio", value=f"{kd_ratio:.2f}", inline=True)
    
    # Add other statistics
    gold_boxes = player_data.get('gold_boxes')
    premium = player_data.get('premium')
    group = player_data.get('group')
    
    if gold_boxes is not None:
        embed.add_field(name="🎁 Gold Boxes", value=f"{gold_boxes:,}", inline=True)
    
    if premium is not None:
        status = "✅ Yes" if premium else "❌ No"
        embed.add_field(name="💎 Premium", value=status, inline=True)
    
    if group:
        embed.add_field(name="👥 Group", value=group, inline=True)
    
    # Add rankings if available
    rankings = player_data.get('rankings', {})
    if rankings:
        ranking_text = []
        for category, data in rankings.items():
            rank = data.get('rank', 'N/A')
            value = data.get('value', 'N/A')
            ranking_text.append(f"{category}: {rank} ({value})")
        
        if ranking_text:
            embed.add_field(
                name="🏆 Current Rankings",
                value="\n".join(ranking_text[:5]),  # Limit to 5 rankings
                inline=False
            )
    
    # Add equipment information
    equipment = player_data.get('equipment', {})
    equipment_text = []
    
    turrets = equipment.get('turrets', [])
    hulls = equipment.get('hulls', [])
    paints = equipment.get('paints', [])
    modules = equipment.get('modules', [])
    
    if turrets:
        equipment_text.append(f"🔫 Turrets: {', '.join(turrets[:3])}")
    if hulls:
        equipment_text.append(f"🛡️ Hulls: {', '.join(hulls[:3])}")
    if paints:
        equipment_text.append(f"🎨 Paints: {', '.join(paints[:3])}")
    if modules:
        equipment_text.append(f"⚙️ Modules: {', '.join(modules[:3])}")
    
    if equipment_text:
        embed.add_field(
            name="🎯 Equipment",
            value="\n".join(equipment_text),
            inline=False
        )
    
    # Footer
    embed.set_footer(
        text="Data from RTanks Online Ratings",
        icon_url="https://ratings.ranked-rtanks.online/public/images/logo.png"
    )
    
    return embed


def create_leaderboard_embed(category_name: str, leaderboard_data: List[Dict]) -> discord.Embed:
    """Create a Discord embed for leaderboard"""
    embed = discord.Embed(
        title=f"🏆 Top 10 Players - {category_name}",
        description="RTanks Online Leaderboard",
        color=0xffd700
    )
    
    if not leaderboard_data:
        embed.add_field(
            name="No Data Available",
            value="Could not retrieve leaderboard data at this time.",
            inline=False
        )
        return embed
    
    # Create leaderboard text
    leaderboard_text = []
    medal_emojis = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(leaderboard_data):
        rank = player.get('rank', i + 1)
        name = player.get('name', 'Unknown')
        value = player.get('formatted_value', player.get('value', 'N/A'))
        
        # Clean up player name
        name = clean_player_name(name)
        
        # Add medal emoji for top 3
        if i < 3:
            emoji = medal_emojis[i]
        else:
            emoji = f"{rank}."
        
        leaderboard_text.append(f"{emoji} **{name}** - {value}")
    
    # Split into multiple fields if too long
    text = "\n".join(leaderboard_text)
    if len(text) > 1024:
        # Split into two fields
        mid = len(leaderboard_text) // 2
        embed.add_field(
            name="Rankings 1-5",
            value="\n".join(leaderboard_text[:mid]),
            inline=True
        )
        embed.add_field(
            name="Rankings 6-10",
            value="\n".join(leaderboard_text[mid:]),
            inline=True
        )
    else:
        embed.add_field(
            name="Rankings",
            value=text,
            inline=False
        )
    
    # Add timestamp info
    embed.add_field(
        name="ℹ️ Info",
        value="Rankings update regularly on the RTanks website.\n"
              "Some categories reset weekly on Monday at 2:00 UTC.",
        inline=False
    )
    
    embed.set_footer(
        text="Data from RTanks Online Ratings",
        icon_url="https://ratings.ranked-rtanks.online/public/images/logo.png"
    )
    
    return embed

def create_error_embed(title: str, description: str) -> discord.Embed:
    """Create an error embed"""
    embed = discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=0xff0000
    )
    return embed

def clean_player_name(name: str) -> str:
    """Clean up player name for display"""
    if not name:
        return "Unknown"
    
    # Remove common prefixes and suffixes
    name = re.sub(r'^[\d\s\.\-\#]+', '', name).strip()
    name = re.sub(r'[\d\s\.\-\#]+$', '', name).strip()
    
    # Remove special characters but keep underscores and basic characters
    name = re.sub(r'[^\w\s\-_\.]', '', name)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name or "Unknown"

def format_number(num: int) -> str:
    """Format large numbers with commas"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)
