import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from colorama import Fore, Style, init
from datetime import datetime, timedelta, timezone
import asyncio, time, random, re, json, os, logging

log = logging.getLogger("bot")

# ================= CONFIG =================
from config import TOKEN, PREFIX

WARN_FILE = "warnings.json"
CONFIG_FILE = "bot_config.json"
LEVELING_FILE = "leveling.json"
ROLE_REWARDS_FILE = "role_rewards.json"
PREMIUM_FILE = "premium.json"

# ================= OWNER / PREMIUM CONFIG =================
# Add your owner IDs here (up to 6)
OWNER_IDS = {
    1460710481999167632,
    # Add more owner IDs below:
    # 123456789012345678,
    # 123456789012345678,
    # 123456789012345678,
    # 123456789012345678,
    # 123456789012345678,
}
DEFAULT_PREMIUM_PASSWORD = "nexafyrez"

# ================= ANIMATED EMOJIS =================
E_BULLET = "<a:op:1452648651481677886>"
E_TICKET = "<a:op:1454901617915854880>"
E_TICKET2 = "<a:op:1454543107738828873>"
E_WELCOME = "<a:op:1452712544887243006>"
E_GIVEAWAY_TITLE = "<a:op:1452711788520144949>"

# ---------- Console Banner ----------
init(autoreset=True)

def banner():
    print(Fore.GREEN + Style.BRIGHT + r"""
███████╗███╗   ██╗
██╔════╝████╗  ██║
█████╗  ██╔██╗ ██║
██╔══╝  ██║╚██╗██║
██║     ██║ ╚████║
╚═╝     ╚═╝  ╚═══╝
""")
    print(Fore.GREEN + Style.BRIGHT + ">> DEVELOPER BY OBITO X AIZEN")

banner()
BOT_START_TIME = datetime.now()

# ---------- Bot Setup ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

def get_prefix(bot_instance, message):
    """Get per-guild prefix, fallback to default."""
    if message.guild:
        gid = str(message.guild.id)
        guild_prefixes = config.get("guild_prefixes", {}) if isinstance(config, dict) else {}
        return guild_prefixes.get(gid, PREFIX)
    return PREFIX

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

FN_COLOR = discord.Color.from_rgb(0, 153, 255)

# ================= DATA =================
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_json(data, path):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

warnings_data = load_json(WARN_FILE)

if not os.path.exists(CONFIG_FILE):
    save_json({"welcome_channels": {}, "goodbye_channels": {}}, CONFIG_FILE)
config = load_json(CONFIG_FILE)

leveling_data = load_json(LEVELING_FILE)
role_rewards = load_json(ROLE_REWARDS_FILE)

# Premium data: { "guild_id": ["user_id1", "user_id2", ...] }
premium_data = load_json(PREMIUM_FILE)
# Premium password (persisted in config)
PREMIUM_PASSWORD = config.get("premium_password", DEFAULT_PREMIUM_PASSWORD)

# --- Persistent bot settings (survive restart) ---
_saved = config.get("bot_settings", {})
features = {"security": _saved.get("security", False), "antinuke": _saved.get("antinuke", False)}
whitelist = set(_saved.get("whitelist", []))
UNBAN_LINK = _saved.get("unban_link", "Not set")
LOG_CHANNEL_ID = _saved.get("log_channel_id", None)

user_spam = {}
giveaways = {}
member_data = {}
voice_states = {}
BAD_WORDS = ["mc", "bc", "madarchod", "behenchod"]
LINK_REGEX = r"(https?:\/\/|www\.)"

def save_bot_settings():
    config["bot_settings"] = {
        "security": features.get("security", False),
        "antinuke": features.get("antinuke", False),
        "whitelist": list(whitelist),
        "ticket_roles": list(ticket_roles) if 'ticket_roles' in dir() else list(config.get("ticket_roles_list", [])),
        "unban_link": UNBAN_LINK,
        "log_channel_id": LOG_CHANNEL_ID,
    }
    save_config()

# ================= HELPERS =================
def fn_embed(title, desc=None):
    return discord.Embed(title=title, description=desc, color=FN_COLOR)

def small_embed(text):
    return discord.Embed(description=text, color=FN_COLOR)

def is_owner(user_id):
    """Check if a user is a bot owner."""
    return user_id in OWNER_IDS

def is_premium(guild_id, user_id):
    """Check if a user has premium in a guild."""
    gid = str(guild_id)
    uid = str(user_id)
    return uid in premium_data.get(gid, [])

def save_premium():
    save_json(premium_data, PREMIUM_FILE)

async def premium_required_msg(ctx_or_interaction):
    """Send 'buy premium' message for non-premium users."""
    embed = discord.Embed(
        title="⭐ Premium Command",
        description="This is a **premium-only** command!\n\n"
                    "🔑 Use `>premium <password>` or `/premium` to activate premium.\n"
                    "📞 Contact the server admin or use `>support` for details.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await ctx_or_interaction.send(embed=embed, delete_after=15)

def blue_embed(title, desc, guild=None):
    e = discord.Embed(title=title, description=desc, color=FN_COLOR)
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    return e

def save_config():
    save_json(config, CONFIG_FILE)

def is_bypass(member):
    try:
        if not member or not getattr(member, "guild", None):
            return False
        if member.guild.owner_id == member.id:
            return True
        if member.id in whitelist:
            return True
    except Exception:
        return False
    return False

def is_bypass_user_by_guild(guild, user):
    if not user:
        return False
    if user.id in whitelist:
        return True
    if user.id == guild.owner_id:
        return True
    return False

async def log_action(guild, text):
    if LOG_CHANNEL_ID:
        ch = guild.get_channel(LOG_CHANNEL_ID)
        if ch:
            try:
                await ch.send(embed=small_embed(text))
            except Exception:
                pass

def protect_link(link):
    link = link.replace("https://", "hxxps://").replace("http://", "hxxp://").replace(".", "[.]")
    return link

def find_role(guild, role_name):
    rn = role_name.lower().strip()
    for r in guild.roles:
        if r.name.lower() == rn:
            return r
    for r in guild.roles:
        if rn in r.name.lower():
            return r
    return None

def punishment_embed(action, reason, server, moderator):
    embed = discord.Embed(title="⚠ Punishment Received", color=FN_COLOR)
    embed.add_field(name="Action", value=action, inline=False)
    embed.add_field(name="Reason", value=reason if reason else "No reason provided", inline=False)
    embed.add_field(name="Server", value=server, inline=False)
    embed.add_field(name="Moderator", value=moderator, inline=False)
    return embed

def parse_duration(duration_str):
    units = {'m': 60000, 'h': 3600000, 'd': 86400000, 's': 1000}
    try:
        num, unit = '', ''
        for c in duration_str.lower():
            if c.isdigit():
                num += c
            else:
                unit += c
        if not num or not unit or unit not in units:
            return None
        return int(num) * units[unit]
    except Exception:
        return None

# ================= ANTI-NUKE =================
async def nuke_punish(guild, action, target_id=None, max_seconds=12):
    try:
        bot_member = guild.me or guild.get_member(bot.user.id)
        if not bot_member or not bot_member.guild_permissions.view_audit_log:
            return
        async for entry in guild.audit_logs(limit=8, action=action):
            if target_id and getattr(entry.target, "id", None) != target_id:
                continue
            try:
                age = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
            except Exception:
                age = 9999
            if age > max_seconds:
                continue
            executor = entry.user
            if not executor or is_bypass_user_by_guild(guild, executor):
                return
            reason = f"Anti-Nuke: {action.name}"
            try:
                await executor.send(embed=discord.Embed(title="🚫 You Were Banned", description=reason, color=discord.Color.red()))
            except Exception:
                pass
            try:
                await guild.ban(executor, reason=reason, delete_message_days=0)
                await log_action(guild, f"{executor} banned for {action.name}")
            except Exception as e:
                await log_action(guild, f"❌ Failed: {e}")
            return
    except Exception:
        pass

# ================= VIEWS =================
ticket_roles = set(_saved.get("ticket_roles", []))

class TicketTypeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Select Ticket Type",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="🎁 Reward", value="reward", description="Open reward ticket"),
            discord.SelectOption(label="🛒 Buy", value="buy", description="Open buy ticket"),
            discord.SelectOption(label="👔 Staff Apply", value="staff_apply", description="Open staff apply ticket"),
            discord.SelectOption(label="🆘 Support", value="support", description="Open support ticket"),
        ],
        custom_id="ticket_type_select"
    )
    async def select_ticket_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        ticket_type = select.values[0]
        guild, user = interaction.guild, interaction.user
        category = discord.utils.get(guild.categories, name="Tickets") or await guild.create_category("Tickets")
        channel_name = f"{ticket_type}-{user.name}".lower()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in ticket_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        embed = discord.Embed(
            title=f"🎫 {ticket_type.replace('_',' ').title()} Ticket",
            description=f"Ticket created by {user.mention}\n\nStaff will assist you shortly.",
            color=FN_COLOR
        )
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.channel.delete()


# ================= HELP VIEW =================
class HelpSelectView(View):
    def __init__(self, guild=None):
        super().__init__(timeout=None)
        self.guild = guild
        options = [
            discord.SelectOption(label="Giveaway Commands", description="Show all giveaway commands", emoji="🎉", value="giveaway"),
            discord.SelectOption(label="Leveling & Voice Commands", description="Show leveling, XP, role rewards & voice commands", emoji="📊", value="leveling"),
            discord.SelectOption(label="Member Commands", description="Show all member commands", emoji="👤", value="member"),
            discord.SelectOption(label="Moderator Commands", description="Show all moderator commands", emoji="🛡️", value="moderator"),
            discord.SelectOption(label="Player / Channel Commands", description="Show player and scan commands", emoji="🎮", value="player"),
            discord.SelectOption(label="Anti-Nuke Commands", description="Show anti-nuke commands", emoji="🔒", value="antinuke"),
            discord.SelectOption(label="Premium Commands", description="Show premium-only commands", emoji="⭐", value="premium"),
        ]
        select = Select(placeholder="Select a command category...", options=options, custom_id="help_select")
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        choice = interaction.data["values"][0]
        embed = _build_help_embed(choice, self.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)

def _set_help_footer(embed, guild=None):
    embed.set_footer(text="Made by obito 💖 | NexafyreZ")
    try:
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
    except Exception:
        pass

