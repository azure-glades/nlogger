import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone
import re
import json
import os

LOG_NUMBERS_FILE = "/tmp/log_numbers.json"  # Railway uses ephemeral storage
IST = timezone(timedelta(hours=5, minutes=30))

class LogBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.synced = False
        self.log_numbers = self.load_log_numbers()

    def load_log_numbers(self):
        """Load log numbers from file"""
        try:
            if os.path.exists(LOG_NUMBERS_FILE):
                with open(LOG_NUMBERS_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_log_numbers(self):
        """Save log numbers to file"""
        try:
            with open(LOG_NUMBERS_FILE, 'w') as f:
                json.dump(self.log_numbers, f, indent=2)
        except:
            pass  # If save fails, continue anyway

    def get_next_log_number(self, user_id: str) -> int:
        """Get and increment log number for user"""
        if user_id not in self.log_numbers:
            self.log_numbers[user_id] = 1
        else:
            self.log_numbers[user_id] += 1
        
        self.save_log_numbers()
        return self.log_numbers[user_id]

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        
        if not self.synced:
            await self.tree.sync()
            self.synced = True
            print("Slash commands synced globally")

def get_ist_time():
    """Get current time in IST timezone"""
    return datetime.now(IST)

bot = LogBot()

def generate_user_code(username: str) -> str:
    """Generate code from first 2 and last 2 characters of username"""
    username = username.strip()
    
    if len(username) < 2:
        return f"{username * 2}{username * 2}".upper()
    elif len(username) == 2:
        return f"{username}{username}".upper()
    elif len(username) == 3:
        return f"{username[:2]}{username[-1] * 2}".upper()
    else:
        return f"{username[:2]}{username[-2:]}".upper()

@bot.tree.command(name="log", description="Log a message in formatted style")
@app_commands.describe(
    message="The log message content",
    date="Optional: Custom date in DD/MM/YYYY format (defaults to today)"
)
async def log_command(interaction: discord.Interaction, message: str, date: str = None):
    """Log a formatted message with auto-generated user code and log number"""
    
    username = interaction.user.name
    user_code = generate_user_code(username)
    
    user_id = str(interaction.user.id)
    log_number = bot.get_next_log_number(user_id)
    
    if date:
        date_pattern = r'^\d{2}/\d{2}/\d{4}$'
        if not re.match(date_pattern, date):
            await interaction.response.send_message(
                "Invalid date format! Please use DD/MM/YYYY format.", 
                ephemeral=True
            )
            return
        log_date = date
    else:
        ist_time = get_ist_time()
        log_date = ist_time.strftime("%d/%m/%Y %H:%M:%S")
    
    formatted_message = (
        f"[{user_code}] [{log_number:02d}] {log_date}:\n"
        f"{message}"
    )
    
    await interaction.response.send_message(formatted_message)


@bot.tree.command(name="reset_log", description="Reset your log counter")
@app_commands.describe(
    user="Optional: User to reset (admin only)",
    new_number="Optional: Set to specific number (default: 0)"
)
async def reset_log_command(interaction: discord.Interaction, user: discord.User = None, new_number: int = 0):
    """Reset log numbers for yourself or others (admin only)"""
    
    is_admin = interaction.user.guild_permissions.administrator
    
    if user and not is_admin:
        await interaction.response.send_message("Only administrators can reset other users' logs.", ephemeral=True)
        return
    
    target_user = user or interaction.user
    user_id = str(target_user.id)
    
    bot.log_numbers[user_id] = new_number
    bot.save_log_numbers()
    
    if user:
        await interaction.response.send_message(f"Reset {target_user.display_name}'s log number to {new_number:02d}")
    else:
        await interaction.response.send_message(f"Reset your log number to {new_number:02d}", ephemeral=True)

@bot.tree.command(name="log_debug", description="Debug log numbers (Admin only)")
async def log_debug_command(interaction: discord.Interaction):
    """View and manage log numbers"""
    '''
    is_owner = interaction.user.id == interaction.guild.owner_id
    is_admin = interaction.user.guild_permissions.administrator
    
    if not (is_owner or is_admin):
        await interaction.response.send_message("Administrator permission required.", ephemeral=True)
        return
    '''
    # Show current IST time for debugging
    ist_time = get_ist_time()
    current_ist = ist_time.strftime("%d/%m/%Y %H:%M:%S")
    
    if not bot.log_numbers:
        debug_info = "No log numbers recorded yet."
    else:
        debug_info = "Current Log Numbers:\n"
        for user_id, number in bot.log_numbers.items():
            try:
                user = await bot.fetch_user(int(user_id))
                username = user.name
            except:
                username = f"Unknown ({user_id})"
            debug_info += f"- {username}: {number:02d}\n"
    
    debug_info += f"\nTotal users: {len(bot.log_numbers)}"
    debug_info += f"\nCurrent IST: {current_ist}"
    
    await interaction.response.send_message(f"```{debug_info}```", ephemeral=True)

if __name__ == "__main__":
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("ERROR: DISCORD_TOKEN environment variable not set!")
        print("Please set it in Railway dashboard → Variables")
        exit(1)
    
    bot.run(token)