def _build_help_embed(choice, guild=None):
    embed = discord.Embed(color=FN_COLOR)
    _set_help_footer(embed, guild)
    a = E_BULLET

    if choice == "giveaway":
        embed.title = f"{E_GIVEAWAY_TITLE} Giveaway Commands"
        embed.add_field(name=f"{a} >giveaway <duration> <prize> | /giveaway", value="Start a new giveaway\n**Example:** `>giveaway 1h iPhone 15`", inline=False)
        embed.add_field(name=f"{a} >removegiveaway <id> | /removegiveaway", value="Remove a specific giveaway by ID", inline=False)
        embed.add_field(name=f"{a} >deletegiveaway | /deletegiveaway", value="Delete ALL active giveaways (Admin Only)", inline=False)
        embed.add_field(name=f"{a} >endgiveaway <id> | /endgiveaway", value="End a giveaway immediately and pick winner", inline=False)
        embed.add_field(name="📌 Giveaway ID Location", value="The Giveaway ID is displayed at the bottom of the giveaway embed", inline=False)
        embed.add_field(name="⏱️ Duration Formats", value="`10m` (10 min) `1h` (1 hour) `2d` (2 days) `30s` (30 sec)", inline=False)
    elif choice == "leveling":
        embed.title = "📊 Leveling & Voice Commands"
        embed.add_field(name="━━━ LEVELING ━━━", value="", inline=False)
        embed.add_field(name=f"{a} >rank / /rank", value="Check your current rank and XP", inline=False)
        embed.add_field(name=f"{a} >leaderboard / /leaderboard", value="View top 10 members by XP", inline=False)
        embed.add_field(name=f"{a} >reset-xp @member / /reset-xp", value="Reset a member's XP (Admin)", inline=False)
        embed.add_field(name=f"{a} >give-xp @member <amount> / /give-xp", value="Give XP to a member (Admin)", inline=False)
        embed.add_field(name="How to Earn XP?", value="Send messages in the server to earn XP\nYou get random XP (10-50) per message", inline=False)
        embed.add_field(name="━━━ ROLE REWARDS ━━━", value="", inline=False)
        embed.add_field(name=f"{a} >set-role-reward <level> @role / /set-role-reward", value="Set role reward for level (Admin)\n**Example:** `>set-role-reward 5 @Streamer`", inline=False)
        embed.add_field(name=f"{a} >remove-role-reward <level> / /remove-role-reward", value="Remove role reward (Admin)", inline=False)
        embed.add_field(name=f"{a} >list-role-rewards / /list-role-rewards", value="List all role rewards", inline=False)
        embed.add_field(name="━━━ VOICE ━━━", value="", inline=False)
        embed.add_field(name=f"{a} >pull all / >pull @member / /pull", value="Pull members to your VC (Admin)", inline=False)
        embed.add_field(name=f"{a} >vcmute / >vcunmute / /vcmute / /vcunmute", value="Mute/Unmute in VC (Admin)", inline=False)
        embed.add_field(name=f"{a} >join / /join | >leave / /leave", value="Bot joins/leaves your VC", inline=False)
    elif choice == "member":
        embed.title = "👤 Member Commands"
        embed.color = discord.Color.green()
        for name, desc in [
            (">ping / /ping", "Bot latency"), (">serverinfo / /serverinfo", "Server info"),
            (">user / /user", "User info"), (">avatar / /avatar", "Show avatar"),
            (">say / /say", "Bot repeat text"), (">support / /support", "Support info"),
            (">rank / /rank", "Check your rank"),
            (">leaderboard / /leaderboard", "View top 10 XP"),
            (">botinfo / /botinfo", "Bot stats & info")]:
            embed.add_field(name=f"{a} {name}", value=desc, inline=False)
    elif choice == "moderator":
        embed.title = "🛡️ Moderator Commands"
        embed.color = discord.Color.red()
        cmds = [
            (">ban / /ban", "Ban member"), (">unban / /unban", "Unban member"),
            (">kick / /kick", "Kick member"), (">timeout / /timeout", "Timeout member"),
            (">removetimeout / /removetimeout", "Remove timeout"), (">purge / /purge", "Delete messages"),
            (">warn / /warn", "Warn member"), (">scan / /scan", "Scan member activity"),
            (">lock / /lock", "Lock channel"), (">unlock / /unlock", "Unlock channel"),
            (">role / /role", "Assign role"), (">removerole / /removerole", "Remove role"),
            (">welcomeset / /welcomeset", "Set welcome"), (">goodbyeset / /setgoodbye", "Set goodbye"),
            (">welcomeremove / /welcomeremove", "Remove welcome"), (">goodbyeremove / /removegoodbye", "Remove goodbye"),
            (">ticketrole / /ticketrole", "Add ticket staff"), (">removeticketrole / /removeticketrole", "Remove ticket role"),
            (">ticket / /ticket", "Ticket panel"), (">close", "Close ticket"),
            (">autorole / /autorole", "Set autorole"), (">removeautorole / /removeautorole", "Remove autorole"),
            (">give-xp / /give-xp", "Give XP"), (">reset-xp / /reset-xp", "Reset XP"),
            (">set-role-reward / /set-role-reward", "Set role reward"), (">remove-role-reward / /remove-role-reward", "Remove reward"),
            (">vcmute / /vcmute", "Mute in VC"), (">vcunmute / /vcunmute", "Unmute in VC"),
            (">pull / /pull", "Pull to VC"), (">linkprotect / /linkprotect", "Protect link (Admin)"),
            (">setapplylink / /setapplylink", "Set apply link"),
            (">setprefix / /setprefix", "Change bot prefix (Admin)"),
        ]
        desc_lines = [f"{a} **{name}** — {desc}" for name, desc in cmds]
        embed.description = "\n".join(desc_lines)
    elif choice == "player":
        embed.title = "🎮 Player / Channel Commands"
        for name, desc in [
            (">warn / /warn", "Warn a member"), (">lock / /lock", "Lock channel"),
            (">unlock / /unlock", "Unlock channel"), (">scan / /scan", "Scan member activity"),
            (">join / /join", "Bot joins VC"), (">leave / /leave", "Bot leaves VC")]:
            embed.add_field(name=f"{a} {name}", value=desc, inline=False)
    elif choice == "antinuke":
        embed.title = "🔒 Anti-Nuke Commands"
        embed.color = discord.Color.dark_purple()
        for name, desc in [
            (">setup / /setup", "Enable all security & anti-nuke"),
            (">unsetup / /unsetup", "Disable all security"),
            (">addwhitelist / /addwhitelist", "Whitelist a member"),
            (">removewhitelist / /removewhitelist", "Remove from whitelist"),
            (">setlink / /setlink", "Set unban link"),
            (">setlogs / /setlogs", "Set log channel")]:
            embed.add_field(name=f"{a} {name}", value=desc, inline=False)
    elif choice == "premium":
        embed.title = "⭐ Premium Commands"
        embed.color = discord.Color.gold()
        embed.description = "Use `>premium <password>` or `/premium` to activate premium!\n\n"
        embed.add_field(name="━━━ ACTIVATION ━━━", value="", inline=False)
        for name, desc in [
            (">premium / /premium", "Activate premium with password"),
            (">givepremium / /givepremium", "Give premium to a user (Owner only)"),
            (">removepremium / /removepremium", "Remove premium from user (Owner only)"),
            (">setpremiumpass / /setpremiumpass", "Change premium password (Owner only)"),
        ]:
            embed.add_field(name=f"{a} {name}", value=desc, inline=False)
        embed.add_field(name="━━━ PREMIUM FEATURES ━━━", value="", inline=False)
        for name, desc in [
            (">dmall / /dmall", "DM all members across all servers ⭐"),
            (">profilechange / /profilechange", "Change bot PFP in this server only ⭐"),
            (">resetprofile / /resetprofile", "Reset bot PFP in this server ⭐"),
        ]:
            embed.add_field(name=f"{a} {name}", value=desc, inline=False)
    return embed

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced ✅")
    except Exception as e:
        log.exception("Error syncing slash commands: %s", e)
    try:
        await bot.change_presence(activity=discord.Game(name="/help | >help | .gg/nexafyrez"), status=discord.Status.online)
    except Exception:
        log.exception("change_presence error")
    # Start background leveling save task
    bot.loop.create_task(_leveling_autosave())

async def _leveling_autosave():
    await bot.wait_until_ready()
    while not bot.is_closed():
        save_json(leveling_data, LEVELING_FILE)
        await asyncio.sleep(60)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Activity tracking
    uid = message.author.id
    if uid not in member_data:
        member_data[uid] = {"warns": 0, "vc_time": 0, "chat_messages": 0, "abuse": 0}
    member_data[uid]["chat_messages"] += 1

    # Tag + Apply → DM
    if bot.user in message.mentions and "apply" in message.content.lower():
        apply_link = config.get("apply_link", "https://bit.ly/NexafyreZ-offical-website")
        try:
            embed = discord.Embed(title="📝 Application Panel", description="Click below to apply!", color=FN_COLOR)
            embed.add_field(name="🔗 Apply Link", value=f"[Click Here]({apply_link})")
            if message.guild and message.guild.icon:
                embed.set_thumbnail(url=message.guild.icon.url)
            embed.set_footer(text="Made by obito | NexafyreZ")
            view = View()
            view.add_item(Button(label="Apply Now", url=apply_link, style=discord.ButtonStyle.link))
            await message.author.send(embed=embed, view=view)
            await message.reply(embed=small_embed("✅ Check your DM!"), delete_after=5)
        except discord.Forbidden:
            await message.reply(embed=small_embed("❌ Your DMs are closed!"), delete_after=5)
        return

    # Mention response
    if bot.user in message.mentions and "apply" not in message.content.lower():
        embed = discord.Embed(title="Use `>help` | `/help` | `>support` to see all commands", color=FN_COLOR)
        embed.set_footer(text="Made by obito | NexafyreZ")
        try:
            await message.channel.send(embed=embed)
        except Exception:
            pass
        return

    # Security checks
    if features.get("security"):
        if is_bypass(message.author):
            await bot.process_commands(message)
            return
        content = message.content.lower()
        if re.search(LINK_REGEX, content):
            try: await message.delete()
            except Exception: pass
            return
        for w in BAD_WORDS:
            if w in content:
                try: await message.delete()
                except Exception: pass
                return
        if "@everyone" in content or "@here" in content:
            try: await message.delete()
            except Exception: pass
            return
        now_ts = time.time()
        user_spam.setdefault(uid, []).append(now_ts)
        user_spam[uid] = [t for t in user_spam[uid] if now_ts - t < 5]
        if len(user_spam[uid]) > 5:
            try: await message.delete()
            except Exception: pass
            user_spam[uid].clear()
            # Auto-warn for spam
            if uid not in member_data:
                member_data[uid] = {"warns": 0, "vc_time": 0, "chat_messages": 0, "abuse": 0}
            member_data[uid]["warns"] += 1
            warns = member_data[uid]["warns"]
            try:
                we = discord.Embed(title="⚠️ Auto-Warning (Spam Detected)", description=f"You were warned in **{message.guild.name}**", color=discord.Color.orange())
                we.add_field(name="Reason", value="Spam detected (5+ messages in 5 sec)", inline=False)
                we.add_field(name="Warns", value=f"**{warns}/3**", inline=False)
                await message.author.send(embed=we)
            except Exception:
                pass
            try:
                await message.channel.send(embed=small_embed(f"⚠️ {message.author.mention} auto-warned for spam (**{warns}/3**)"), delete_after=5)
            except Exception:
                pass
            if warns >= 3:
                member_data[uid]["warns"] = 0
                try:
                    await message.author.timeout(timedelta(minutes=1), reason="Auto-timeout: 3 spam warns")
                    await message.channel.send(embed=small_embed(f"⏱ {message.author.mention} timed out for **1 min** (3 spam warns)"), delete_after=10)
                except Exception:
                    pass
            return

    # XP gain
    if message.guild:
        gid, user_id = str(message.guild.id), str(message.author.id)
        gd = leveling_data.setdefault(gid, {})
        ud = gd.setdefault(user_id, {"xp": 0, "level": 1})
        ud["xp"] += random.randint(10, 50)
        next_xp = ud["level"] * 1000
        if ud["xp"] >= next_xp:
            ud["level"] += 1
            new_level = ud["level"]
            embed = fn_embed("🎉 Level Up!", f"{message.author.mention} reached level **{new_level}**!")
            if gid in role_rewards and str(new_level) in role_rewards[gid]:
                role = message.guild.get_role(role_rewards[gid][str(new_level)])
                if role:
                    try:
                        await message.author.add_roles(role)
                        embed.description += f"\nYou earned the {role.mention} role!"
                    except Exception:
                        pass
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except Exception:
                pass

    await bot.process_commands(message)

# Anti-nuke events
@bot.event
async def on_guild_channel_delete(channel):
    if features.get("antinuke"):
        await nuke_punish(channel.guild, discord.AuditLogAction.channel_delete, target_id=channel.id)

@bot.event
async def on_guild_channel_update(before, after):
    if features.get("antinuke"):
        await nuke_punish(after.guild, discord.AuditLogAction.channel_update, target_id=after.id)

@bot.event
async def on_guild_role_delete(role):
    if features.get("antinuke"):
        await nuke_punish(role.guild, discord.AuditLogAction.role_delete, target_id=role.id)

@bot.event
async def on_guild_role_update(before, after):
    if features.get("antinuke"):
        await nuke_punish(after.guild, discord.AuditLogAction.role_update, target_id=after.id)

# Welcome / Goodbye / Autorole / Anti-Nuke Bot Detection
@bot.event
async def on_member_join(member):
    guild = member.guild
    gid = str(guild.id)

    # --- Anti-Nuke: Bot add detection ---
    if member.bot and features.get("antinuke"):
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == member.id:
                    inviter = entry.user
                    if inviter and not is_bypass_user_by_guild(guild, inviter):
                        reason = "Anti-Nuke: Added bot without whitelist"
                        try:
                            await inviter.send(embed=discord.Embed(
                                title="🚫 Banned — Anti-Nuke",
                                description=f"You were banned from **{guild.name}** for adding a bot without being whitelisted.",
                                color=discord.Color.red()
                            ))
                        except Exception:
                            pass
                        try:
                            inviter_member = guild.get_member(inviter.id)
                            if inviter_member:
                                await guild.ban(inviter_member, reason=reason, delete_message_days=0)
                        except Exception:
                            pass
                        try:
                            await member.kick(reason=reason)
                        except Exception:
                            pass
                        await log_action(guild, f"🛡️ **{inviter}** banned for adding bot **{member}** without whitelist")
                    break
        except Exception:
            pass
        return  # Don't send welcome for bots

    ch_id = config.get("welcome_channels", {}).get(gid)
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    if ch_id:
        ch = guild.get_channel(ch_id)
        if ch:
            embed = discord.Embed(title=f"{E_WELCOME} WELCOME TO {guild.name.upper()}! {E_WELCOME}", description=f"{member.mention} joined the server! 🎉", color=FN_COLOR)
            embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text="Made by obito")
            gif_path = "assets/welcome.gif"
            if os.path.exists(gif_path):
                file = discord.File(gif_path, filename="welcome.gif")
                embed.set_image(url="attachment://welcome.gif")
                await ch.send(embed=embed, content=member.mention, file=file)
            else:
                await ch.send(embed=embed, content=member.mention)
    # Autorole
    autorole_id = config.get("autorole", {}).get(gid)
    if autorole_id:
        role = guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role, reason="Autorole on join")
            except Exception:
                pass
    try:
        dm_embed = discord.Embed(title=f"{E_WELCOME} Welcome to {guild.name}! {E_WELCOME}", description=f"Hello **{member.name}** 👋 Enjoy your stay!", color=FN_COLOR)
        dm_embed.set_thumbnail(url=avatar_url)
        dm_embed.set_footer(text="Made by obito")
        await member.send(embed=dm_embed)
    except Exception:
        pass

@bot.event
async def on_member_remove(member):
    gid = str(member.guild.id)
    ch_id = config.get("goodbye_channels", {}).get(gid)
    if ch_id:
        ch = member.guild.get_channel(ch_id)
        if ch:
            embed = discord.Embed(title="👋 GOODBYE", description=f"**{member.name}** left **{member.guild.name}**", color=FN_COLOR)
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text="Made by obito")
            await ch.send(embed=embed)

# Global error handler
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=small_embed("❌ You don't have permission!"), delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(embed=small_embed("❌ Member not found!"), delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=small_embed(f"❌ Missing argument: `{error.param.name}`"), delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        log.exception("Command error: %s", error)

# ================= SETUP / UNSETUP =================
def enable_all():
    features["security"] = True
    features["antinuke"] = True
    save_bot_settings()

def disable_all():
    features["security"] = False
    features["antinuke"] = False
    save_bot_settings()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    msg = await ctx.send(embed=small_embed("⚙️ Setting up security systems..."))
    await asyncio.sleep(3)
    enable_all()
    await msg.edit(embed=blue_embed("✅ Successfully Setup", "All security enabled", ctx.guild))

@bot.command()
@commands.has_permissions(administrator=True)
async def unsetup(ctx):
    msg = await ctx.send(embed=small_embed("⚙️ Disabling security systems..."))
    await asyncio.sleep(3)
    disable_all()
    await msg.edit(embed=blue_embed("❌ Security Disabled", "All security disabled", ctx.guild))

@bot.tree.command(name="setup", description="Enable all security & anti-nuke")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    await interaction.response.send_message(embed=small_embed("⚙️ Setting up..."), ephemeral=True)
    await asyncio.sleep(3)
    enable_all()
    await interaction.edit_original_response(embed=blue_embed("✅ Setup", "All security enabled", interaction.guild))

@bot.tree.command(name="unsetup", description="Disable all security")
@app_commands.checks.has_permissions(administrator=True)
async def slash_unsetup(interaction: discord.Interaction):
    await interaction.response.send_message(embed=small_embed("⚙️ Disabling..."), ephemeral=True)
    await asyncio.sleep(3)
    disable_all()
    await interaction.edit_original_response(embed=blue_embed("❌ Disabled", "All security disabled", interaction.guild))

# ================= WHITELIST =================
@bot.command(name="addwhitelist")
@commands.has_permissions(administrator=True)
async def add_whitelist(ctx, member: discord.Member):
    whitelist.add(member.id)
    save_bot_settings()
    await ctx.send(embed=small_embed(f"✅ {member.mention} whitelisted"))

@bot.command(name="removewhitelist")
@commands.has_permissions(administrator=True)
async def remove_whitelist(ctx, member: discord.Member):
    whitelist.discard(member.id)
    save_bot_settings()
    await ctx.send(embed=small_embed(f"❌ {member.mention} removed"))

@bot.tree.command(name="addwhitelist", description="Whitelist a member")
@app_commands.checks.has_permissions(administrator=True)
async def slash_addwhitelist(interaction: discord.Interaction, member: discord.Member):
    whitelist.add(member.id)
    save_bot_settings()
    await interaction.response.send_message(embed=small_embed(f"✅ {member.mention} whitelisted"), ephemeral=True)

@bot.tree.command(name="removewhitelist", description="Remove from whitelist")
@app_commands.checks.has_permissions(administrator=True)
async def slash_removewhitelist(interaction: discord.Interaction, member: discord.Member):
    whitelist.discard(member.id)
    save_bot_settings()
    await interaction.response.send_message(embed=small_embed(f"❌ {member.mention} removed"), ephemeral=True)

# ================= SET LINK / LOGS =================
@bot.command()
@commands.has_permissions(administrator=True)
async def setlink(ctx, link: str):
    global UNBAN_LINK
    UNBAN_LINK = link
    save_bot_settings()
    await ctx.send(embed=small_embed("🔗 Link set successfully"))

@bot.tree.command(name="setlink", description="Set unban link")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setlink(interaction: discord.Interaction, link: str):
    global UNBAN_LINK
    UNBAN_LINK = link
    save_bot_settings()
    await interaction.response.send_message(embed=small_embed("🔗 Link set"), ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def setlogs(ctx, channel: discord.TextChannel):
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    save_bot_settings()
    await ctx.send(embed=small_embed(f"✅ Logs set to {channel.mention}"))

@bot.tree.command(name="setlogs", description="Set log channel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    save_bot_settings()
    await interaction.response.send_message(embed=small_embed(f"✅ Logs: {channel.mention}"), ephemeral=True)

@bot.command(name="setapplylink")
@commands.has_permissions(administrator=True)
async def setapplylink(ctx, *, link: str):
    config["apply_link"] = link
    save_config()
    await ctx.send(embed=small_embed(f"✅ Apply link set!\n🔗 `{link}`"))

@bot.tree.command(name="setapplylink", description="Set the apply link for @bot apply")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setapplylink(interaction: discord.Interaction, link: str):
    config["apply_link"] = link
    save_config()
    await interaction.response.send_message(embed=small_embed(f"✅ Apply link: `{link}`"), ephemeral=True)

# ================= MODERATION =================
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.send(embed=punishment_embed("BAN", reason, ctx.guild.name, str(ctx.author)))
    except Exception: pass
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member} banned!")

@bot.tree.command(name="ban", description="Ban member")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    try: await member.send(embed=punishment_embed("BAN", reason, interaction.guild.name, str(interaction.user)))
    except Exception: pass
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member} banned")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try: await member.send(embed=punishment_embed("KICK", reason, ctx.guild.name, str(ctx.author)))
    except Exception: pass
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} kicked!")

@bot.tree.command(name="kick", description="Kick member")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    try: await member.send(embed=punishment_embed("KICK", reason, interaction.guild.name, str(interaction.user)))
    except Exception: pass
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member} kicked")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int):
    await member.timeout(timedelta(minutes=minutes))
    await ctx.send(f"⏱ {member} timed out for {minutes} min")
    try: await member.send(embed=punishment_embed("TIMEOUT", f"{minutes} minutes", ctx.guild.name, str(ctx.author)))
    except Exception: pass

@bot.tree.command(name="timeout", description="Timeout member")
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    await member.timeout(timedelta(minutes=minutes))
    await interaction.response.send_message(f"⏱ {member} timed out for {minutes} min")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def removetimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"✅ Timeout removed from {member}")

@bot.tree.command(name="removetimeout", description="Remove timeout")
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_removetimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"✅ Timeout removed from {member}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member_name):
    try: name, discrim = member_name.split("#")
    except Exception: return await ctx.send("❌ Use Name#1234")
    async for ban_entry in ctx.guild.bans():
        user = ban_entry.user
        if (user.name, user.discriminator) == (name, discrim):
            await ctx.guild.unban(user)
            return await ctx.send(f"✅ {user} unbanned")
    await ctx.send("❌ Not found in ban list")

@bot.tree.command(name="unban", description="Unban member")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_unban(interaction: discord.Interaction, member_name: str):
    try: name, discrim = member_name.split("#")
    except Exception: return await interaction.response.send_message("❌ Use Name#1234", ephemeral=True)
    async for ban_entry in interaction.guild.bans():
        user = ban_entry.user
        if (user.name, user.discriminator) == (name, discrim):
            await interaction.guild.unban(user)
            return await interaction.response.send_message(f"✅ {user} unbanned")
    await interaction.response.send_message("❌ Not found", ephemeral=True)

# Warn
@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    uid = member.id
    if uid not in member_data:
        member_data[uid] = {"warns": 0, "vc_time": 0, "chat_messages": 0, "abuse": 0}
    member_data[uid]["warns"] += 1
    warns = member_data[uid]["warns"]
    we = discord.Embed(title="⚠️ Warning", description=f"Warned in **{ctx.guild.name}**", color=FN_COLOR)
    we.add_field(name="Reason", value=reason, inline=False)
    we.add_field(name="Count", value=f"{warns}/3", inline=False)
    try: await member.send(embed=we)
    except Exception: pass
    await ctx.send(embed=small_embed(f"⚠️ {member.mention} warned (**{warns}/3**)"))
    if warns >= 3:
        await member.timeout(timedelta(minutes=1))
        await ctx.send(embed=small_embed(f"⏱ {member.mention} auto-timed out (3 warns)"))
        member_data[uid]["warns"] = 0

@bot.tree.command(name="warn", description="Warn a member")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    uid = member.id
    if uid not in member_data:
        member_data[uid] = {"warns": 0, "vc_time": 0, "chat_messages": 0, "abuse": 0}
    member_data[uid]["warns"] += 1
    warns = member_data[uid]["warns"]
    await interaction.response.send_message(embed=small_embed(f"⚠️ {member.mention} warned (**{warns}/3**)"))
    if warns >= 3:
        await member.timeout(timedelta(minutes=1))
        await interaction.followup.send(embed=small_embed(f"⏱ {member.mention} auto-timed out"))
        member_data[uid]["warns"] = 0

# Lock / Unlock
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Channel locked!")

@bot.tree.command(name="lock", description="Lock channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def slash_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked!")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Channel unlocked!")

@bot.tree.command(name="unlock", description="Unlock channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def slash_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked!")

# Purge
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {len(deleted)-1} messages", delete_after=3)

@bot.tree.command(name="purge", description="Delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted **{len(deleted)}** messages", ephemeral=True)

# ================= SCAN (Stats-style) =================
def _make_bar(value, max_val, length=10):
    filled = int((min(value, max_val) / max_val) * length) if max_val > 0 else 0
    return "█" * filled + "░" * (length - filled)

async def _scan_embed(member):
    uid = member.id
    d = member_data.get(uid, {"warns": 0, "vc_time": 0, "chat_messages": 0, "abuse": 0})
    msgs = d.get("chat_messages", 0)
    warns = d.get("warns", 0)
    abuse = d.get("abuse", 0)
    vc_time = d.get("vc_time", 0)
    # XP data
    gid = str(member.guild.id)
    xp_data = leveling_data.get(gid, {}).get(str(uid), {"xp": 0, "level": 1})
    xp, level = xp_data.get("xp", 0), xp_data.get("level", 1)
    next_xp = level * 1000
    # Account age
    created = member.created_at
    joined = member.joined_at
    days_old = (datetime.now(timezone.utc) - created).days if created else 0
    days_in = (datetime.now(timezone.utc) - joined).days if joined else 0
    # Roles
    roles = [r.mention for r in member.roles if r.name != "@everyone"][:8]

    embed = discord.Embed(title=f"📊 Stats — {member.display_name}", color=FN_COLOR)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

    # Profile section
    embed.add_field(name="━━━ PROFILE ━━━", value="", inline=False)
    embed.add_field(name="🆔 User ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="📅 Account Age", value=f"`{days_old}` days", inline=True)
    embed.add_field(name="📥 Server Since", value=f"`{days_in}` days", inline=True)

    # Activity section
    embed.add_field(name="━━━ ACTIVITY ━━━", value="", inline=False)
    embed.add_field(name="💬 Messages", value=f"`{msgs:,}`  {_make_bar(msgs, 1000)}", inline=False)
    embed.add_field(name="🎤 VC Time", value=f"`{vc_time}` min  {_make_bar(vc_time, 600)}", inline=False)

    # Level section
    embed.add_field(name="━━━ LEVELING ━━━", value="", inline=False)
    embed.add_field(name="⭐ Level", value=f"`{level}`", inline=True)
    embed.add_field(name="✨ XP", value=f"`{xp:,}`", inline=True)
    embed.add_field(name="📈 Progress", value=f"`{xp % next_xp}/{next_xp}`  {_make_bar(xp % next_xp, next_xp)}", inline=False)

    # Safety section
    embed.add_field(name="━━━ SAFETY ━━━", value="", inline=False)
    embed.add_field(name="⚠️ Warns", value=f"`{warns}/3`  {_make_bar(warns, 3)}", inline=True)
    embed.add_field(name="🚫 Abuse", value=f"`{abuse}`", inline=True)

    # Roles
    if roles:
        embed.add_field(name=f"━━━ ROLES ({len(roles)}) ━━━", value=" ".join(roles), inline=False)

    embed.set_footer(text="Made by obito | NexafyreZ")
    embed.timestamp = datetime.now()
    return embed

@bot.command()
@commands.has_permissions(kick_members=True)
async def scan(ctx, member: discord.Member):
    embed = await _scan_embed(member)
    await ctx.send(embed=embed)

@bot.tree.command(name="scan", description="Scan member stats & activity")
@app_commands.checks.has_permissions(kick_members=True)
async def slash_scan(interaction: discord.Interaction, member: discord.Member):
    embed = await _scan_embed(member)
    await interaction.response.send_message(embed=embed)

# ================= ROLE =================
@bot.command(name="role", aliases=["r"])
@commands.has_permissions(administrator=True)
async def assign_role(ctx, member: discord.Member, *, role_name: str):
    role = find_role(ctx.guild, role_name)
    if not role:
        return await ctx.send(embed=small_embed(f"❌ Role '{role_name}' not found"))
    if role in member.roles:
        return await ctx.send(embed=small_embed(f"⚠️ {member.mention} already has {role.mention}"))
    await member.add_roles(role)
    await ctx.send(embed=small_embed(f"✅ {member.mention} got {role.mention}"))

@bot.tree.command(name="role", description="Assign role to member")
@app_commands.checks.has_permissions(administrator=True)
async def slash_assign_role(interaction: discord.Interaction, member: discord.Member, role_name: str):
    role = find_role(interaction.guild, role_name)
    if not role:
        return await interaction.response.send_message(embed=small_embed(f"❌ Role '{role_name}' not found"), ephemeral=True)
    if role in member.roles:
        return await interaction.response.send_message(embed=small_embed(f"⚠️ Already has {role.mention}"), ephemeral=True)
    await member.add_roles(role)
    await interaction.response.send_message(embed=small_embed(f"✅ {member.mention} got {role.mention}"), ephemeral=True)

@bot.command(name="removerole", aliases=["rr"])
@commands.has_permissions(administrator=True)
async def remove_role(ctx, member: discord.Member, *, role_name: str):
    role = find_role(ctx.guild, role_name)
    if not role:
        return await ctx.send(embed=small_embed(f"❌ Role '{role_name}' not found"))
    if role not in member.roles:
        return await ctx.send(embed=small_embed(f"⚠️ {member.mention} doesn't have {role.mention}"))
    await member.remove_roles(role)
    await ctx.send(embed=small_embed(f"✅ Removed {role.mention} from {member.mention}"))

@bot.tree.command(name="removerole", description="Remove role from member")
@app_commands.checks.has_permissions(administrator=True)
async def slash_remove_role(interaction: discord.Interaction, member: discord.Member, role_name: str):
    role = find_role(interaction.guild, role_name)
    if not role:
        return await interaction.response.send_message(embed=small_embed(f"❌ Role not found"), ephemeral=True)
    if role not in member.roles:
        return await interaction.response.send_message(embed=small_embed(f"⚠️ Doesn't have {role.mention}"), ephemeral=True)
    await member.remove_roles(role)
    await interaction.response.send_message(embed=small_embed(f"✅ Removed {role.mention}"), ephemeral=True)

# ================= TICKET =================
@bot.command(name="ticket")
@commands.has_permissions(administrator=True)
async def ticket_panel(ctx):
    embed = discord.Embed(title=f"{E_TICKET} 🎫 Ticket Panel", description=f"{E_TICKET2} Select your ticket type from the menu below", color=FN_COLOR)
    await ctx.send(embed=embed, view=TicketTypeView())

@bot.tree.command(name="ticket", description="Send ticket panel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_ticket(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{E_TICKET} 🎫 Ticket Panel", description=f"{E_TICKET2} Select your ticket type from the menu below", color=FN_COLOR)
    await interaction.response.send_message(embed=embed, view=TicketTypeView())

@bot.command(name="close")
async def close_ticket(ctx):
    await ctx.channel.delete()

@bot.command(name="ticketrole")
@commands.has_permissions(administrator=True)
async def add_ticket_role(ctx, role: discord.Role):
    ticket_roles.add(role.id)
    await ctx.send(f"✅ Added {role.mention} as ticket staff role\n✓ They can now create and view tickets")

@bot.command(name="removeticketrole")
@commands.has_permissions(administrator=True)
async def remove_ticket_role(ctx, role: discord.Role):
    if role.id in ticket_roles:
        ticket_roles.remove(role.id)
        await ctx.send(f"✅ Removed {role.mention} from ticket staff roles")
    else:
        await ctx.send(f"❌ {role.mention} is not a ticket staff role")

@bot.tree.command(name="ticketrole", description="Add staff role for tickets")
@app_commands.checks.has_permissions(administrator=True)
async def slash_ticketrole(interaction: discord.Interaction, role: discord.Role):
    ticket_roles.add(role.id)
    await interaction.response.send_message(f"✅ Added {role.mention} as ticket staff role")

@bot.tree.command(name="removeticketrole", description="Remove staff role from tickets")
@app_commands.checks.has_permissions(administrator=True)
async def slash_removeticketrole(interaction: discord.Interaction, role: discord.Role):
    if role.id in ticket_roles:
        ticket_roles.remove(role.id)
        await interaction.response.send_message(f"✅ Removed {role.mention}")
    else:
        await interaction.response.send_message(f"❌ {role.mention} is not a ticket role", ephemeral=True)

# ================= AUTOROLE =================
@bot.command(name="autorole")
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    gid = str(ctx.guild.id)
    config.setdefault("autorole", {})[gid] = role.id
    save_config()
    await ctx.send(embed=small_embed(f"✅ Autorole set to {role.mention}\nNew members will get this role automatically"))

@bot.command(name="removeautorole")
@commands.has_permissions(administrator=True)
async def removeautorole(ctx):
    gid = str(ctx.guild.id)
    if config.get("autorole", {}).get(gid):
        config["autorole"].pop(gid, None)
        save_config()
        await ctx.send(embed=small_embed("✅ Autorole removed"))
    else:
        await ctx.send(embed=small_embed("❌ No autorole is set"))

@bot.tree.command(name="autorole", description="Set autorole for new members")
@app_commands.checks.has_permissions(administrator=True)
async def slash_autorole(interaction: discord.Interaction, role: discord.Role):
    gid = str(interaction.guild.id)
    config.setdefault("autorole", {})[gid] = role.id
    save_config()
    await interaction.response.send_message(embed=small_embed(f"✅ Autorole: {role.mention}"))

@bot.tree.command(name="removeautorole", description="Remove autorole")
@app_commands.checks.has_permissions(administrator=True)
async def slash_removeautorole(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    if config.get("autorole", {}).get(gid):
        config["autorole"].pop(gid, None)
        save_config()
        await interaction.response.send_message(embed=small_embed("✅ Autorole removed"))
    else:
        await interaction.response.send_message(embed=small_embed("❌ Not set"), ephemeral=True)


# ================= WELCOME / GOODBYE CONFIG =================
@bot.command()
@commands.has_permissions(administrator=True)
async def welcomeset(ctx, channel: discord.TextChannel):
    config.setdefault("welcome_channels", {})[str(ctx.guild.id)] = channel.id
    save_config()
    await ctx.send(f"✅ Welcome channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def welcomeremove(ctx):
    config.get("welcome_channels", {}).pop(str(ctx.guild.id), None)
    save_config()
    await ctx.send("❌ Welcome removed")

@bot.command()
@commands.has_permissions(administrator=True)
async def goodbyeset(ctx, channel: discord.TextChannel):
    config.setdefault("goodbye_channels", {})[str(ctx.guild.id)] = channel.id
    save_config()
    await ctx.send(f"✅ Goodbye channel: {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def goodbyeremove(ctx):
    config.get("goodbye_channels", {}).pop(str(ctx.guild.id), None)
    save_config()
    await ctx.send("❌ Goodbye removed")

@bot.tree.command(name="welcomeset", description="Set welcome channel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_welcomeset(interaction: discord.Interaction, channel: discord.TextChannel):
    config.setdefault("welcome_channels", {})[str(interaction.guild.id)] = channel.id
    save_config()
    await interaction.response.send_message(f"✅ Welcome: {channel.mention}", ephemeral=True)

@bot.tree.command(name="welcomeremove", description="Remove welcome channel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_welcomeremove(interaction: discord.Interaction):
    config.get("welcome_channels", {}).pop(str(interaction.guild.id), None)
    save_config()
    await interaction.response.send_message("❌ Welcome removed", ephemeral=True)

@bot.tree.command(name="setgoodbye", description="Set goodbye channel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_goodbyeset(interaction: discord.Interaction, channel: discord.TextChannel):
    config.setdefault("goodbye_channels", {})[str(interaction.guild.id)] = channel.id
    save_config()
    await interaction.response.send_message(f"✅ Goodbye: {channel.mention}", ephemeral=True)

@bot.tree.command(name="removegoodbye", description="Remove goodbye channel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_goodbyeremove(interaction: discord.Interaction):
    config.get("goodbye_channels", {}).pop(str(interaction.guild.id), None)
    save_config()
    await interaction.response.send_message("❌ Goodbye removed", ephemeral=True)

# ================= VOICE COMMANDS =================

async def _safe_vc_cleanup(guild):
    """Force cleanup any stale/stuck voice client."""
    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
    except Exception:
        pass
    await asyncio.sleep(0.5)


def _vc_info_embed(title, desc, channel=None):
    """Build a rich embed for VC actions."""
    embed = discord.Embed(title=title, description=desc, color=FN_COLOR)
    if channel:
        members_in_vc = len([m for m in channel.members if not m.bot])
        embed.add_field(name="🔊 Channel", value=channel.name, inline=True)
        embed.add_field(name="👥 Members", value=str(members_in_vc), inline=True)
        embed.add_field(name="📡 Bitrate", value=f"{channel.bitrate // 1000}kbps", inline=True)
    embed.set_footer(text="Made by obito | NexafyreZ")
    return embed


@bot.command()
@commands.has_permissions(manage_channels=True)
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send(embed=small_embed("❌ You must be in a voice channel first!"), delete_after=10)
    vc = ctx.author.voice.channel

    # Already in same channel
    if ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
        if ctx.guild.voice_client.channel.id == vc.id:
            return await ctx.send(embed=_vc_info_embed("✅ Already Connected", f"I'm already in **{vc.name}**!", vc))
        # Move to new channel
        try:
            await ctx.guild.voice_client.move_to(vc)
            return await ctx.send(embed=_vc_info_embed("✅ Moved", f"Moved to **{vc.name}**!", vc))
        except Exception:
            await _safe_vc_cleanup(ctx.guild)

    # Fresh connect with timeout
    msg = await ctx.send(embed=small_embed(f"⏳ Connecting to **{vc.name}**..."))
    try:
        await asyncio.wait_for(vc.connect(self_deaf=True), timeout=10)
        await msg.edit(embed=_vc_info_embed("✅ Connected", f"Successfully joined **{vc.name}**!", vc))
    except asyncio.TimeoutError:
        await _safe_vc_cleanup(ctx.guild)
        await msg.edit(embed=small_embed("❌ Connection timed out! Please try again."))
    except discord.ClientException:
        # Already connected somehow — cleanup and retry
        await _safe_vc_cleanup(ctx.guild)
        try:
            await asyncio.wait_for(vc.connect(self_deaf=True), timeout=10)
            await msg.edit(embed=_vc_info_embed("✅ Connected", f"Successfully joined **{vc.name}**!", vc))
        except Exception as e:
            await msg.edit(embed=small_embed(f"❌ Failed to connect: {e}"))
    except Exception as e:
        await _safe_vc_cleanup(ctx.guild)
        await msg.edit(embed=small_embed(f"❌ Failed to connect: {e}"))


@bot.tree.command(name="join", description="Bot joins your voice channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def slash_join(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            embed=small_embed("❌ You must be in a voice channel first!"), ephemeral=True
        )
    vc = interaction.user.voice.channel

    # Already in same channel
    if interaction.guild.voice_client and interaction.guild.voice_client.is_connected():
        if interaction.guild.voice_client.channel.id == vc.id:
            return await interaction.response.send_message(
                embed=_vc_info_embed("✅ Already Connected", f"I'm already in **{vc.name}**!", vc)
            )
        try:
            await interaction.guild.voice_client.move_to(vc)
            return await interaction.response.send_message(
                embed=_vc_info_embed("✅ Moved", f"Moved to **{vc.name}**!", vc)
            )
        except Exception:
            await _safe_vc_cleanup(interaction.guild)

    await interaction.response.defer()
    try:
        await asyncio.wait_for(vc.connect(self_deaf=True), timeout=10)
        await interaction.followup.send(embed=_vc_info_embed("✅ Connected", f"Successfully joined **{vc.name}**!", vc))
    except asyncio.TimeoutError:
        await _safe_vc_cleanup(interaction.guild)
        await interaction.followup.send(embed=small_embed("❌ Connection timed out! Please try again."))
    except discord.ClientException:
        await _safe_vc_cleanup(interaction.guild)
        try:
            await asyncio.wait_for(vc.connect(self_deaf=True), timeout=10)
            await interaction.followup.send(
                embed=_vc_info_embed("✅ Connected", f"Successfully joined **{vc.name}**!", vc)
            )
        except Exception as e:
            await interaction.followup.send(embed=small_embed(f"❌ Failed to connect: {e}"))
    except Exception as e:
        await _safe_vc_cleanup(interaction.guild)
        await interaction.followup.send(embed=small_embed(f"❌ Failed to connect: {e}"))


@bot.command()
@commands.has_permissions(manage_channels=True)
async def leave(ctx):
    if not ctx.guild.voice_client:
        return await ctx.send(embed=small_embed("❌ I'm not in any voice channel!"), delete_after=10)
    name = ctx.guild.voice_client.channel.name
    try:
        await ctx.guild.voice_client.disconnect(force=True)
    except Exception:
        await _safe_vc_cleanup(ctx.guild)
    await ctx.send(embed=_vc_info_embed("👋 Disconnected", f"Left **{name}**"))


@bot.tree.command(name="leave", description="Bot leaves voice channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def slash_leave(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        return await interaction.response.send_message(
            embed=small_embed("❌ I'm not in any voice channel!"), ephemeral=True
        )
    name = interaction.guild.voice_client.channel.name
    try:
        await interaction.guild.voice_client.disconnect(force=True)
    except Exception:
        await _safe_vc_cleanup(interaction.guild)
    await interaction.response.send_message(embed=_vc_info_embed("👋 Disconnected", f"Left **{name}**"))


@bot.command(name="pull")
@commands.has_permissions(administrator=True)
async def pull(ctx, member: discord.Member = None):
    if not ctx.author.voice:
        return await ctx.send(embed=small_embed("❌ You must be in a voice channel!"), delete_after=10)
    target = ctx.author.voice.channel
    if member is None:
        msg = await ctx.send(embed=small_embed(f"⏳ Pulling all members to **{target.name}**..."))
        count, failed = 0, 0
        for m in ctx.guild.members:
            if m.voice and m.voice.channel and m.voice.channel != target and not m.bot:
                try:
                    await m.move_to(target)
                    count += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    failed += 1
        result = f"🎤 Pulled **{count}** members to **{target.name}**"
        if failed:
            result += f"\n⚠️ Failed to pull **{failed}** members"
        await msg.edit(embed=_vc_info_embed("🎤 Pull Complete", result, target))
    else:
        if not member.voice:
            return await ctx.send(embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), delete_after=10)
        try:
            await member.move_to(target)
            await ctx.send(embed=_vc_info_embed("🎤 Pulled", f"Pulled {member.mention} to **{target.name}**", target))
        except Exception as e:
            await ctx.send(embed=small_embed(f"❌ Failed to pull {member.mention}: {e}"))


@bot.tree.command(name="pull", description="Pull members to your voice channel")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Specific member to pull (leave empty for all)")
async def slash_pull(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            embed=small_embed("❌ You must be in a voice channel!"), ephemeral=True
        )
    target = interaction.user.voice.channel
    if member:
        if not member.voice:
            return await interaction.response.send_message(
                embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), ephemeral=True
            )
        try:
            await member.move_to(target)
            await interaction.response.send_message(
                embed=_vc_info_embed("🎤 Pulled", f"Pulled {member.mention} to **{target.name}**", target)
            )
        except Exception as e:
            await interaction.response.send_message(embed=small_embed(f"❌ Failed: {e}"), ephemeral=True)
    else:
        await interaction.response.defer()
        count, failed = 0, 0
        for m in interaction.guild.members:
            if m.voice and m.voice.channel and m.voice.channel != target and not m.bot:
                try:
                    await m.move_to(target)
                    count += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    failed += 1
        result = f"🎤 Pulled **{count}** members to **{target.name}**"
        if failed:
            result += f"\n⚠️ Failed to pull **{failed}** members"
        await interaction.followup.send(embed=_vc_info_embed("🎤 Pull Complete", result, target))


@bot.command(name="vcmute")
@commands.has_permissions(administrator=True)
async def vcmute(ctx, member: discord.Member):
    if not member.voice:
        return await ctx.send(embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), delete_after=10)
    try:
        await member.edit(mute=True)
        embed = discord.Embed(
            title="🔇 Server Muted",
            description=f"{member.mention} has been **muted** in voice.",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made by obito | NexafyreZ")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(embed=small_embed(f"❌ Failed to mute: {e}"))


@bot.tree.command(name="vcmute", description="Server mute a member in VC")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="The member to mute")
async def slash_vcmute(interaction: discord.Interaction, member: discord.Member):
    if not member.voice:
        return await interaction.response.send_message(
            embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), ephemeral=True
        )
    try:
        await member.edit(mute=True)
        embed = discord.Embed(
            title="🔇 Server Muted",
            description=f"{member.mention} has been **muted** in voice.",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Made by obito | NexafyreZ")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(embed=small_embed(f"❌ Failed: {e}"), ephemeral=True)


@bot.command(name="vcunmute")
@commands.has_permissions(administrator=True)
async def vcunmute(ctx, member: discord.Member):
    if not member.voice:
        return await ctx.send(embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), delete_after=10)
    try:
        await member.edit(mute=False)
        embed = discord.Embed(
            title="🔊 Server Unmuted",
            description=f"{member.mention} has been **unmuted** in voice.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by obito | NexafyreZ")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(embed=small_embed(f"❌ Failed to unmute: {e}"))


@bot.tree.command(name="vcunmute", description="Server unmute a member in VC")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="The member to unmute")
async def slash_vcunmute(interaction: discord.Interaction, member: discord.Member):
    if not member.voice:
        return await interaction.response.send_message(
            embed=small_embed(f"❌ {member.mention} is not in any voice channel!"), ephemeral=True
        )
    try:
        await member.edit(mute=False)
        embed = discord.Embed(
            title="🔊 Server Unmuted",
            description=f"{member.mention} has been **unmuted** in voice.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Made by obito | NexafyreZ")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(embed=small_embed(f"❌ Failed: {e}"), ephemeral=True)

# ================= LINKPROTECT =================
@bot.command(name="linkprotect")
@commands.has_permissions(administrator=True)
async def linkprotect_prefix(ctx, *, link: str):
    protected = protect_link(link)
    try:
        await ctx.author.send(f"🔐 **Protected link:**\n{protected}")
        await ctx.reply("✅ Check your DM!", delete_after=5)
    except discord.Forbidden:
        await ctx.reply("❌ DM closed", delete_after=5)

@bot.tree.command(name="linkprotect", description="Protect a link → DM (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def linkprotect_slash(interaction: discord.Interaction, link: str):
    protected = protect_link(link)
    try:
        await interaction.user.send(f"🔐 **Protected link:**\n{protected}")
        await interaction.response.send_message("✅ Check DM!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ DM closed", ephemeral=True)

# ================= BOTINFO =================
import sys
import platform

@bot.command(name="botinfo")
async def botinfo(ctx):
    uptime = datetime.now() - BOT_START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    total_members = sum(g.member_count or 0 for g in bot.guilds)
    total_cmds = len(bot.commands) + len(bot.tree.get_commands())
    embed = fn_embed("🤖 Bot Info")
    embed.add_field(name="📛 Name", value=f"`{bot.user.name}`", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="🏓 Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="🌐 Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="👥 Total Members", value=f"`{total_members:,}`", inline=True)
    embed.add_field(name="📜 Total Commands", value=f"`{total_cmds}`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{hours}h {minutes}m {seconds}s`", inline=True)
    embed.add_field(name="🐍 Python", value=f"`{sys.version.split()[0]}`", inline=True)
    embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
    embed.add_field(name="🔒 Security", value=f"`{'ON' if features.get('security') else 'OFF'}`", inline=True)
    embed.add_field(name="🛡️ Anti-Nuke", value=f"`{'ON' if features.get('antinuke') else 'OFF'}`", inline=True)
    embed.add_field(name="💻 Platform", value=f"`{platform.system()}`", inline=True)
    embed.set_footer(text="Made by obito | NexafyreZ")
    embed.timestamp = datetime.now()
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.reply(embed=embed)

@bot.tree.command(name="botinfo", description="Bot stats & info")
async def slash_botinfo(interaction: discord.Interaction):
    uptime = datetime.now() - BOT_START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    total_members = sum(g.member_count or 0 for g in bot.guilds)
    total_cmds = len(bot.commands) + len(bot.tree.get_commands())
    embed = fn_embed("🤖 Bot Info")
    embed.add_field(name="📛 Name", value=f"`{bot.user.name}`", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="🏓 Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="🌐 Servers", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="👥 Total Members", value=f"`{total_members:,}`", inline=True)
    embed.add_field(name="📜 Total Commands", value=f"`{total_cmds}`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{hours}h {minutes}m {seconds}s`", inline=True)
    embed.add_field(name="🐍 Python", value=f"`{sys.version.split()[0]}`", inline=True)
    embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
    embed.add_field(name="🔒 Security", value=f"`{'ON' if features.get('security') else 'OFF'}`", inline=True)
    embed.add_field(name="🛡️ Anti-Nuke", value=f"`{'ON' if features.get('antinuke') else 'OFF'}`", inline=True)
    embed.add_field(name="💻 Platform", value=f"`{platform.system()}`", inline=True)
    embed.set_footer(text="Made by obito | NexafyreZ")
    embed.timestamp = datetime.now()
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

# ================= UTILITY =================
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="ping", description="Bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = fn_embed("📌 Server Info")
    embed.add_field(name="Name", value=g.name)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Owner", value=g.owner)
    embed.add_field(name="ID", value=g.id)
    await ctx.send(embed=embed)

@bot.tree.command(name="serverinfo", description="Server info")
async def slash_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = fn_embed("📌 Server Info")
    embed.add_field(name="Name", value=g.name)
    embed.add_field(name="Members", value=g.member_count)
    embed.add_field(name="Owner", value=g.owner)
    embed.add_field(name="ID", value=g.id)
    await interaction.response.send_message(embed=embed)

@bot.command()
async def user(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = fn_embed("👤 User Info")
    embed.add_field(name="Username", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%d-%m-%Y") if member.joined_at else "Unknown")
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.tree.command(name="user", description="User info")
async def slash_user(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = fn_embed("👤 User Info")
    embed.add_field(name="Username", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%d-%m-%Y") if member.joined_at else "Unknown")
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.command(name="say")
async def say(ctx, *, text: str):
    try: await ctx.message.delete()
    except Exception: pass
    clean = discord.utils.escape_mentions(text)
    await ctx.send(clean, allowed_mentions=discord.AllowedMentions.none())

@bot.tree.command(name="say", description="Bot repeats your text")
async def slash_say(interaction: discord.Interaction, text: str):
    clean = discord.utils.escape_mentions(text)
    await interaction.response.send_message(clean, allowed_mentions=discord.AllowedMentions.none())

# Avatar
def _avatar_embed(member):
    embed = discord.Embed(title=f"Avatar — {member.name}", description=f"[**Download**]({member.display_avatar.url})", color=FN_COLOR, timestamp=datetime.now())
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {member}", icon_url=member.display_avatar.url)
    return embed

@bot.command(name="avatar", aliases=["av"])
async def avatar_text(ctx, member: discord.Member = None):
    await ctx.send(embed=_avatar_embed(member or ctx.author))

@bot.tree.command(name="avatar", description="Show avatar")
async def avatar_slash(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.send_message(embed=_avatar_embed(member or interaction.user))

# ================= HELP =================
@bot.command()
async def help(ctx):
    guild = ctx.guild
    view = HelpSelectView(guild)
    embed = discord.Embed(title=f"{E_BULLET} Bot Commands Menu", description="Select a category below to see commands", color=FN_COLOR)
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Made by obito 💖 | NexafyreZ")
    await ctx.send(embed=embed, view=view)

@bot.tree.command(name="help", description="Show all commands")
async def slash_help(interaction: discord.Interaction):
    guild = interaction.guild
    view = HelpSelectView(guild)
    embed = discord.Embed(title=f"{E_BULLET} Bot Commands Menu", description="Select a category below to see commands", color=FN_COLOR)
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Made by obito 💖 | NexafyreZ")
    await interaction.response.send_message(embed=embed, view=view)

# ================= SUPPORT =================
@bot.command(name="support")
async def support(ctx):
    embed = fn_embed("📞 Support", "Need help? Here's how:")
    embed.add_field(name="📧 Email", value="espadakaizen@gmail.com", inline=False)
    embed.add_field(name="💬 Discord", value="[Join](https://discord.gg/nexafyrez)", inline=False)
    embed.add_field(name="🌐 Website", value="[Visit](https://espada.work.gd/)", inline=False)
    embed.add_field(name="❓ Commands", value="Use `>help` | `/help` to see all commands", inline=False)
    embed.set_footer(text="Made by obito | NexafyreZ")
    embed.timestamp = datetime.now()
    await ctx.reply(embed=embed)

@bot.tree.command(name="support", description="Get support info")
async def slash_support(interaction: discord.Interaction):
    embed = fn_embed("📞 Support", "Need help? Here's how:")
    embed.add_field(name="📧 Email", value="espadakaizen@gmail.com", inline=False)
    embed.add_field(name="💬 Discord", value="[Join](https://discord.gg/nexafyrez)", inline=False)
    embed.add_field(name="🌐 Website", value="[Visit](https://espada.work.gd/)", inline=False)
    embed.add_field(name="❓ Commands", value="Use `>help` | `/help` to see all commands", inline=False)
    embed.set_footer(text="Made by obito | NexafyreZ")
    embed.timestamp = datetime.now()
    await interaction.response.send_message(embed=embed)

# ================= GIVEAWAY =================
@bot.command(name="giveaway", aliases=["ga"])
@commands.has_permissions(manage_messages=True)
async def giveaway(ctx, duration: str, *, prize: str):
    dur_ms = parse_duration(duration)
    if not dur_ms:
        return await ctx.reply(embed=small_embed("❌ Invalid duration. Use: `10m`, `1h`, `2d`, `30s`"))
    gid = int(datetime.now().timestamp() * 1000)
    end_time = datetime.now() + timedelta(milliseconds=dur_ms)
    embed = fn_embed("🎉 GIVEAWAY 🎉", f"**Prize:** {prize}")
    embed.add_field(name="⏱️ Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
    embed.add_field(name="👥 Enter", value="React with 🎉", inline=False)
    embed.set_footer(text=f"Giveaway ID: {gid}")
    embed.timestamp = datetime.now()
    msg = await ctx.reply(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[gid] = {"message_id": msg.id, "channel_id": ctx.channel.id, "prize": prize, "end_time": end_time, "created_by_name": ctx.author.name}
    await asyncio.sleep(dur_ms / 1000)
    await _end_giveaway(gid)

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_giveaway(interaction: discord.Interaction, duration: str, prize: str):
    dur_ms = parse_duration(duration)
    if not dur_ms:
        return await interaction.response.send_message(embed=small_embed("❌ Invalid duration"), ephemeral=True)
    await interaction.response.defer()
    gid = int(datetime.now().timestamp() * 1000)
    end_time = datetime.now() + timedelta(milliseconds=dur_ms)
    embed = fn_embed("🎉 GIVEAWAY 🎉", f"**Prize:** {prize}")
    embed.add_field(name="⏱️ Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
    embed.add_field(name="👥 Enter", value="React with 🎉", inline=False)
    embed.set_footer(text=f"Giveaway ID: {gid}")
    msg = await interaction.followup.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[gid] = {"message_id": msg.id, "channel_id": interaction.channel.id, "prize": prize, "end_time": end_time, "created_by_name": interaction.user.name}
    await asyncio.sleep(dur_ms / 1000)
    await _end_giveaway(gid)

@bot.command(name="removegiveaway", aliases=["rmga"])
@commands.has_permissions(manage_messages=True)
async def removegiveaway(ctx, giveaway_id: int):
    if giveaway_id not in giveaways:
        return await ctx.reply(embed=small_embed(f"❌ Giveaway `{giveaway_id}` not found"))
    ga = giveaways.pop(giveaway_id)
    await ctx.reply(embed=small_embed(f"✅ Giveaway removed: **{ga['prize']}**"))

@bot.command(name="endgiveaway", aliases=["endga"])
@commands.has_permissions(manage_messages=True)
async def endgiveaway(ctx, giveaway_id: int):
    if giveaway_id not in giveaways:
        return await ctx.reply(embed=small_embed(f"❌ Giveaway `{giveaway_id}` not found"))
    await _end_giveaway(giveaway_id)

@bot.command(name="deletegiveaway", aliases=["delga"])
@commands.has_permissions(administrator=True)
async def deletegiveaway(ctx):
    if not giveaways:
        return await ctx.reply(embed=small_embed("❌ No active giveaways"))
    count = len(giveaways)
    giveaways.clear()
    await ctx.reply(embed=small_embed(f"✅ Deleted {count} giveaways"))

@bot.tree.command(name="removegiveaway", description="Remove a giveaway")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_removegiveaway(interaction: discord.Interaction, giveaway_id: int):
    if giveaway_id not in giveaways:
        return await interaction.response.send_message("❌ Not found", ephemeral=True)
    ga = giveaways.pop(giveaway_id)
    await interaction.response.send_message(embed=small_embed(f"✅ Removed: **{ga['prize']}**"))

@bot.tree.command(name="endgiveaway", description="End giveaway & pick winner")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_endgiveaway(interaction: discord.Interaction, giveaway_id: int):
    if giveaway_id not in giveaways:
        return await interaction.response.send_message("❌ Not found", ephemeral=True)
    await interaction.response.defer()
    await _end_giveaway(giveaway_id, interaction=interaction)

@bot.tree.command(name="deletegiveaway", description="Delete all giveaways")
@app_commands.checks.has_permissions(administrator=True)
async def slash_deletegiveaway(interaction: discord.Interaction):
    if not giveaways:
        return await interaction.response.send_message("❌ None active", ephemeral=True)
    count = len(giveaways)
    giveaways.clear()
    await interaction.response.send_message(embed=small_embed(f"✅ Deleted {count} giveaways"))

async def _end_giveaway(gid, interaction=None):
    if gid not in giveaways:
        return
    ga = giveaways.pop(gid)
    try:
        ch = bot.get_channel(ga["channel_id"])
        if not ch:
            return
        msg = await ch.fetch_message(ga["message_id"])
        reaction = None
        for r in msg.reactions:
            if str(r.emoji) == "🎉":
                reaction = r
                break
        if not reaction:
            embed = fn_embed("❌ Giveaway Ended", f"**{ga['prize']}** — No participants")
            if interaction:
                await interaction.followup.send(embed=embed)
            else:
                await ch.send(embed=embed)
            return
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            embed = fn_embed("❌ Giveaway Ended", f"**{ga['prize']}** — No valid participants")
            if interaction:
                await interaction.followup.send(embed=embed)
            else:
                await ch.send(embed=embed)
            return
        winner = random.choice(users)
        embed = fn_embed("🎊 Giveaway Ended!", f"**Prize:** {ga['prize']}")
        embed.add_field(name="🏆 Winner", value=winner.mention, inline=True)
        embed.add_field(name="👥 Participants", value=str(len(users)), inline=True)
        embed.set_footer(text=f"Started by: {ga['created_by_name']}")
        embed.timestamp = datetime.now()
        if interaction:
            await interaction.followup.send(embed=embed)
        else:
            await ch.send(embed=embed)
    except Exception as e:
        log.exception("Giveaway end error: %s", e)

# ================= LEVELING =================
@bot.command(name="rank")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid, uid = str(ctx.guild.id), str(member.id)
    ud = leveling_data.get(gid, {}).get(uid, {"xp": 0, "level": 1})
    xp, level = ud.get("xp", 0), ud.get("level", 1)
    embed = fn_embed(f"📊 {member.name}'s Rank")
    embed.add_field(name="Level", value=f"`{level}`", inline=True)
    embed.add_field(name="XP", value=f"`{xp:,}`", inline=True)
    embed.add_field(name="Progress", value=f"`{xp % (level*1000)}/{level*1000}`", inline=False)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await ctx.reply(embed=embed)

@bot.tree.command(name="rank", description="Check rank & XP")
async def slash_rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    gid, uid = str(interaction.guild.id), str(member.id)
    ud = leveling_data.get(gid, {}).get(uid, {"xp": 0, "level": 1})
    xp, level = ud.get("xp", 0), ud.get("level", 1)
    embed = fn_embed(f"📊 {member.name}'s Rank")
    embed.add_field(name="Level", value=f"`{level}`", inline=True)
    embed.add_field(name="XP", value=f"`{xp:,}`", inline=True)
    embed.add_field(name="Progress", value=f"`{xp % (level*1000)}/{level*1000}`", inline=False)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.command(name="leaderboard")
async def leaderboard(ctx):
    gid = str(ctx.guild.id)
    gd = leveling_data.get(gid, {})
    if not gd:
        return await ctx.reply(embed=fn_embed("📊 Leaderboard", "No data yet!"))
    top = sorted(gd.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
    embed = fn_embed("📊 Top 10")
    for i, (uid, d) in enumerate(top, 1):
        try:
            u = await bot.fetch_user(int(uid))
            embed.add_field(name=f"{i}. {u.name}", value=f"Level: {d.get('level',1)} | XP: {d.get('xp',0)}", inline=False)
        except Exception:
            pass
    await ctx.reply(embed=embed)

@bot.tree.command(name="leaderboard", description="Top 10 by XP")
async def slash_leaderboard(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    gd = leveling_data.get(gid, {})
    if not gd:
        return await interaction.response.send_message(embed=fn_embed("📊 Leaderboard", "No data yet!"))
    top = sorted(gd.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
    embed = fn_embed("📊 Top 10")
    for i, (uid, d) in enumerate(top, 1):
        try:
            u = await bot.fetch_user(int(uid))
            embed.add_field(name=f"{i}. {u.name}", value=f"Level: {d.get('level',1)} | XP: {d.get('xp',0)}", inline=False)
        except Exception:
            pass
    await interaction.response.send_message(embed=embed)

@bot.command(name="reset-xp")
@commands.has_permissions(administrator=True)
async def reset_xp(ctx, member: discord.Member):
    gid, uid = str(ctx.guild.id), str(member.id)
    if gid in leveling_data and uid in leveling_data[gid]:
        leveling_data[gid][uid] = {"xp": 0, "level": 1}
        save_json(leveling_data, LEVELING_FILE)
        await ctx.reply(embed=small_embed(f"✅ {member.mention} XP reset"))
    else:
        await ctx.reply(embed=small_embed(f"❌ No data for {member.mention}"))

@bot.tree.command(name="reset-xp", description="Reset member XP (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_reset_xp(interaction: discord.Interaction, member: discord.Member):
    gid, uid = str(interaction.guild.id), str(member.id)
    if gid in leveling_data and uid in leveling_data[gid]:
        leveling_data[gid][uid] = {"xp": 0, "level": 1}
        save_json(leveling_data, LEVELING_FILE)
        await interaction.response.send_message(embed=small_embed(f"✅ {member.mention} XP reset"))
    else:
        await interaction.response.send_message(embed=small_embed("❌ No data"), ephemeral=True)

@bot.command(name="give-xp")
@commands.has_permissions(administrator=True)
async def give_xp(ctx, member: discord.Member, amount: int):
    if amount < 1 or amount > 1000000000:
        return await ctx.reply(embed=small_embed("❌ Amount must be 1 to 1,000,000,000"))
    gid, uid = str(ctx.guild.id), str(member.id)
    gd = leveling_data.setdefault(gid, {})
    ud = gd.setdefault(uid, {"xp": 0, "level": 1})
    ud["xp"] += amount
    if ud["xp"] >= ud["level"] * 1000:
        ud["level"] += 1
    save_json(leveling_data, LEVELING_FILE)
    embed = fn_embed("✅ XP Given", f"Gave **{amount:,} XP** to {member.mention}")
    embed.add_field(name="Level", value=f"`{ud['level']}`", inline=True)
    embed.add_field(name="XP", value=f"`{ud['xp']:,}`", inline=True)
    await ctx.reply(embed=embed)

@bot.tree.command(name="give-xp", description="Give XP to member (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_give_xp(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount < 1 or amount > 1000000000:
        return await interaction.response.send_message("❌ 1 to 1B", ephemeral=True)
    gid, uid = str(interaction.guild.id), str(member.id)
    gd = leveling_data.setdefault(gid, {})
    ud = gd.setdefault(uid, {"xp": 0, "level": 1})
    ud["xp"] += amount
    if ud["xp"] >= ud["level"] * 1000:
        ud["level"] += 1
    save_json(leveling_data, LEVELING_FILE)
    embed = fn_embed("✅ XP Given", f"Gave **{amount:,} XP** to {member.mention}")
    embed.add_field(name="Level", value=f"`{ud['level']}`", inline=True)
    embed.add_field(name="XP", value=f"`{ud['xp']:,}`", inline=True)
    await interaction.response.send_message(embed=embed)

# Role Rewards
@bot.command(name="set-role-reward")
@commands.has_permissions(administrator=True)
async def set_role_reward(ctx, level: int, role: discord.Role):
    gid = str(ctx.guild.id)
    role_rewards.setdefault(gid, {})[str(level)] = role.id
    save_json(role_rewards, ROLE_REWARDS_FILE)
    await ctx.reply(embed=small_embed(f"✅ Level **{level}** → {role.mention}"))

@bot.tree.command(name="set-role-reward", description="Set role reward for level (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_set_role_reward(interaction: discord.Interaction, level: int, role: discord.Role):
    gid = str(interaction.guild.id)
    role_rewards.setdefault(gid, {})[str(level)] = role.id
    save_json(role_rewards, ROLE_REWARDS_FILE)
    await interaction.response.send_message(embed=small_embed(f"✅ Level **{level}** → {role.mention}"))

@bot.command(name="remove-role-reward")
@commands.has_permissions(administrator=True)
async def remove_role_reward(ctx, level: int):
    gid = str(ctx.guild.id)
    if gid in role_rewards and str(level) in role_rewards[gid]:
        del role_rewards[gid][str(level)]
        save_json(role_rewards, ROLE_REWARDS_FILE)
        await ctx.reply(embed=small_embed(f"✅ Removed reward for level **{level}**"))
    else:
        await ctx.reply(embed=small_embed(f"❌ No reward for level **{level}**"))

@bot.tree.command(name="remove-role-reward", description="Remove role reward (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_remove_role_reward(interaction: discord.Interaction, level: int):
    gid = str(interaction.guild.id)
    if gid in role_rewards and str(level) in role_rewards[gid]:
        del role_rewards[gid][str(level)]
        save_json(role_rewards, ROLE_REWARDS_FILE)
        await interaction.response.send_message(embed=small_embed(f"✅ Removed reward for level **{level}**"))
    else:
        await interaction.response.send_message(embed=small_embed("❌ Not found"), ephemeral=True)

@bot.command(name="list-role-rewards")
async def list_role_rewards(ctx):
    gid = str(ctx.guild.id)
    rr = role_rewards.get(gid, {})
    if not rr:
        return await ctx.reply(embed=fn_embed("🏆 Role Rewards", "None set yet!"))
    embed = fn_embed("🏆 Role Rewards")
    for lvl, rid in sorted(rr.items(), key=lambda x: int(x[0])):
        role = ctx.guild.get_role(rid)
        if role:
            embed.add_field(name=f"Level {lvl}", value=role.mention, inline=False)
    await ctx.reply(embed=embed)

@bot.tree.command(name="list-role-rewards", description="List all role rewards")
async def slash_list_role_rewards(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    rr = role_rewards.get(gid, {})
    if not rr:
        return await interaction.response.send_message(embed=fn_embed("🏆 Role Rewards", "None set!"))
    embed = fn_embed("🏆 Role Rewards")
    for lvl, rid in sorted(rr.items(), key=lambda x: int(x[0])):
        role = interaction.guild.get_role(rid)
        if role:
            embed.add_field(name=f"Level {lvl}", value=role.mention, inline=False)
    await interaction.response.send_message(embed=embed)

# ================= DM ALL (PREMIUM) =================
@bot.command(name="dmall")
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message: str):
    """DM all members across all servers the bot is in. (Premium)"""
    if not is_premium(ctx.guild.id, ctx.author.id) and not is_owner(ctx.author.id):
        return await premium_required_msg(ctx)
    # Collect unique non-bot members across all guilds
    seen_ids = set()
    targets = []
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot and member.id not in seen_ids:
                seen_ids.add(member.id)
                targets.append(member)

    if not targets:
        return await ctx.reply(embed=small_embed("❌ No members found to DM"))

    total = len(targets)
    success = 0
    failed = 0

    embed = fn_embed("📨 DM All — Sending...", f"**Message:**\n{message[:200]}")
    embed.add_field(name="📊 Progress", value=f"`0/{total}` (0%)", inline=True)
    embed.add_field(name="✅ Sent", value="`0`", inline=True)
    embed.add_field(name="❌ Failed", value="`0`", inline=True)
    embed.set_footer(text=f"Started by {ctx.author}")
    embed.timestamp = datetime.now()
    progress_msg = await ctx.reply(embed=embed)

    dm_embed = discord.Embed(
        title="📩 Message from Server Staff",
        description=message,
        color=FN_COLOR,
        timestamp=datetime.now()
    )
    dm_embed.set_footer(text=f"Sent via {ctx.guild.name}")
    if ctx.guild.icon:
        dm_embed.set_thumbnail(url=ctx.guild.icon.url)

    for i, member in enumerate(targets, 1):
        try:
            await member.send(embed=dm_embed)
            success += 1
        except Exception:
            failed += 1

        # Update progress every 10 members or on the last one
        if i % 10 == 0 or i == total:
            pct = int((i / total) * 100)
            embed.set_field_at(0, name="📊 Progress", value=f"`{i}/{total}` ({pct}%)", inline=True)
            embed.set_field_at(1, name="✅ Sent", value=f"`{success}`", inline=True)
            embed.set_field_at(2, name="❌ Failed", value=f"`{failed}`", inline=True)
            try:
                await progress_msg.edit(embed=embed)
            except Exception:
                pass

        await asyncio.sleep(0.1)  # Rate limit protection

    # Final result
    final_embed = fn_embed("📨 DM All — Complete!", f"**Message:**\n{message[:200]}")
    final_embed.add_field(name="✅ Sent", value=f"`{success}`", inline=True)
    final_embed.add_field(name="❌ Failed", value=f"`{failed}`", inline=True)
    final_embed.add_field(name="👥 Total", value=f"`{total}`", inline=True)
    final_embed.set_footer(text=f"Completed by {ctx.author}")
    final_embed.timestamp = datetime.now()
    try:
        await progress_msg.edit(embed=final_embed)
    except Exception:
        await ctx.send(embed=final_embed)

@bot.tree.command(name="dmall", description="DM all members across all servers (Premium)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message="The message to send to all members")
async def slash_dmall(interaction: discord.Interaction, message: str):
    """DM all members across all servers the bot is in. (Premium)"""
    if not is_premium(interaction.guild.id, interaction.user.id) and not is_owner(interaction.user.id):
        return await premium_required_msg(interaction)
    await interaction.response.defer()

    seen_ids = set()
    targets = []
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot and member.id not in seen_ids:
                seen_ids.add(member.id)
                targets.append(member)

    if not targets:
        return await interaction.followup.send(embed=small_embed("❌ No members found to DM"))

    total = len(targets)
    success = 0
    failed = 0

    embed = fn_embed("📨 DM All — Sending...", f"**Message:**\n{message[:200]}")
    embed.add_field(name="📊 Progress", value=f"`0/{total}` (0%)", inline=True)
    embed.add_field(name="✅ Sent", value="`0`", inline=True)
    embed.add_field(name="❌ Failed", value="`0`", inline=True)
    embed.set_footer(text=f"Started by {interaction.user}")
    embed.timestamp = datetime.now()
    progress_msg = await interaction.followup.send(embed=embed, wait=True)

    dm_embed = discord.Embed(
        title="📩 Message from Server Staff",
        description=message,
        color=FN_COLOR,
        timestamp=datetime.now()
    )
    dm_embed.set_footer(text=f"Sent via {interaction.guild.name}")
    if interaction.guild.icon:
        dm_embed.set_thumbnail(url=interaction.guild.icon.url)

    for i, member in enumerate(targets, 1):
        try:
            await member.send(embed=dm_embed)
            success += 1
        except Exception:
            failed += 1

        if i % 10 == 0 or i == total:
            pct = int((i / total) * 100)
            embed.set_field_at(0, name="📊 Progress", value=f"`{i}/{total}` ({pct}%)", inline=True)
            embed.set_field_at(1, name="✅ Sent", value=f"`{success}`", inline=True)
            embed.set_field_at(2, name="❌ Failed", value=f"`{failed}`", inline=True)
            try:
                await progress_msg.edit(embed=embed)
            except Exception:
                pass

        await asyncio.sleep(0.5)

    final_embed = fn_embed("📨 DM All — Complete!", f"**Message:**\n{message[:200]}")
    final_embed.add_field(name="✅ Sent", value=f"`{success}`", inline=True)
    final_embed.add_field(name="❌ Failed", value=f"`{failed}`", inline=True)
    final_embed.add_field(name="👥 Total", value=f"`{total}`", inline=True)
    final_embed.set_footer(text=f"Completed by {interaction.user}")
    final_embed.timestamp = datetime.now()
    try:
        await progress_msg.edit(embed=final_embed)
    except Exception:
        await interaction.followup.send(embed=final_embed)

# ================= PREMIUM SYSTEM =================
@bot.command(name="premium")
async def premium_cmd(ctx, *, password: str = None):
    """Activate premium with password. Message auto-deletes for security."""
    # Auto-delete the user's message (hide password)
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not password:
        embed = discord.Embed(
            title="⭐ Premium Activation",
            description="**Usage:** `>premium <password>`\n\n"
                        "🔑 Enter your premium password to unlock premium commands.\n"
                        "📞 Contact the bot owner to get a premium password.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Premium by NexafyreZ")
        return await ctx.send(embed=embed, delete_after=15)

    if password.strip() != PREMIUM_PASSWORD:
        embed = discord.Embed(
            title="❌ Wrong Password",
            description="The premium password is incorrect!\n"
                        "📞 Contact the bot owner for the correct password.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Premium by NexafyreZ")
        return await ctx.send(embed=embed, delete_after=10)

    # Activate premium
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    premium_data.setdefault(gid, [])
    if uid not in premium_data[gid]:
        premium_data[gid].append(uid)
        save_premium()

    embed = discord.Embed(
        title="⭐ Premium Activated!",
        description=f"🎉 {ctx.author.mention} is now a **Premium** member!\n\n"
                    "You can now use all premium commands.\n"
                    "Use `>help` → **Premium Commands** to see them.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await ctx.send(embed=embed)

    # DM the user
    try:
        dm_embed = discord.Embed(
            title="⭐ Premium Activated!",
            description=f"🎉 Congratulations! Your **Premium** has been activated in **{ctx.guild.name}**!\n\n"
                        "✅ You now have access to all premium commands.\n"
                        "Use `>help` → **Premium Commands** to see what you unlocked.",
            color=discord.Color.gold()
        )
        dm_embed.set_footer(text="Premium by NexafyreZ")
        if ctx.guild.icon:
            dm_embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.author.send(embed=dm_embed)
    except Exception:
        pass


@bot.tree.command(name="premium", description="Activate premium with password")
@app_commands.describe(password="Your premium password")
async def slash_premium(interaction: discord.Interaction, password: str):
    """Activate premium with password (slash version)."""
    if password.strip() != PREMIUM_PASSWORD:
        embed = discord.Embed(
            title="❌ Wrong Password",
            description="The premium password is incorrect!\n"
                        "📞 Contact the bot owner for the correct password.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Premium by NexafyreZ")
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    premium_data.setdefault(gid, [])
    if uid not in premium_data[gid]:
        premium_data[gid].append(uid)
        save_premium()

    embed = discord.Embed(
        title="⭐ Premium Activated!",
        description=f"🎉 {interaction.user.mention} is now a **Premium** member!\n\n"
                    "You can now use all premium commands.\n"
                    "Use `/help` → **Premium Commands** to see them.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # DM the user
    try:
        dm_embed = discord.Embed(
            title="⭐ Premium Activated!",
            description=f"🎉 Congratulations! Your **Premium** has been activated in **{interaction.guild.name}**!\n\n"
                        "✅ You now have access to all premium commands.\n"
                        "Use `/help` → **Premium Commands** to see what you unlocked.",
            color=discord.Color.gold()
        )
        dm_embed.set_footer(text="Premium by NexafyreZ")
        if interaction.guild.icon:
            dm_embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.user.send(embed=dm_embed)
    except Exception:
        pass


# --- Remove Premium (Owner Only) ---
@bot.command(name="removepremium")
async def removepremium_cmd(ctx, member: discord.Member):
    """Remove premium from a user. Owner only."""
    if not is_owner(ctx.author.id):
        return await ctx.send(embed=small_embed("❌ Only the bot owner can use this command!"), delete_after=5)

    gid = str(ctx.guild.id)
    uid = str(member.id)
    if gid in premium_data and uid in premium_data[gid]:
        premium_data[gid].remove(uid)
        save_premium()
        await ctx.send(embed=small_embed(f"✅ Removed premium from {member.mention}"))
        # DM the user about removal
        try:
            dm_embed = discord.Embed(
                title="❌ Premium Removed",
                description=f"Your **Premium** has been removed in **{ctx.guild.name}**.\n\n"
                            "You no longer have access to premium commands.\n"
                            "Contact the bot owner if you think this is a mistake.",
                color=discord.Color.red()
            )
            dm_embed.set_footer(text="Premium by NexafyreZ")
            if ctx.guild.icon:
                dm_embed.set_thumbnail(url=ctx.guild.icon.url)
            await member.send(embed=dm_embed)
        except Exception:
            pass
    else:
        await ctx.send(embed=small_embed(f"❌ {member.mention} doesn't have premium in this server"))


@bot.tree.command(name="removepremium", description="Remove premium from a user (Owner only)")
@app_commands.describe(member="The member to remove premium from")
async def slash_removepremium(interaction: discord.Interaction, member: discord.Member):
    """Remove premium from a user. Owner only."""
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message(
            embed=small_embed("❌ Only the bot owner can use this command!"), ephemeral=True
        )

    gid = str(interaction.guild.id)
    uid = str(member.id)
    if gid in premium_data and uid in premium_data[gid]:
        premium_data[gid].remove(uid)
        save_premium()
        await interaction.response.send_message(embed=small_embed(f"✅ Removed premium from {member.mention}"))
        # DM the user about removal
        try:
            dm_embed = discord.Embed(
                title="❌ Premium Removed",
                description=f"Your **Premium** has been removed in **{interaction.guild.name}**.\n\n"
                            "You no longer have access to premium commands.\n"
                            "Contact the bot owner if you think this is a mistake.",
                color=discord.Color.red()
            )
            dm_embed.set_footer(text="Premium by NexafyreZ")
            if interaction.guild.icon:
                dm_embed.set_thumbnail(url=interaction.guild.icon.url)
            await member.send(embed=dm_embed)
        except Exception:
            pass
    else:
        await interaction.response.send_message(
            embed=small_embed(f"❌ {member.mention} doesn't have premium"), ephemeral=True
        )


# --- Set Premium Password (Owner Only) ---
@bot.command(name="setpremiumpass")
async def setpremiumpass_cmd(ctx, *, new_password: str):
    """Change the premium password. Owner only."""
    # Auto-delete for security
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not is_owner(ctx.author.id):
        return await ctx.send(embed=small_embed("❌ Only the bot owner can use this command!"), delete_after=5)

    global PREMIUM_PASSWORD
    PREMIUM_PASSWORD = new_password.strip()
    config["premium_password"] = PREMIUM_PASSWORD
    save_config()

    embed = discord.Embed(
        title="🔑 Premium Password Updated!",
        description=f"New password has been set successfully.\n"
                    f"**New Password:** ||{PREMIUM_PASSWORD}||",
        color=discord.Color.gold()
    )
    embed.set_footer(text="This message will auto-delete in 15 seconds")
    await ctx.send(embed=embed, delete_after=15)


@bot.tree.command(name="setpremiumpass", description="Change premium password (Owner only)")
@app_commands.describe(new_password="The new premium password")
async def slash_setpremiumpass(interaction: discord.Interaction, new_password: str):
    """Change the premium password. Owner only."""
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message(
            embed=small_embed("❌ Only the bot owner can use this command!"), ephemeral=True
        )

    global PREMIUM_PASSWORD
    PREMIUM_PASSWORD = new_password.strip()
    config["premium_password"] = PREMIUM_PASSWORD
    save_config()

    embed = discord.Embed(
        title="🔑 Premium Password Updated!",
        description=f"New password: ||{PREMIUM_PASSWORD}||",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Give Premium (Owner Only) ---
@bot.command(name="givepremium")
async def givepremium_cmd(ctx, member: discord.Member):
    """Give premium to a user. Owner only."""
    if not is_owner(ctx.author.id):
        return await ctx.send(embed=small_embed("❌ Only the bot owner can use this command!"), delete_after=5)

    gid = str(ctx.guild.id)
    uid = str(member.id)
    premium_data.setdefault(gid, [])
    if uid in premium_data[gid]:
        return await ctx.send(embed=small_embed(f"⚠️ {member.mention} already has premium in this server"))

    premium_data[gid].append(uid)
    save_premium()
    await ctx.send(embed=small_embed(f"⭐ Premium given to {member.mention}!"))

    # DM the user
    try:
        dm_embed = discord.Embed(
            title="⭐ Premium Activated!",
            description=f"🎉 Congratulations! You have been given **Premium** in **{ctx.guild.name}**!\n\n"
                        "✅ You now have access to all premium commands.\n"
                        "Use `>help` → **Premium Commands** to see what you unlocked.",
            color=discord.Color.gold()
        )
        dm_embed.set_footer(text="Premium by NexafyreZ")
        if ctx.guild.icon:
            dm_embed.set_thumbnail(url=ctx.guild.icon.url)
        await member.send(embed=dm_embed)
    except Exception:
        pass


@bot.tree.command(name="givepremium", description="Give premium to a user (Owner only)")
@app_commands.describe(member="The member to give premium to")
async def slash_givepremium(interaction: discord.Interaction, member: discord.Member):
    """Give premium to a user. Owner only."""
    if not is_owner(interaction.user.id):
        return await interaction.response.send_message(
            embed=small_embed("❌ Only the bot owner can use this command!"), ephemeral=True
        )

    gid = str(interaction.guild.id)
    uid = str(member.id)
    premium_data.setdefault(gid, [])
    if uid in premium_data[gid]:
        return await interaction.response.send_message(
            embed=small_embed(f"⚠️ {member.mention} already has premium"), ephemeral=True
        )

    premium_data[gid].append(uid)
    save_premium()
    await interaction.response.send_message(embed=small_embed(f"⭐ Premium given to {member.mention}!"))

    # DM the user
    try:
        dm_embed = discord.Embed(
            title="⭐ Premium Activated!",
            description=f"🎉 Congratulations! You have been given **Premium** in **{interaction.guild.name}**!\n\n"
                        "✅ You now have access to all premium commands.\n"
                        "Use `/help` → **Premium Commands** to see what you unlocked.",
            color=discord.Color.gold()
        )
        dm_embed.set_footer(text="Premium by NexafyreZ")
        if interaction.guild.icon:
            dm_embed.set_thumbnail(url=interaction.guild.icon.url)
        await member.send(embed=dm_embed)
    except Exception:
        pass


# ================= PROFILE CHANGE (PREMIUM) =================
import aiohttp

@bot.command(name="profilechange")
async def profilechange_cmd(ctx, pfp_url: str = None):
    """Change bot profile picture in this server only. Premium only."""
    if not is_premium(ctx.guild.id, ctx.author.id) and not is_owner(ctx.author.id):
        return await premium_required_msg(ctx)

    if not pfp_url:
        embed = discord.Embed(
            title="🖼️ Profile Change (Server Only)",
            description="**Usage:**\n"
                        "`>profilechange <pfp_link>`\n\n"
                        "⚠️ This will only change the bot's PFP in **this server**.\n"
                        "Other servers will not be affected.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Premium by NexafyreZ")
        return await ctx.send(embed=embed, delete_after=15)

    msg = await ctx.send(embed=small_embed("⚙️ Changing bot profile for this server..."))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(pfp_url) as resp:
                if resp.status == 200:
                    pfp_data = await resp.read()
                    me = ctx.guild.me
                    await me.edit(avatar=pfp_data)
                    result_text = f"✅ Bot profile picture updated for **{ctx.guild.name}** only!"
                else:
                    result_text = f"❌ PFP download failed (HTTP {resp.status})"
    except Exception as e:
        result_text = f"❌ PFP error: {e}"

    embed = discord.Embed(
        title="🖼️ Profile Change (Server Only)",
        description=result_text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await msg.edit(embed=embed)


@bot.tree.command(name="profilechange", description="Change bot PFP in this server only (Premium)")
@app_commands.describe(pfp_url="Image URL for new profile picture")
async def slash_profilechange(interaction: discord.Interaction, pfp_url: str = None):
    """Change bot profile picture in this server only. Premium only."""
    if not is_premium(interaction.guild.id, interaction.user.id) and not is_owner(interaction.user.id):
        return await premium_required_msg(interaction)

    if not pfp_url:
        embed = discord.Embed(
            title="🖼️ Profile Change (Server Only)",
            description="**Usage:**\n"
                        "`/profilechange pfp_url:<link>`\n\n"
                        "⚠️ This will only change the bot's PFP in **this server**.",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Premium by NexafyreZ")
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    await interaction.response.defer()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(pfp_url) as resp:
                if resp.status == 200:
                    pfp_data = await resp.read()
                    me = interaction.guild.me
                    await me.edit(avatar=pfp_data)
                    result_text = f"✅ Bot profile picture updated for **{interaction.guild.name}** only!"
                else:
                    result_text = f"❌ PFP download failed (HTTP {resp.status})"
    except Exception as e:
        result_text = f"❌ PFP error: {e}"

    embed = discord.Embed(
        title="🖼️ Profile Change (Server Only)",
        description=result_text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await interaction.followup.send(embed=embed)


# --- Reset Profile (Premium) ---
@bot.command(name="resetprofile")
async def resetprofile_cmd(ctx):
    """Reset bot profile picture in this server to default. Premium only."""
    if not is_premium(ctx.guild.id, ctx.author.id) and not is_owner(ctx.author.id):
        return await premium_required_msg(ctx)

    msg = await ctx.send(embed=small_embed("⚙️ Resetting bot profile for this server..."))

    try:
        me = ctx.guild.me
        await me.edit(avatar=None)
        result_text = f"✅ Bot profile picture reset to default for **{ctx.guild.name}**!"
    except Exception as e:
        result_text = f"❌ PFP reset error: {e}"

    embed = discord.Embed(
        title="🖼️ Profile Reset (Server Only)",
        description=result_text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await msg.edit(embed=embed)


@bot.tree.command(name="resetprofile", description="Reset bot PFP in this server to default (Premium)")
async def slash_resetprofile(interaction: discord.Interaction):
    """Reset bot profile picture in this server to default. Premium only."""
    if not is_premium(interaction.guild.id, interaction.user.id) and not is_owner(interaction.user.id):
        return await premium_required_msg(interaction)

    await interaction.response.defer()

    try:
        me = interaction.guild.me
        await me.edit(avatar=None)
        result_text = f"✅ Bot profile picture reset to default for **{interaction.guild.name}**!"
    except Exception as e:
        result_text = f"❌ PFP reset error: {e}"

    embed = discord.Embed(
        title="🖼️ Profile Reset (Server Only)",
        description=result_text,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Premium by NexafyreZ")
    await interaction.followup.send(embed=embed)


# ================= SET PREFIX =================
@bot.command(name="setprefix")
@commands.has_permissions(administrator=True)
async def setprefix_cmd(ctx, new_prefix: str = None):
    """Change the bot prefix for this server. Admin only."""
    if not new_prefix:
        gid = str(ctx.guild.id)
        current = config.get("guild_prefixes", {}).get(gid, PREFIX)
        embed = discord.Embed(
            title="⚙️ Bot Prefix",
            description=f"Current prefix: `{current}`\n\n"
                        f"**Usage:** `{current}setprefix <new_prefix>`\n"
                        f"**Example:** `{current}setprefix !`",
            color=FN_COLOR
        )
        embed.set_footer(text="Made by obito | NexafyreZ")
        return await ctx.send(embed=embed, delete_after=15)

    if len(new_prefix) > 5:
        return await ctx.send(embed=small_embed("❌ Prefix must be 5 characters or less!"), delete_after=5)

    gid = str(ctx.guild.id)
    if "guild_prefixes" not in config:
        config["guild_prefixes"] = {}
    config["guild_prefixes"][gid] = new_prefix
    save_config()

    embed = discord.Embed(
        title="✅ Prefix Updated!",
        description=f"New prefix for this server: `{new_prefix}`\n\n"
                    f"**Example:** `{new_prefix}help`",
        color=FN_COLOR
    )
    embed.set_footer(text="Made by obito | NexafyreZ")
    await ctx.send(embed=embed)


@bot.tree.command(name="setprefix", description="Change bot prefix for this server (Admin)")
@app_commands.describe(new_prefix="The new prefix for this server (max 5 characters)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setprefix(interaction: discord.Interaction, new_prefix: str):
    """Change the bot prefix for this server. Admin only."""
    if len(new_prefix) > 5:
        return await interaction.response.send_message(
            embed=small_embed("❌ Prefix must be 5 characters or less!"), ephemeral=True
        )

    gid = str(interaction.guild.id)
    if "guild_prefixes" not in config:
        config["guild_prefixes"] = {}
    config["guild_prefixes"][gid] = new_prefix
    save_config()

    embed = discord.Embed(
        title="✅ Prefix Updated!",
        description=f"New prefix for this server: `{new_prefix}`\n\n"
                    f"**Example:** `{new_prefix}help`",
        color=FN_COLOR
    )
    embed.set_footer(text="Made by obito | NexafyreZ")
    await interaction.response.send_message(embed=embed)


# ---------- RUN BOT ----------
bot.run(TOKEN)
