#CGTC BOT
import discord
import json
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View
from typing import Optional
from datetime import datetime, timezone


# ── Server & Role IDs ─────────────────────────────────────────────────────────
Server_id = discord.Object(id=1521991917729222657)

Commentator_role = None
Referee_role     = None
Caster_role      = None
team_player_role = 1524100467746144306

# ── Channel IDs ───────────────────────────────────────────────────────────────
Transaction_channel  = 1522110757297459330
Audit_log_channel    = None
Scrims_channel       = None
Scrim_score_channel  = None
Officials_channel    = None

# run on railway
Data_Railway = os.getenv("Data_Railway", "/data")
os.makedirs(Data_Railway, exist_ok=True)
Team_file           = os.path.join(Data_Railway, "teams.json")
Scrim_file          = os.path.join(Data_Railway, "scrims.json")
Scrim_message_file  = os.path.join(Data_Railway, "scrim_messages.json")
Invite_file         = os.path.join(Data_Railway, "invites.json")
Seeding_file        = os.path.join(Data_Railway, "seeding.json")
Scrim_channel_file  = os.path.join(Data_Railway, "scrim_channels.json")
Player_history_file = os.path.join(Data_Railway, "player_history.json")

# ── Premium ───────────────────────────────────────────────────────────────────
Paid_for_premium = {}
Premium_enabled  = Server_id.id in Paid_for_premium
print("Premium features enabled." if Premium_enabled else "Premium features are not enabled.")

# ── Locks ─────────────────────────────────────────────────────────────────────
teams_lock   = asyncio.Lock()
seeding_lock = asyncio.Lock()
scrims_lock  = asyncio.Lock()

# ── JSON helpers ──────────────────────────────────────────────────────────────

def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        content = f.read().strip()
        return json.loads(content) if content else default

def save_json_file(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_teams() -> dict:
    data = load_json_file(Team_file, {})
    return {k.lower(): v for k, v in data.items()}

def save_teams():               save_json_file(Team_file, teams)
def load_seeding() -> dict:     return load_json_file(Seeding_file, {})
def save_seeding(data: dict):   save_json_file(Seeding_file, data)

def load_scrims() -> list:
    data = load_json_file(Scrim_file, [])
    return data if isinstance(data, list) else []

def save_scrims():              save_json_file(Scrim_file, scrims_schedule)
def load_scrim_messages() -> dict: return load_json_file(Scrim_message_file, {})
def save_scrim_messages():      save_json_file(Scrim_message_file, scrim_message_ids)

def load_scrim_channels() -> dict:
    data = load_json_file(Scrim_channel_file, {})
    return {int(k): v for k, v in data.items()}

def save_scrim_channels():
    save_json_file(Scrim_channel_file, {str(k): v for k, v in scrim_channels.items()})

def save_invites():
    save_json_file(Invite_file, {str(k): v for k, v in pending_invites.items()})

def load_invites() -> dict:
    data = load_json_file(Invite_file, {})
    return {int(k): v for k, v in data.items()}

def load_player_history() -> dict: return load_json_file(Player_history_file, {})
def save_player_history():         save_json_file(Player_history_file, player_history)

# ── In-memory state ───────────────────────────────────────────────────────────
teams:             dict = load_teams()
seeding:           dict = load_seeding()
scrims_schedule:   list = load_scrims()
scrim_message_ids: dict = load_scrim_messages()
scrim_messages:    dict = {}
scrim_channels:    dict = load_scrim_channels()
pending_invites:   dict = load_invites()
player_history:    dict = load_player_history()

# ── Bot class ─────────────────────────────────────────────────────────────────

class ProGorillaComp(commands.Bot):
    async def on_ready(self):
        print(f'{self.user} is now online')
        try:
            synced = await self.tree.sync(guild=Server_id)
            print(f'{len(synced)} commands synced to {Server_id.id}.')
        except Exception as e:
            print(f'Sync error: {e}')

intents                 = discord.Intents.default()
intents.members         = True
intents.message_content = True
progorillacomp          = ProGorillaComp(command_prefix="!", intents=intents)

# ── Helper: resolve team_player_role int to Role object ──────────────────────

def get_tpr(guild: discord.Guild) -> discord.Role | None:
    return guild.get_role(team_player_role)

# ── Premium check ─────────────────────────────────────────────────────────────

def is_premium():
    async def paid_premium(interaction: discord.Interaction):
        if interaction.guild and interaction.guild.id in Paid_for_premium:
            return True
        await interaction.response.send_message(
            "This server has not paid for premium. Contact @had3s.PGC.", ephemeral=True)
        return False
    return app_commands.check(paid_premium)

# ── Audit log ─────────────────────────────────────────────────────────────────

async def log_command(interaction: discord.Interaction) -> bool:
    if interaction.command is None:                                       return True
    if interaction.type == discord.InteractionType.autocomplete:          return True
    if not interaction.guild or interaction.guild.id not in Paid_for_premium: return True
    channel = interaction.guild.get_channel(Audit_log_channel)
    if channel:
        options = interaction.data.get("options", [])
        parts   = []
        for opt in options:
            val = f"<@{opt['value']}>" if opt["name"] == "player" else opt["value"]
            parts.append(f"{opt['name']}: `{val}`")
        embed = discord.Embed(
            description=f"**/{interaction.command.name}**" + (f"\n{' '.join(parts)}" if parts else ""),
            color=0xB3B3FC)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await channel.send(embed=embed)
    return True

progorillacomp.tree.interaction_check = log_command

# ── Autocomplete ──────────────────────────────────────────────────────────────

async def category_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=c.name, value=c.name)
            for c in interaction.guild.categories if current.lower() in c.name.lower()][:25]

async def team_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=n.title(), value=n)
            for n in teams if current.lower() in n.lower()][:25]

async def seeding_team_autocomplete(interaction: discord.Interaction, current: str):
    try:
        order  = seeding.get("order", [])
        points = seeding.get("points", {})
        return [app_commands.Choice(name=f"{n.title()}: {points.get(n, 0)} pts", value=n)
                for n in order if current.lower() in n.lower()][:25]
    except Exception:
        return []

async def scrim_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(
                name=f"{s['team1']} vs {s['team2']} — {s['date']} at {s['time']}",
                value=f"{s['team1'].lower()}|{s['team2'].lower()}|{s['time']}|{s['date']}")
            for s in scrims_schedule
            if current.lower() in f"{s['team1']} {s['team2']}".lower()][:25]

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_player_team(player_id: int) -> str | None:
    for name, team in teams.items():
        if player_id in team["players"]:
            return name
    return None

def make_scrim_key(team1: str, team2: str) -> str:
    # FIX: use separator unlikely to appear in team names to avoid key collisions
    return f"{team1.lower()}:vs:{team2.lower()}"

async def log_transaction(interaction: discord.Interaction, message: str):
    ch = interaction.guild.get_channel(Transaction_channel)
    if ch:
        await ch.send(message)

async def get_scrim_message(guild: discord.Guild, key: str):
    if key in scrim_messages:
        return scrim_messages[key]
    data = scrim_message_ids.get(key)
    if not data:
        return None
    try:
        ch = guild.get_channel(data["channel_id"])
        if ch is None:
            return None
        msg = await ch.fetch_message(data["message_id"])
        scrim_messages[key] = msg
        return msg
    except (discord.NotFound, discord.Forbidden):
        return None

async def get_mirror_message(guild: discord.Guild, key: str):
    data = scrim_message_ids.get(key)
    if not data or not data.get("mirror_message_id"):
        return None
    try:
        ch = guild.get_channel(Scrims_channel)
        if ch is None:
            return None
        return await ch.fetch_message(data["mirror_message_id"])
    except (discord.NotFound, discord.Forbidden):
        return None

async def get_seeding_message(guild: discord.Guild):
    channel_id = seeding.get("channel_id")
    message_id = seeding.get("message_id")
    if not channel_id or not message_id:
        return None
    try:
        ch = guild.get_channel(channel_id)
        return await ch.fetch_message(message_id) if ch else None
    except (discord.NotFound, discord.Forbidden):
        return None

def build_seeding_embed(order, footer, points, ended=False, qualifiers=None):
    if not ended:
        desc = "# CGTC Season's Seeding 🎯\n**Current seedings based on team scores.**"
    else:
        desc = f"# CGTC Seeding Results 🏆\n**Top {qualifiers} teams have moved on! Congratulations!**"
    lines = []
    for rank, name in enumerate(order, 1):
        d   = teams.get(name, {})
        pts = points.get(name, 0)
        pfx = ("✅" if rank <= qualifiers else "❌") if (ended and qualifiers) else ""
        lines.append(f"## {pfx} **{rank}. {name.title()}**\n"
                     f"> **{d.get('wins',0)}W | {d.get('losses',0)}L | {d.get('draws',0)}D | {pts}pts**")
    embed = discord.Embed(
        description=desc + "\n\n" + "\n\n".join(lines),
        color=0xB3B3FC if not ended else discord.Color.gold())
    embed.set_footer(text=footer)
    return embed

async def apply_seeding_result(interaction, winner, loser, label):
    if not (seeding and seeding.get("order") and not seeding.get("locked")):
        return
    win_pts  = seeding.get("win_points", 0)
    loss_pts = seeding.get("loss_points", 0)
    points   = seeding.get("points", {})
    updated  = False
    if winner in points:
        points[winner] = points.get(winner, 0) + win_pts
        updated = True
    if loser in points:
        points[loser] = points.get(loser, 0) + loss_pts
        updated = True
    if updated:
        order            = sorted(points, key=lambda k: points[k], reverse=True)
        seeding["order"] = order
        seeding["points"] = points
        save_seeding(seeding)
        msg = await get_seeding_message(interaction.guild)
        if msg:
            await msg.edit(embed=build_seeding_embed(order, footer=label, points=points))

def record_team_join(player_id, team_name):
    h = str(player_id)
    player_history.setdefault(h, []).append(
        {"team": team_name, "action": "joined", "timestamp": discord.utils.utcnow().isoformat()})
    save_player_history()

def record_team_leave(player_id, team_name):
    h = str(player_id)
    player_history.setdefault(h, []).append(
        {"team": team_name, "action": "left", "timestamp": discord.utils.utcnow().isoformat()})
    save_player_history()

def role_pings(guild: discord.Guild) -> str:
    roles = [guild.get_role(r) for r in (Commentator_role, Caster_role, Referee_role)]
    return " ".join(r.mention for r in roles if r)

# ── ScrimThingy ───────────────────────────────────────────────────────────────

class ScrimThingy(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def has_role(self, interaction: discord.Interaction, *role_ids: int) -> bool:
        if not any(r.id in role_ids for r in interaction.user.roles):
            await interaction.response.send_message(
                "You don't have the required role for this.", ephemeral=True)
            return False
        return True

    def lock_if_full(self, description: str):
        all_filled = (
            "**Commentator:** None"     not in description and
            "**2nd Commentator:** None" not in description and
            "**Referee:** None"         not in description and
            "**Caster:** None"          not in description)
        if all_filled:
            for item in self.children:
                if hasattr(item, "custom_id") and item.custom_id != "scrim:leave":
                    item.disabled = True

    async def sync_mirror(self, interaction: discord.Interaction, embed: discord.Embed):
        key = next(
            (k for k, v in scrim_message_ids.items()
             if v.get("channel_id") == interaction.channel.id
             and v.get("message_id") == interaction.message.id), None)
        if key is None:
            return
        mirror = await get_mirror_message(interaction.guild, key)
        if not mirror:
            return
        try:
            lines = embed.description.splitlines()
            teams_line = lines[0].replace("# ", "")
            team1, team2 = [t.strip() for t in teams_line.split(" vs ")]
            time_date = lines[1].strip().split(" ", 1)
            time = time_date[0]
            date = time_date[1] if len(time_date) > 1 else ""
            mirror_embed = build_scrim_embed(time, date, team1, team2)
            for line in lines[2:]:
                for role_key in ("**Commentator:**", "**2nd Commentator:**", "**Referee:**", "**Caster:**"):
                    if line.startswith(role_key):
                        mirror_embed.description = mirror_embed.description.replace(
                            f"{role_key} None", line.strip())
            await mirror.edit(embed=mirror_embed)
        except Exception:
            pass

    @discord.ui.button(label="Claim Commentator",     style=discord.ButtonStyle.gray, emoji="🎙️", custom_id="scrim:commentator")
    async def com(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_role(interaction, Commentator_role): return
        embed = interaction.message.embeds[0]
        if interaction.user.mention in embed.description:
            await interaction.response.send_message("You already claimed a role.", ephemeral=True); return
        if "**Commentator:** None" not in embed.description:
            await interaction.response.send_message("Commentator already taken.", ephemeral=True); return
        embed.description = embed.description.replace("**Commentator:** None", f"**Commentator:** {interaction.user.mention}")
        button.disabled   = True
        self.lock_if_full(embed.description)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

    @discord.ui.button(label="Claim 2nd Commentator", style=discord.ButtonStyle.gray, emoji="🎤", custom_id="scrim:commentator2")
    async def com2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_role(interaction, Commentator_role): return
        embed = interaction.message.embeds[0]
        if interaction.user.mention in embed.description:
            await interaction.response.send_message("You already claimed a role.", ephemeral=True); return
        if "**2nd Commentator:** None" not in embed.description:
            await interaction.response.send_message("2nd Commentator already taken.", ephemeral=True); return
        embed.description = embed.description.replace("**2nd Commentator:** None", f"**2nd Commentator:** {interaction.user.mention}")
        button.disabled   = True
        self.lock_if_full(embed.description)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

    @discord.ui.button(label="Claim Referee",         style=discord.ButtonStyle.gray, emoji="⁉️", custom_id="scrim:referee")
    async def ref(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_role(interaction, Referee_role): return
        embed = interaction.message.embeds[0]
        if interaction.user.mention in embed.description:
            await interaction.response.send_message("You already claimed a role.", ephemeral=True); return
        if "**Referee:** None" not in embed.description:
            await interaction.response.send_message("Referee already taken.", ephemeral=True); return
        embed.description = embed.description.replace("**Referee:** None", f"**Referee:** {interaction.user.mention}")
        button.disabled   = True
        self.lock_if_full(embed.description)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

    @discord.ui.button(label="Claim Caster",          style=discord.ButtonStyle.gray, emoji="📸", custom_id="scrim:caster")
    async def cast(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_role(interaction, Caster_role): return
        embed = interaction.message.embeds[0]
        if interaction.user.mention in embed.description:
            await interaction.response.send_message("You already claimed a role.", ephemeral=True); return
        if "**Caster:** None" not in embed.description:
            await interaction.response.send_message("Caster already taken.", ephemeral=True); return
        embed.description = embed.description.replace("**Caster:** None", f"**Caster:** {interaction.user.mention}")
        button.disabled   = True
        self.lock_if_full(embed.description)
        await interaction.response.edit_message(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

    @discord.ui.button(label="Exit Role", style=discord.ButtonStyle.gray, emoji="🚫", custom_id="scrim:leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_role(interaction, Caster_role, Commentator_role, Referee_role): return
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        if interaction.user.mention not in embed.description:
            await interaction.followup.send("You don't have a role in this scrim.", ephemeral=True); return
        role_labels = {
            "scrim:commentator":  "**Commentator:**",
            "scrim:commentator2": "**2nd Commentator:**",
            "scrim:referee":      "**Referee:**",
            "scrim:caster":       "**Caster:**",
        }
        for item in self.children:
            if hasattr(item, "custom_id") and item.custom_id in role_labels:
                label      = role_labels[item.custom_id]
                full_entry = f"{label} {interaction.user.mention}"
                if full_entry in embed.description:
                    embed.description = embed.description.replace(full_entry, f"{label} None")
                    item.disabled     = False
        await interaction.message.edit(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

    @discord.ui.button(label="Cancel Scrim", style=discord.ButtonStyle.red, emoji="❌", custom_id="scrim:cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permission to cancel scrims.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        embed             = interaction.message.embeds[0]
        embed.colour      = discord.Color.red()
        embed.description = "# Scrim Cancelled\n" + "\n".join(embed.description.split("\n")[1:])
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        await self.sync_mirror(interaction, embed)

        global scrims_schedule
        key = next((k for k, v in scrim_message_ids.items()
                    if v.get("message_id") == interaction.message.id), None)
        if key:
            parts = key.split(":vs:", 1)
            if len(parts) == 2:
                t1, t2 = parts
                scrims_schedule = [g for g in scrims_schedule
                                   if not (g["team1"].lower() == t1 and g["team2"].lower() == t2)]
                save_scrims()
            scrim_messages.pop(key, None)
            scrim_message_ids.pop(key, None)
            save_scrim_messages()

        await interaction.followup.send("Scrim has been cancelled.", ephemeral=True)


# ── Shared helper: post scrim to both channels ────────────────────────────────

def build_scrim_embed(time: str, date: str, team1: str, team2: str) -> discord.Embed:
    return discord.Embed(
        description=(
            "# **----------CGTC OFFICIAL SCRIM----------**\n"
            ">>> ## Scrim Details:\n\n"
            f"**Time:** {time}\n"
            f"**Day:** {date}\n"
            f"**First Team:** {team1}\n"
            f"**Second Team:** {team2}\n\n"
            "**Commentator:** None\n"
            "**2nd Commentator:** None\n"
            "**Referee:** None\n"
            "**Caster:** None"),
        color=0xB3B3FC)

def build_officials_embed(time: str, date: str, team1: str, team2: str) -> discord.Embed:
    return discord.Embed(
        description=(
            f"# {team1} vs {team2}\n"
            f"{time} {date}\n"
            "**Commentator:** None\n"
            "**2nd Commentator:** None\n"
            "**Referee:** None\n"
            "**Caster:** None"),
        color=0xB3B3FC)

async def post_scrim_to_channels(
        guild: discord.Guild,
        key: str,
        time: str,
        date: str,
        team1: str,
        team2: str):

    officials_ch = guild.get_channel(Officials_channel)
    scrims_ch    = guild.get_channel(Scrims_channel)

    if not officials_ch:
        raise ValueError(f"Officials channel {Officials_channel} not found.")
    if not scrims_ch:
        raise ValueError(f"Scrims channel {Scrims_channel} not found.")

    officials_embed = build_officials_embed(time, date, team1, team2)
    mirror_embed    = build_scrim_embed(time, date, team1, team2)

    pings = role_pings(guild)

    officials_msg = await officials_ch.send(pings or None, embed=officials_embed, view=ScrimThingy())
    mirror_msg    = await scrims_ch.send(embed=mirror_embed)

    scrim_messages[key]    = officials_msg
    scrim_message_ids[key] = {
        "channel_id":        officials_ch.id,
        "message_id":        officials_msg.id,
        "mirror_message_id": mirror_msg.id,
    }
    save_scrim_messages()
    return officials_msg, mirror_msg

# ── Views ─────────────────────────────────────────────────────────────────────

class MyInvitesView(discord.ui.View):
    def __init__(self, player: discord.Member, invites: list):
        super().__init__(timeout=60)
        self.player = player
        for inv in invites:
            self.add_item(InviteButton(inv["team_name"], inv["inviter_id"]))


class InviteButton(discord.ui.Button):
    def __init__(self, team_name: str, inviter_id: int):
        super().__init__(label=team_name.title(), style=discord.ButtonStyle.blurple, emoji="📨")
        self.team_name  = team_name
        self.inviter_id = inviter_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.player.id:
            await interaction.response.send_message("These invites are not for you.", ephemeral=True); return
        view = InvitingThing(interaction.user, self.team_name, self.inviter_id, self.view)
        await interaction.response.edit_message(
            content=f"Invite to **{self.team_name.title()}** from <@{self.inviter_id}>. Accept or decline?",
            view=view)


class ScrimProposalView(discord.ui.View):
    def __init__(self, t1_key, t2_key, time, date, proposer_id, other_captain_id):
        super().__init__(timeout=None)
        self.t1_key           = t1_key
        self.t2_key           = t2_key
        self.time             = time
        self.date             = date
        self.proposer_id      = proposer_id
        self.other_captain_id = other_captain_id

    def is_other_captain(self, interaction: discord.Interaction) -> bool:
        uid   = interaction.user.id
        team1 = teams.get(self.t1_key, {})
        team2 = teams.get(self.t2_key, {})
        on1   = self.proposer_id in (team1.get("captain"), team1.get("co_captain"))
        return uid in (team2.get("captain"), team2.get("co_captain")) if on1 \
               else uid in (team1.get("captain"), team1.get("co_captain"))

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_other_captain(interaction):
            await interaction.response.send_message("Only the other captain can respond.", ephemeral=True); return
        for item in self.children:
            item.disabled = True
        await interaction.response.send_message(
            f"✅ Scrim confirmed for **{self.date}** at **{self.time}**!\n"
            f"<@{self.proposer_id}> <@{self.other_captain_id}>")
        await interaction.message.edit(view=self)
        key = make_scrim_key(self.t1_key, self.t2_key)
        await post_scrim_to_channels(
            interaction.guild, key,
            self.time, self.date,
            self.t1_key.title(), self.t2_key.title())
        scrims_schedule.append({
            "time": self.time, "date": self.date,
            "team1": self.t1_key.title(), "team2": self.t2_key.title()})
        save_scrims()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_other_captain(interaction):
            await interaction.response.send_message("Only the other captain can respond.", ephemeral=True); return
        for item in self.children:
            item.disabled = True
        await interaction.response.send_message(
            f"❌ Proposal declined. <@{self.proposer_id}>, suggest a new time with `/suggest_time`.")
        await interaction.message.edit(view=self)


class InvitingThing(discord.ui.View):
    def __init__(self, player, team_name, inviter_id, previous_view):
        super().__init__(timeout=60)
        self.player        = player
        self.team_name     = team_name
        self.inviter_id    = inviter_id
        self.previous_view = previous_view

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.gray, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        lower = self.team_name.lower()
        if lower not in teams:
            await interaction.response.edit_message(content="This team no longer exists.", view=None); return
        team = teams[lower]
        if team.get("locked"):
            await interaction.response.edit_message(content="Roster is locked.", view=None); return
        if self.player.id in team["players"]:
            await interaction.response.edit_message(content="Already on this team.", view=None); return
        existing = get_player_team(self.player.id)
        if existing and existing != lower:
            await interaction.response.edit_message(
                content=f"You're on **{existing.title()}** — leave first.", view=None); return
        if len(team["players"]) >= 12:
            await interaction.response.edit_message(content="Team is full.", view=None); return
        role = interaction.guild.get_role(team["team_role"])
        if role is None:
            await interaction.response.edit_message(content="Team role not found.", view=None); return
        tpr = get_tpr(interaction.guild)
        roles_to_add = [role] + ([tpr] if tpr else [])
        await self.player.add_roles(*roles_to_add)
        team["players"].append(self.player.id)
        record_team_join(self.player.id, lower)
        if self.player.id in pending_invites:
            pending_invites[self.player.id] = [
                i for i in pending_invites[self.player.id] if i["team_name"] != self.team_name]
            save_invites()
        save_teams()
        await log_transaction(interaction, f"{self.player.mention} joined **{self.team_name.title()}**.")
        await interaction.response.edit_message(content=f"You've joined **{self.team_name.title()}**!", view=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.gray, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not for you.", ephemeral=True); return
        if self.player.id in pending_invites:
            pending_invites[self.player.id] = [
                i for i in pending_invites[self.player.id] if i["team_name"] != self.team_name]
            save_invites()
        await interaction.response.edit_message(
            content=f"You declined the invite to **{self.team_name.title()}**.", view=None)


# ── Events ────────────────────────────────────────────────────────────────────

@progorillacomp.event
async def on_member_remove(member: discord.Member):
    team_name = get_player_team(member.id)
    if not team_name:
        return
    team = teams[team_name]
    team["players"].remove(member.id)
    record_team_leave(member.id, team_name)
    if team["captain"]    == member.id: team["captain"]    = None
    if team["co_captain"] == member.id: team["co_captain"] = None
    save_teams()
    # FIX: check if player is on any remaining team before removing tpr
    still_on_team = get_player_team(member.id)
    tpr = member.guild.get_role(team_player_role)
    if tpr and still_on_team is None:
        try:
            await member.remove_roles(tpr)
        except Exception:
            pass
    ch = member.guild.get_channel(Transaction_channel)
    if ch:
        await ch.send(f"{member.mention} (`{member.name}`) left and was removed from **{team_name.title()}**.")


# ── Commands ──────────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="print", description="Print a message", guild=Server_id)
@is_premium()
async def msg(interaction: discord.Interaction, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    await interaction.response.send_message("Sent!", ephemeral=True)
    await interaction.channel.send(message)


@progorillacomp.tree.command(name="dm_user", description="Send a DM to a user.", guild=Server_id)
@is_premium()
@app_commands.describe(user="User to DM", message="Message to send")
async def dm_user(interaction: discord.Interaction, user: discord.Member, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if user.bot:
        await interaction.response.send_message("Can't DM a bot.", ephemeral=True); return
    try:
        await user.send(message)
        await interaction.response.send_message(f"DM sent to {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"Couldn't DM {user.mention}.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Failed: {e}", ephemeral=True)


@progorillacomp.tree.command(name="info", description="Bot command guide", guild=Server_id)
async def info(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True); return
    embed = discord.Embed(description=(
        "# CGTC Command Guide\n"
        "What every command does and who can use it:\n\n"
        ">>> ## 👤 Anyone\n"
        "**/info** — Shows this embed.\n"
        "**/roster** — Shows a team's roster.\n"
        "**/check_invites** — View and respond to your pending team invites.\n"
        "**/leave_team** — Leave your current team.\n"
        "**/command_guide** — Shows a detailed guide for all commands and how to use them.\n"
        "## 👑 Captains & Co-Captains\n"
        "**/kick_player** — Removes a player from your team.\n"
        "**/assign_cocaptain** — Assigns a co-captain to your team.\n"
        "**/transfer_captain** — Transfers captaincy to another player on the team.\n"
        "**/invite_player** — Invites a player to join your team.\n"
        "## 🔧 Administrators\n"
        "**/create_team** — Creates a new team with captain, co-captain, and roles.\n"
        "**/disband_team** — Disbands a team and deletes its roles.\n"
        "**/lock_rosters** — Locks all team rosters preventing changes.\n"
        "**/unlock_rosters** — Unlocks all team rosters allowing changes.\n"
        "**/assign_captain** — Assigns a captain to a team.\n"
        "## 💎 Premium\n"
        "**/print** — Prints a message to the channel.\n"
        "**/dm_user** — Sends a direct message to a user.\n"
        "**/disband_all** — Disbands every team at once.\n"
        "**/list_teams** — Lists all active teams.\n"
        "**/rename_team** — Renames an existing team and updates its roles.\n"
        "**/add_player** — Manually adds a player to a team.\n"
        "**/player_info** — Shows a player's current team, role, record, and team history.\n"
        "**/set_scrim** — Creates an official scrim embed.\n"
        "**/set_time** — Forcibly sets a scrim time in a scrim channel, no approval needed.\n"
        "**/end_scrim** — Records the final score of a scrim and removes team access from the scrim channel.\n"
        "**/check_scrims** — Quick list of all upcoming scrims.\n"
        "**/create_scrim_channel** — Creates a private channel for two teams to coordinate their scrim.\n"
        "**/suggest_time** — Proposes a scrim time for the other captain to accept or decline.\n"
        "**/forfeit_scrim** — Marks any team as forfeiting a scrim.\n"
        "**/autoforfeit_scrim** — Flags or immediately triggers an auto-forfeit for a team.\n"
        "**/create_seeding** — Starts a seeding round and tracks team scores.\n"
        "**/edit_seeding** — Manually adds or removes wins/points from a team in seeding.\n"
        "**/end_seeding** — Ends the seeding round and displays which teams advanced.\n\n"
        "CGTC Season Management System - Created by Had3s"), color=0xB3B3FC)
    await interaction.response.send_message("Info sent", ephemeral=True)
    await interaction.channel.send(embed=embed)


Free_commands = {
    "📋 All Commands": [
        "This is the Staff Guide for my bot (Had3s), each category explains each command and how & when to use them.\n"
        "## Commands:\n"
        "> * **/info**\n"
        "> * **/roster** \n"
        "> * **/check_invites**\n"
        "> * **/leave_team**\n"
        "> * **/kick_player**\n"
        "> * **/assign_cocaptain**\n"
        "> * **/transfer_captain**\n"
        "> * **/invite_player**\n"
        "> * **/create_team** \n"
        "> * **/disband_team**\n"
        "> * **/lock_rosters**\n"
        "> * **/unlock_rosters**\n"
        "> * **/assign_captain**\n"
        "> * **/staff_guide**\n"
        "> * **/print**\n"
        "> * **/dm_user**\n"
        "> * **/disband_all**\n"
        "> * **/list_teams**\n"
        "> * **/rename_team** \n"
        "> * **/add_player**\n"
        "> * **/player_info**\n"
        "> * **/set_scrim**\n"
        "> * **/set_time**\n"
        "> * **/end_scrim** \n"
        "> * **/check_scrims**\n"
        "> * **/create_scrim_channel** \n"
        "> * **/suggest_time** \n"
        "> * **/forfeit_scrim** \n"
        "> * **/autoforfeit_scrim**\n"
        "> * **/create_seeding**\n"
        "> * **/edit_seeding**\n"
        "> * **/end_seeding** \n\n"
        "Click the commands below to see their details"
    ],
    "📖 /info": [
        "### What does it do?:\n"
        "The `/info` command sends a public embed to the channel containing a full list of every available command,"
        " along with a brief description of what each one does and who is allowed to use it.\n"
        "Use it whenever you need a quick reminder of what a command does, or if you're new to the server and want to get an overview of everything the bot has to offer.\n"
        "*Anyone within the server can use this command.*"
    ],
    "📃 /Roster": [
        "### What does it do?:\n"
        "The `/roster` command displays the full roster of any team, showing the Captain, Co-Captain, and all registered players."
        " Simply select a team from the autocomplete and the bot will send an ephemeral embed visible only to you.\n"
        "Use it whenever you need to check who is currently on a team.\n"
        "*Anyone within the server can use this command.*"
    ],
    "🏢 /staff_guide": [
        "### What does it do?:\n"
        "The `/staff_guide` command provides a detailed guide for staff members on how to use every bot command.\n"
        "Use it whenever you need a refresher on how a command works or want to share the guide with new staff members.\n"
        "*Anyone within the server can use this command.*"
    ],
    "👑 Captains & Co-Captains": [
        "### /invite_player\n"
        "The `/invite_player` command allows a captain or co-captain to invite a player to join their team.\n"
        "Use it when you want to add a new player to your team.\n"
        "*Only captains and co-captains can use this command.*\n\n"
        "### /kick_player\n"
        "The `/kick_player` command allows a captain, co-captain, or admin to forcibly remove a player from a team's roster.\n"
        "Use it when you need to remove a player from your team, whether that's due to inactivity or a roster change.\n"
        "*Only captains and co-captains can use this command.*\n\n"
        "### /assign_cocaptain\n"
        "The `/assign_cocaptain` command allows a captain or admin to assign a co-captain to a team, giving them the ability to help manage the roster by inviting and kicking players.\n"
        "Use it when you want to delegate some team management responsibilities to a trusted player.\n"
        "*Only captains can use this command.*\n\n"
        "### /transfer_captain\n"
        "The `/transfer_captain` command allows a captain or admin to transfer the captaincy of a team to another player.\n"
        "Use it when you want to step down as captain or promote a new one.\n"
        "*Only captains can use this command.*\n\n"
        "### /leave_team\n"
        "The `/leave_team` command allows a player to leave their current team.\n"
        "Use it when you want to leave a team voluntarily.\n"
        "*Anyone on a team can use this command.*"
    ],
    "🔧 Administrator": [
        "### /create_team\n"
        "The `/create_team` command allows an administrator to create a new team, assigning a captain, co-captain, and generating the necessary roles.\n"
        "Use it when you want to add a new team to the league.\n"
        "*Only administrators can use this command.*\n\n"
        "### /disband_team\n"
        "The `/disband_team` command allows an administrator to permanently disband a team, removing all associated roles and data.\n"
        "Use it when you want to dissolve a team from the league.\n"
        "*Only administrators can use this command.*\n\n"
        "### /assign_captain\n"
        "The `/assign_captain` command allows an administrator to assign a new captain to a team.\n"
        "Use it when you need to promote a player to captain or replace an existing one.\n"
        "*Only administrators can use this command.*\n\n"
        "### /lock_rosters\n"
        "The `/lock_rosters` command locks all team rosters, preventing any further player additions or removals.\n"
        "Use it when you want to freeze rosters, such as before a tournament or season cutoff.\n"
        "*Only administrators can use this command.*\n\n"
        "### /unlock_rosters\n"
        "The `/unlock_rosters` command unlocks all team rosters, allowing player changes to be made again.\n"
        "Use it when you want to re-open rosters after a lock period.\n"
        "*Only administrators can use this command.*"
    ]
}

Premium_commands = {
    "🖨️ /print": [
        "### What does it do?:\n"
        "The `/print` command allows a user to send a message to the channel through the bot.\n"
        "Use it when you want to send a message without revealing your identity.\n"
        "*Only members with administrator permissions can use this command.*"
    ],
    "✉️ /dm_user": [
        "### What does it do?:\n"
        "The `/dm_user` command allows a user to send a direct message to another user through the bot.\n"
        "Use it when you want to send information privately to another user without revealing your identity.\n"
        "*Only members with administrator permissions can use this command.*"
    ],
    "📋 /player_info": [
        "The `/player_info` command lets you view a player's current team, role, record, and full team history.\n"
        "Use it when you want detailed information about a player's involvement in the league.\n"
        "*Anyone within the server can use this command.*\n\n"
    ],
    "💎 Premium; Players": [
        "### /add_player\n"
        "The `/add_player` command allows an administrator to manually add a player to a team's roster, bypassing the usual invitation process.\n"
        "Use it when you want to add a player to a team without sending them an invitation.\n"
        "*Only administrators can use this command.*\n\n"
        "### /rename_team\n"
        "The `/rename_team` command allows an administrator to rename an existing team and update its associated roles.\n"
        "Use it when you want to change a team's name for any reason, such as a rebrand or correction.\n"
        "*Only administrators can use this command.*\n\n"
        "### /disband_all\n"
        "The `/disband_all` command allows an administrator to disband every team at once, removing all roles and clearing all team data.\n"
        "Use it when you want to fully reset the league or start a fresh season.\n"
        "*Only administrators can use this command.*\n\n"
        "### /list_teams\n"
        "The `/list_teams` command displays a list of all active teams currently in the league.\n"
        "Use it when you want a quick overview of all teams in the server.\n"
        "*Anyone within the server can use this command.*"
    ],
    "🏁 Scrims": [
        "### /set_scrim\n"
        "The `/set_scrim` command allows an administrator to create an official scrim embed with all the details filled in.\n"
        "Use it when you want to quickly set up a scrim without going through the usual proposal and acceptance process.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /set_time\n"
        "The `/set_time` command allows an administrator to forcibly set a scrim time in a scrim channel without needing approval from the captains.\n"
        "Use it when you need to quickly update the time of an upcoming scrim on short notice.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /end_scrim\n"
        "The `/end_scrim` command allows an administrator to record the final score of a scrim and remove team access from the scrim channel.\n"
        "Use it when a scrim has concluded and you need to log the results.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /check_scrims\n"
        "The `/check_scrims` command provides a quick list of all upcoming scrims, including the teams involved and the scheduled times.\n"
        "Use it when you want an overview of all upcoming scrims.\n"
        "*Anyone within the server can use this command.*\n\n"
        "### /create_scrim_channel\n"
        "The `/create_scrim_channel` command allows an administrator to create a private channel for two teams to coordinate their scrim.\n"
        "Use it when you want to set up a dedicated space for two teams to discuss their upcoming scrim.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /suggest_time\n"
        "The `/suggest_time` command allows a captain to propose a scrim time for the other captain to accept or decline.\n"
        "Use it when you want to suggest a specific time for an upcoming scrim and need the other captain's approval.\n"
        "*Only captains can use this command.*\n\n"
        "### /forfeit_scrim\n"
        "The `/forfeit_scrim` command allows a captain to mark their own team as forfeiting an upcoming scrim.\n"
        "Use it when your team is unable to participate in a scheduled scrim and you need to officially forfeit the match.\n"
        "*Only captains of the forfeiting team can use this command.*\n\n"
        "### /autoforfeit_scrim\n"
        "The `/autoforfeit_scrim` command allows an administrator to flag or immediately trigger an auto-forfeit for a team that has failed to show up.\n"
        "Use it when a team has not appeared for their scheduled scrim and you need to enforce the no-show rules.\n"
        "*Only members with administrator permissions can use this command.*"
    ],
    "🌱 Seeding": [
        "### /create_seeding\n"
        "The `/create_seeding` command allows an administrator to start a seeding round and track team scores.\n"
        "Use it when you want to initiate a seeding phase for the league.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /edit_seeding\n"
        "The `/edit_seeding` command allows an administrator to manually add or remove wins and/or points from a team in the seeding round.\n"
        "Use negative numbers to subtract. At least one of `wins` or `points` must be provided.\n"
        "*Only members with administrator permissions can use this command.*\n\n"
        "### /end_seeding\n"
        "The `/end_seeding` command allows an administrator to end the seeding round and display which teams advanced based on their points.\n"
        "Use it when the seeding phase has concluded and you need to finalize the standings.\n"
        "*Only members with administrator permissions can use this command.*"
    ],
}


def build_embed(category: str) -> discord.Embed:
    if Premium_enabled:
        total_commands = Free_commands.get(category, []) + Premium_commands.get(category, [])
    else:
        total_commands = Free_commands.get(category, [])
    # FIX: handle missing category explicitly
    if not total_commands:
        return discord.Embed(description="# 🤖 GTE Bot Command Guide\nCategory not found.", color=0xB3B3FC)
    embed = discord.Embed(
        description="# 🤖 GTE Bot Command Guide\n" + "\n\n".join(total_commands),
        color=0xB3B3FC)
    return embed


class CommandChoose(Select):
    def __init__(self):
        all_commands = list(Free_commands.keys())
        if Premium_enabled:
            all_commands += [cmd for cmd in Premium_commands if cmd not in all_commands]
        options = [
            discord.SelectOption(label=command, value=command)
            for command in all_commands
        ]
        super().__init__(
            placeholder="Select a command/category",
            min_values=1,
            max_values=1,
            options=options)

    async def callback(self, interaction: discord.Interaction):
        embed = build_embed(self.values[0])
        await interaction.response.edit_message(embed=embed, view=self.view)


class CommandsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CommandChoose())


@progorillacomp.tree.command(name="command_guide", description="Show the command guide with all CGTC bot commands", guild=Server_id)
async def commands_panel(interaction: discord.Interaction):
    da_commands = next(iter(Free_commands))
    embed       = build_embed(da_commands)
    view        = CommandsView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@progorillacomp.tree.command(name="create_team", description="Create a new team", guild=Server_id)
async def create_team(interaction: discord.Interaction, team_name: str,
                      captain_name: discord.Member,
                      co_captain_name: Optional[discord.Member] = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if team_name.lower() in teams:
        await interaction.response.send_message(f"**{team_name.title()}** already exists.", ephemeral=True); return
    for cand, label in [(captain_name, "Captain"), (co_captain_name, "Co-Captain")]:
        if cand:
            ex = get_player_team(cand.id)
            if ex:
                await interaction.response.send_message(
                    f"{cand.mention} is on **{ex.title()}**.", ephemeral=True); return

    await interaction.response.defer(ephemeral=True)
    async with teams_lock:
        tpr             = get_tpr(interaction.guild)
        team_role       = await interaction.guild.create_role(name=team_name.title())
        captain_role    = await interaction.guild.create_role(name=f"{team_name.title()} | Captain")
        co_captain_role = await interaction.guild.create_role(name=f"{team_name.title()} | Co-Captain")
        cap_roles   = [team_role, captain_role] + ([tpr] if tpr else [])
        await captain_name.add_roles(*cap_roles)
        if co_captain_name:
            cocap_roles = [team_role, co_captain_role] + ([tpr] if tpr else [])
            await co_captain_name.add_roles(*cocap_roles)
        teams[team_name.lower()] = {
            "name": team_name, "captain": captain_name.id,
            "co_captain": co_captain_name.id if co_captain_name else None,
            "players": [captain_name.id] + ([co_captain_name.id] if co_captain_name else []),
            "wins": 0, "losses": 0, "draws": 0,
            "team_role": team_role.id, "captain_role": captain_role.id, "co_captain_role": co_captain_role.id,
        }
        record_team_join(captain_name.id, team_name.lower())
        if co_captain_name:
            record_team_join(co_captain_name.id, team_name.lower())
        save_teams()
    await log_transaction(interaction,
        f"# **{team_name.title()}** joined CGTC\n"
        f">>> ### Captain: {captain_name.mention}\n"
        f"### Co-Captain: {co_captain_name.mention if co_captain_name else 'None'}")
    embed = discord.Embed(description=(
        f"**{team_name}** was created.\n### Roles created:\n"
        f">>> • {team_role.mention}\n• {captain_role.mention}\n• {co_captain_role.mention}"),
        color=0xB3B3FC)
    await interaction.followup.send(embed=embed, ephemeral=True)


@progorillacomp.tree.command(name="rename_team", description="Rename an existing team", guild=Server_id)
@is_premium()
@app_commands.autocomplete(team_name=team_autocomplete)
async def rename_team(interaction: discord.Interaction, team_name: str, new_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    new_lower = new_name.lower().strip()
    if not new_lower or new_lower in teams:
        await interaction.response.send_message("Invalid new name.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    async with teams_lock:
        team = teams[lower]
        for role_id, new_role_name in [
            (team["team_role"], new_name.title()),
            (team["captain_role"], f"{new_name.title()} | Captain"),
            (team["co_captain_role"], f"{new_name.title()} | Co-Captain"),
        ]:
            role = interaction.guild.get_role(role_id)
            if role:
                await role.edit(name=new_role_name)
        team["name"]     = new_name.title()
        teams[new_lower] = team
        del teams[lower]
        save_teams()

    async with seeding_lock:
        if seeding and seeding.get("order"):
            seeding["order"] = [new_lower if t == lower else t for t in seeding["order"]]
            if lower in seeding.get("points", {}):
                seeding["points"][new_lower] = seeding["points"].pop(lower)
            save_seeding(seeding)
            # FIX: refresh seeding embed immediately after rename
            seed_msg = await get_seeding_message(interaction.guild)
            if seed_msg:
                pts   = seeding.get("points", {})
                order = seeding.get("order", [])
                await seed_msg.edit(embed=build_seeding_embed(
                    order,
                    footer=f"Updated after team rename: {team_name.title()} → {new_name.title()}",
                    points=pts))

    async with scrims_lock:
        # FIX: also update scrim_message_ids keys that reference the old team name
        old_keys = [k for k in scrim_message_ids if lower in k.split(":vs:")]
        for old_key in old_keys:
            parts = old_key.split(":vs:")
            if len(parts) == 2:
                new_key = make_scrim_key(
                    new_lower if parts[0] == lower else parts[0],
                    new_lower if parts[1] == lower else parts[1]
                )
                scrim_message_ids[new_key] = scrim_message_ids.pop(old_key)
                if old_key in scrim_messages:
                    scrim_messages[new_key] = scrim_messages.pop(old_key)
        save_scrim_messages()

        for scrim in scrims_schedule:
            if scrim["team1"].lower() == lower:
                scrim["team1"] = new_name.title()
            if scrim["team2"].lower() == lower:
                scrim["team2"] = new_name.title()
        save_scrims()

    await log_transaction(interaction, f"**{team_name.title()}** renamed to **{new_name.title()}**")
    await interaction.followup.send(
        embed=discord.Embed(description=f"Renamed to **{new_name.title()}**.", color=0xB3B3FC),
        ephemeral=True)


@progorillacomp.tree.command(name="disband_team", description="Disbands an existing team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def disband_team(interaction: discord.Interaction, team_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    async with teams_lock:
        tpr  = get_tpr(interaction.guild)
        team = teams[lower]
        role_objs = [interaction.guild.get_role(team[k]) for k in ("team_role", "captain_role", "co_captain_role")]
        # FIX: snapshot player list before modifying, don't mutate while iterating
        player_ids = list(team["players"])
        for pid in player_ids:
            m = interaction.guild.get_member(pid)
            record_team_leave(pid, lower)
            if m:
                roles_to_remove = [r for r in role_objs if r and r in m.roles]
                # FIX: check if player will still be on any other team before removing tpr
                other_team = next((n for n, t in teams.items() if n != lower and pid in t["players"]), None)
                if tpr and tpr in m.roles and other_team is None:
                    roles_to_remove.append(tpr)
                if roles_to_remove:
                    await m.remove_roles(*roles_to_remove)
        for role in role_objs:
            try:
                if role:
                    await role.delete()
            except discord.NotFound:
                pass
        del teams[lower]
        save_teams()
    await log_transaction(interaction, f"**{team_name.title()}** disbanded by {interaction.user.mention}.")
    await interaction.followup.send("Team Disbanded.", ephemeral=True)


@progorillacomp.tree.command(name="disband_all", description="Disbands all teams", guild=Server_id)
@is_premium()
async def disband_all(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not teams:
        await interaction.response.send_message("No teams exist.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    async with teams_lock:
        tpr = get_tpr(interaction.guild)
        for name in list(teams.keys()):
            team  = teams[name]
            roles = [interaction.guild.get_role(team[k]) for k in ("team_role","captain_role","co_captain_role")]
            for pid in team["players"]:
                m = interaction.guild.get_member(pid)
                if m:
                    roles_to_remove = [r for r in roles if r and r in m.roles]
                    if tpr and tpr in m.roles:
                        roles_to_remove.append(tpr)
                    if roles_to_remove:
                        await m.remove_roles(*roles_to_remove)
                record_team_leave(pid, name)
            for role in roles:
                try:
                    if role:
                        await role.delete()
                except discord.NotFound:
                    pass
        teams.clear()
        save_teams()
    await log_transaction(interaction, f"All teams disbanded by {interaction.user.mention}.")
    await interaction.followup.send("All teams disbanded.", ephemeral=True)


@progorillacomp.tree.command(name="list_teams", description="List all active teams", guild=Server_id)
@is_premium()
async def list_teams(interaction: discord.Interaction):
    if not teams:
        await interaction.response.send_message("No teams exist.", ephemeral=True); return
    team_list = "\n".join(f"* **{n.title()}**" for n in teams)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"## 🏆 Current Teams:\n>>> {team_list}", color=0xB3B3FC),
        ephemeral=True)


@progorillacomp.tree.command(name="roster", description="Show the roster of a team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def roster(interaction: discord.Interaction, team_name: str):
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team = teams[lower]
    cap  = f"<@{team['captain']}>"    if team["captain"]    else "None"
    coc  = f"<@{team['co_captain']}>" if team["co_captain"] else "None"
    pls  = "\n".join(f"<@{p}>" for p in team["players"]) if team["players"] else "None"
    await interaction.response.send_message(
        embed=discord.Embed(description=(
            f"## **{team_name.title()}** Roster:\n\n"
            f">>> **Captain:** {cap}\n**Co-Captain:** {coc}\n**Players:**\n{pls}"),
            color=0xB3B3FC),
        ephemeral=True)


@progorillacomp.tree.command(name="lock_rosters", description="Lock all team rosters", guild=Server_id)
async def lock_rosters(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not teams:
        await interaction.response.send_message("No teams exist.", ephemeral=True); return
    for n in teams:
        teams[n]["locked"] = True
    save_teams()
    await log_transaction(interaction, f"All rosters locked by {interaction.user.mention}.")
    await interaction.response.send_message("All Rosters Locked.", ephemeral=True)


@progorillacomp.tree.command(name="unlock_rosters", description="Unlock all team rosters", guild=Server_id)
async def cmd_unlock_rosters(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not teams:
        await interaction.response.send_message("No teams exist.", ephemeral=True); return
    for n in teams:
        teams[n]["locked"] = False
    save_teams()
    await log_transaction(interaction, f"All rosters unlocked by {interaction.user.mention}.")
    await interaction.response.send_message("All Rosters Unlocked.", ephemeral=True)


@progorillacomp.tree.command(name="add_player", description="Manually add a player to a team", guild=Server_id)
@is_premium()
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_add_player(interaction: discord.Interaction, team_name: str, player: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team = teams[lower]
    if team.get("locked"):
        await interaction.response.send_message("Roster is locked.", ephemeral=True); return
    if player.id in team["players"]:
        await interaction.response.send_message(f"{player.mention} is already on this team.", ephemeral=True); return
    if len(team["players"]) >= 12:
        await interaction.response.send_message("Team is full.", ephemeral=True); return
    ex = get_player_team(player.id)
    if ex:
        await interaction.response.send_message(f"{player.mention} is on **{ex.title()}**.", ephemeral=True); return
    role = interaction.guild.get_role(team["team_role"])
    tpr  = get_tpr(interaction.guild)
    roles_to_add = ([role] if role else []) + ([tpr] if tpr else [])
    if roles_to_add:
        await player.add_roles(*roles_to_add)
    team["players"].append(player.id)
    record_team_join(player.id, lower)
    save_teams()
    await log_transaction(interaction, f"{player.mention} manually added to **{team_name.title()}**")
    await interaction.response.send_message(f"{player.mention} added to **{team_name.title()}**.", ephemeral=True)


@progorillacomp.tree.command(name="kick_player", description="Kick a player from a team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_kick_player(interaction: discord.Interaction, team_name: str, player: discord.Member):
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team          = teams[lower]
    is_captain    = team["captain"]    == interaction.user.id
    is_co_captain = team["co_captain"] == interaction.user.id
    is_admin      = interaction.user.guild_permissions.administrator
    if not (is_captain or is_co_captain or is_admin):
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not is_admin and interaction.user.id not in team["players"]:
        await interaction.response.send_message("You're not on this team.", ephemeral=True); return
    if player.id == interaction.user.id and not is_admin:
        await interaction.response.send_message("Use /leave_team instead.", ephemeral=True); return
    if player.id not in team["players"]:
        await interaction.response.send_message(f"{player.mention} isn't on the team.", ephemeral=True); return
    if is_co_captain and team["captain"] == player.id:
        await interaction.response.send_message("Co-captains can't kick the captain.", ephemeral=True); return
    tpr = get_tpr(interaction.guild)
    for k in ("team_role","captain_role","co_captain_role"):
        role = interaction.guild.get_role(team[k])
        if role and role in player.roles:
            await player.remove_roles(role)
    team["players"].remove(player.id)
    record_team_leave(player.id, lower)
    if team["captain"]    == player.id: team["captain"]    = None
    if team["co_captain"] == player.id: team["co_captain"] = None
    save_teams()
    if tpr and tpr in player.roles and get_player_team(player.id) is None:
        await player.remove_roles(tpr)
    await log_transaction(interaction, f"{player.mention} removed from **{team_name.title()}**.")
    await interaction.response.send_message("Done.", ephemeral=True)


@progorillacomp.tree.command(name="leave_team", description="Leave your current team", guild=Server_id)
async def cmd_leave_team(interaction: discord.Interaction):
    lower = get_player_team(interaction.user.id)
    if not lower:
        await interaction.response.send_message("You're not on any team.", ephemeral=True); return
    team = teams[lower]
    if team.get("locked"):
        await interaction.response.send_message("Roster is locked.", ephemeral=True); return
    tpr = get_tpr(interaction.guild)
    for k in ("team_role","captain_role","co_captain_role"):
        role = interaction.guild.get_role(team[k])
        if role and role in interaction.user.roles:
            await interaction.user.remove_roles(role)
    if team["captain"]    == interaction.user.id: team["captain"]    = None
    if team["co_captain"] == interaction.user.id: team["co_captain"] = None
    team["players"].remove(interaction.user.id)
    record_team_leave(interaction.user.id, lower)
    save_teams()
    if tpr and tpr in interaction.user.roles and get_player_team(interaction.user.id) is None:
        await interaction.user.remove_roles(tpr)
    await log_transaction(interaction, f"{interaction.user.mention} left **{lower.title()}**.")
    await interaction.response.send_message(f"You left **{lower.title()}**.", ephemeral=True)


@progorillacomp.tree.command(name="assign_captain", description="Assign a captain to a team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_assign_captain(interaction: discord.Interaction, team_name: str, player: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team = teams[lower]
    if team["captain"] == player.id:
        await interaction.response.send_message(f"{player.mention} is already captain.", ephemeral=True); return
    if player.id not in team["players"]:
        await interaction.response.send_message(f"{player.mention} isn't on the team.", ephemeral=True); return
    tpr = get_tpr(interaction.guild)
    if team["captain"]:
        old      = interaction.guild.get_member(team["captain"])
        cap_role = interaction.guild.get_role(team["captain_role"])
        if old and cap_role:
            await old.remove_roles(cap_role)
    cap_role = interaction.guild.get_role(team["captain_role"])
    roles_to_add = ([cap_role] if cap_role else []) + ([tpr] if tpr else [])
    if roles_to_add:
        await player.add_roles(*roles_to_add)
    team["captain"] = player.id
    save_teams()
    await log_transaction(interaction, f"{player.mention} assigned captain of **{team_name.title()}**.")
    await interaction.response.send_message("Done.", ephemeral=True)


@progorillacomp.tree.command(name="assign_cocaptain", description="Assign a co-captain to a team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_assign_cocaptain(interaction: discord.Interaction, team_name: str, player: discord.Member):
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team = teams[lower]
    if not (team["captain"] == interaction.user.id or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if team["co_captain"] == player.id:
        await interaction.response.send_message(f"{player.mention} is already co-captain.", ephemeral=True); return
    if player.id not in team["players"]:
        await interaction.response.send_message(f"{player.mention} isn't on the team.", ephemeral=True); return
    tpr = get_tpr(interaction.guild)
    if team["co_captain"]:
        old      = interaction.guild.get_member(team["co_captain"])
        coc_role = interaction.guild.get_role(team["co_captain_role"])
        if old and coc_role:
            await old.remove_roles(coc_role)
    coc_role = interaction.guild.get_role(team["co_captain_role"])
    roles_to_add = ([coc_role] if coc_role else []) + ([tpr] if tpr else [])
    if roles_to_add:
        await player.add_roles(*roles_to_add)
    team["co_captain"] = player.id
    save_teams()
    await log_transaction(interaction, f"{player.mention} assigned co-captain of **{team_name.title()}**.")
    await interaction.response.send_message("Done.", ephemeral=True)


@progorillacomp.tree.command(name="transfer_captain", description="Transfer captaincy to another player", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_transfer_captain(interaction: discord.Interaction, team_name: str, player: discord.Member):
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team = teams[lower]
    if not (team["captain"] == interaction.user.id or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if player.id == interaction.user.id:
        await interaction.response.send_message("Can't transfer to yourself.", ephemeral=True); return
    if team["captain"] == player.id:
        await interaction.response.send_message(f"{player.mention} is already captain.", ephemeral=True); return
    if player.id not in team["players"]:
        await interaction.response.send_message(f"{player.mention} isn't on the team.", ephemeral=True); return
    tpr = get_tpr(interaction.guild)
    if team["captain"]:
        old      = interaction.guild.get_member(team["captain"])
        cap_role = interaction.guild.get_role(team["captain_role"])
        if old and cap_role:
            await old.remove_roles(cap_role)
    cap_role = interaction.guild.get_role(team["captain_role"])
    roles_to_add = ([cap_role] if cap_role else []) + ([tpr] if tpr else [])
    if roles_to_add:
        await player.add_roles(*roles_to_add)
    team["captain"] = player.id
    save_teams()
    await log_transaction(interaction, f"{player.mention} is now captain of **{team_name.title()}**.")
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"Captaincy of **{team_name.title()}** transferred to {player.mention}.",
            color=0xB3B3FC),
        ephemeral=True)


@progorillacomp.tree.command(name="invite_player", description="Invite a player to a team", guild=Server_id)
@app_commands.autocomplete(team_name=team_autocomplete)
async def cmd_invite_player(interaction: discord.Interaction, team_name: str, player: discord.Member):
    lower = team_name.lower()
    if lower not in teams:
        await interaction.response.send_message(f"**{team_name.title()}** doesn't exist.", ephemeral=True); return
    team          = teams[lower]
    is_captain    = team["captain"]    == interaction.user.id
    is_co_captain = team["co_captain"] == interaction.user.id
    is_admin      = interaction.user.guild_permissions.administrator
    if not (is_captain or is_co_captain or is_admin):
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not is_admin and interaction.user.id not in team["players"]:
        await interaction.response.send_message("You're not on this team.", ephemeral=True); return
    if team.get("locked"):
        await interaction.response.send_message("Rosters are locked.", ephemeral=True); return
    if player.id in team["players"]:
        await interaction.response.send_message(f"{player.mention} is already on the team.", ephemeral=True); return
    if len(team["players"]) >= 12:
        await interaction.response.send_message("Team is full.", ephemeral=True); return
    if interaction.guild.get_role(team["team_role"]) is None:
        await interaction.response.send_message("Team role not found.", ephemeral=True); return
    ex = get_player_team(player.id)
    if ex:
        await interaction.response.send_message(f"{player.mention} is on **{ex.title()}**.", ephemeral=True); return
    if any(i["team_name"] == lower for i in pending_invites.get(player.id, [])):
        await interaction.response.send_message(f"{player.mention} already has a pending invite.", ephemeral=True); return
    pending_invites.setdefault(player.id, []).append({"team_name": lower, "inviter_id": interaction.user.id})
    save_invites()
    await interaction.response.send_message(f"Invite sent to {player.mention}.", ephemeral=True)


@progorillacomp.tree.command(name="check_invites", description="View your pending team invites", guild=Server_id)
async def cmd_check_invites(interaction: discord.Interaction):
    invites = pending_invites.get(interaction.user.id, [])
    if not invites:
        await interaction.response.send_message("No pending invites.", ephemeral=True); return
    await interaction.response.send_message(
        content="## Your pending invites\nClick a team to accept or decline:",
        view=MyInvitesView(interaction.user, invites), ephemeral=True)


@progorillacomp.tree.command(name="player_info", description="View a player's profile", guild=Server_id)
@is_premium()
async def cmd_player_info(interaction: discord.Interaction, player: discord.Member):
    team_key = get_player_team(player.id)
    if team_key:
        team      = teams[team_key]
        team_name = team_key.title()
        w, l, d   = team.get("wins",0), team.get("losses",0), team.get("draws",0)
        role_label = ("👑 Captain" if team["captain"] == player.id
                      else "⭐ Co-Captain" if team["co_captain"] == player.id
                      else "🎮 Player")
    else:
        team_name = "Free Agent"; w = l = d = 0; role_label = "—"
    history = player_history.get(str(player.id), [])
    hist_str = "\n".join(
        f"{'➕ Joined' if e['action']=='joined' else '➖ Left'} **{e['team'].title()}** — `{e['timestamp'][:10]}`"
        for e in reversed(history)) or "No history on record."
    embed = discord.Embed(description=(
        f"# 🎮 {player.display_name}\n"
        f">>> **Team:** {team_name}\n**Role:** {role_label}\n\n"
        f"**Record:** {w}W / {l}L / {d}D\n## 📋 Team History\n{hist_str}"),
        color=0xB3B3FC)
    embed.set_thumbnail(url=player.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)


@progorillacomp.tree.command(name="create_seeding", description="Create a seeding round", guild=Server_id)
@is_premium()
@app_commands.describe(win_points="Points per win", loss_points="Points per loss")
async def cmd_create_seeding(interaction: discord.Interaction, win_points: int, loss_points: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not teams:
        await interaction.response.send_message("No teams yet.", ephemeral=True); return
    for n in teams:
        teams[n]["wins"] = teams[n]["losses"] = teams[n]["draws"] = 0
    save_teams()
    points = {n: 0 for n in teams}
    order  = sorted(points, key=lambda k: points[k], reverse=True)
    embed  = build_seeding_embed(order, footer=f"Seeding created by {interaction.user.display_name}", points=points)
    await interaction.response.send_message("Done.", ephemeral=True)
    message = await interaction.channel.send(embed=embed)
    seeding.update({
        "created_by": interaction.user.id, "created_at": discord.utils.utcnow().isoformat(),
        "order": order, "points": points, "win_points": win_points, "loss_points": loss_points,
        "channel_id": interaction.channel.id, "message_id": message.id, "locked": False,
    })
    save_seeding(seeding)


@progorillacomp.tree.command(name="edit_seeding", description="Edit a team's wins and/or points in seeding", guild=Server_id)
@is_premium()
@app_commands.autocomplete(team_name=seeding_team_autocomplete)
@app_commands.describe(
    team_name="Team to edit",
    wins="Wins to add (use negative to subtract)",
    points="Points to add (use negative to subtract)"
)
async def cmd_edit_seeding(
    interaction: discord.Interaction,
    team_name: str,
    wins: int = 0,
    points: int = 0
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not seeding or not seeding.get("order"):
        await interaction.response.send_message("No seeding active.", ephemeral=True); return
    if seeding.get("locked"):
        await interaction.response.send_message("Seeding is locked.", ephemeral=True); return

    lower = team_name.lower()
    if lower not in seeding["order"]:
        await interaction.response.send_message(f"**{team_name.title()}** not in seeding.", ephemeral=True); return
    if wins == 0 and points == 0:
        await interaction.response.send_message("Provide at least one of `wins` or `points`.", ephemeral=True); return

    async with seeding_lock:
        # Apply wins to team record
        if wins != 0 and lower in teams:
            if wins > 0:
                teams[lower]["wins"] = teams[lower].get("wins", 0) + wins
            else:
                teams[lower]["wins"] = max(0, teams[lower].get("wins", 0) + wins)
            save_teams()

        # Apply points
        pts = seeding.get("points", {})
        if points != 0:
            pts[lower] = max(0, pts.get(lower, 0) + points)

        order = sorted(pts, key=lambda k: pts[k], reverse=True)
        seeding["order"] = order
        seeding["points"] = pts
        save_seeding(seeding)

    original  = await get_seeding_message(interaction.guild)
    footer    = original.embeds[0].footer.text if original and original.embeds else f"Updated by {interaction.user.display_name}"
    new_embed = build_seeding_embed(order, footer=footer, points=pts)
    if original:
        await original.edit(embed=new_embed)

    changes = []
    if wins != 0:
        changes.append(f"{'➕' if wins > 0 else '➖'} **{abs(wins)} win(s)** {'added to' if wins > 0 else 'removed from'} **{team_name.title()}**")
    if points != 0:
        changes.append(f"{'➕' if points > 0 else '➖'} **{abs(points)} point(s)** {'added to' if points > 0 else 'removed from'} **{team_name.title()}**")

    await interaction.response.send_message(
        embed=discord.Embed(description="\n".join(changes), color=0xB3B3FC),
        ephemeral=True)


@progorillacomp.tree.command(name="end_seeding", description="End the seeding round", guild=Server_id)
@is_premium()
@app_commands.describe(qualifiers="Number of teams that advance")
async def cmd_end_seeding(interaction: discord.Interaction, qualifiers: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if not seeding or not seeding.get("order"):
        await interaction.response.send_message("No seeding yet.", ephemeral=True); return
    if seeding.get("locked"):
        await interaction.response.send_message("Seeding already ended.", ephemeral=True); return
    order = seeding["order"]
    if not 1 <= qualifiers <= len(order):
        await interaction.response.send_message(f"Must be 1–{len(order)}.", ephemeral=True); return
    seeding["locked"] = True
    seeding["qualifiers"] = qualifiers
    save_seeding(seeding)
    pts   = seeding.get("points", {})
    embed = build_seeding_embed(order,
        footer=f"Ended by {interaction.user.display_name} — {qualifiers}/{len(order)} advanced",
        points=pts, ended=True, qualifiers=qualifiers)
    msg = await get_seeding_message(interaction.guild)
    if msg:
        await msg.edit(embed=embed)
        await interaction.response.send_message("Seeding ended.", ephemeral=True)
    else:
        await interaction.response.send_message("Original not found, posting new.", ephemeral=True)
        new = await interaction.channel.send(embed=embed)
        seeding["channel_id"] = interaction.channel.id
        seeding["message_id"] = new.id
        save_seeding(seeding)


# ── /set_scrim ────────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="set_scrim", description="Set a time and date for a scrim", guild=Server_id)
@is_premium()
@app_commands.autocomplete(first_team=team_autocomplete, second_team=team_autocomplete)
async def cmd_set_scrim(interaction: discord.Interaction, time: str, date: str,
                        first_team: str, second_team: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    if first_team.lower() == second_team.lower():
        await interaction.response.send_message("Teams can't be the same.", ephemeral=True); return
    # FIX: check for duplicate scrim
    t1l, t2l = first_team.lower(), second_team.lower()
    for s in scrims_schedule:
        if (s["team1"].lower() == t1l and s["team2"].lower() == t2l) or \
           (s["team1"].lower() == t2l and s["team2"].lower() == t1l):
            await interaction.response.send_message(
                f"A scrim between **{first_team.title()}** and **{second_team.title()}** already exists.",
                ephemeral=True); return

    await interaction.response.send_message("Scrim created.", ephemeral=True)
    key = make_scrim_key(first_team, second_team)
    await post_scrim_to_channels(
        interaction.guild, key,
        time, date, first_team.title(), second_team.title())
    scrims_schedule.append({"time": time, "date": date,
                             "team1": first_team.title(), "team2": second_team.title()})
    save_scrims()


# ── /suggest_time ─────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="suggest_time", description="Propose a scrim time in a scrim channel", guild=Server_id)
@is_premium()
async def cmd_suggest_time(interaction: discord.Interaction, time: str, date: str):
    channel_data = scrim_channels.get(interaction.channel.id)
    if not channel_data:
        await interaction.response.send_message("Only usable in a scrim channel.", ephemeral=True); return
    t1_key = channel_data["t1_key"]
    t2_key = channel_data["t2_key"]
    if t1_key not in teams or t2_key not in teams:
        await interaction.response.send_message("One or both teams no longer exist.", ephemeral=True); return
    team1 = teams[t1_key]
    team2 = teams[t2_key]
    uid   = interaction.user.id
    is_t1 = uid in (team1["captain"], team1["co_captain"])
    is_t2 = uid in (team2["captain"], team2["co_captain"])
    if not (is_t1 or is_t2):
        await interaction.response.send_message("Only captains can propose a time.", ephemeral=True); return
    other_captain_id = team2["captain"] if is_t1 else team1["captain"]
    other_team_name  = t2_key if is_t1 else t1_key
    if not other_captain_id:
        await interaction.response.send_message(f"**{other_team_name.title()}** has no captain.", ephemeral=True); return
    await interaction.response.send_message("Proposal sent!", ephemeral=True)
    embed = discord.Embed(description=(
        f"# 🕐 Scrim Time Proposal\n"
        f">>> **{t1_key.title()}** vs **{t2_key.title()}**\n\n"
        f"**Proposed Time:** {time}\n**Proposed Date:** {date}\n\n"
        f"*Proposed by {interaction.user.mention}*"), color=0xB3B3FC)
    await interaction.channel.send(f"<@{other_captain_id}>", embed=embed,
        view=ScrimProposalView(t1_key, t2_key, time, date, uid, other_captain_id))


# ── /set_time ─────────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="set_time", description="Forcibly set a scrim time (Admin only)", guild=Server_id)
@is_premium()
async def cmd_set_time(interaction: discord.Interaction, time: str, date: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    channel_data = scrim_channels.get(interaction.channel.id)
    if not channel_data:
        await interaction.response.send_message("Channel not registered.", ephemeral=True); return
    t1_key = channel_data["t1_key"]
    t2_key = channel_data["t2_key"]
    if t1_key not in teams or t2_key not in teams:
        await interaction.response.send_message("One or both teams no longer exist.", ephemeral=True); return
    await interaction.response.send_message(f"Scrim set for **{date}** at **{time}**!", ephemeral=True)
    key = make_scrim_key(t1_key, t2_key)
    await post_scrim_to_channels(
        interaction.guild, key,
        time, date, t1_key.title(), t2_key.title())
    scrims_schedule.append({"time": time, "date": date, "team1": t1_key.title(), "team2": t2_key.title()})
    save_scrims()


# ── shared forfeit logic ──────────────────────────────────────────────────────

async def _process_forfeit(interaction: discord.Interaction, team1: str, team2: str,
                            forfeiting_team: str, reason: str, auto: bool = False):
    global scrims_schedule
    fkey   = forfeiting_team.lower()
    winner = (team2 if fkey == team1.lower() else team1).lower()
    loser  = fkey
    key    = make_scrim_key(team1, team2)

    forfeit_embed = discord.Embed(description=(
        f"# **----------🚫 SCRIM FORFEITED----------**\n"
        f">>> ## **Official Scrim:**\n\n"
        f"**First Team:** {team1.title()}\n**Second Team:** {team2.title()}\n\n"
        f"**🏆 Winner:** {winner.title()} (by {'auto-' if auto else ''}forfeit)\n"
        f"**❌ Forfeit:** {loser.title()}\n**Reason:** {reason}"),
        color=discord.Color.orange())

    msg = await get_scrim_message(interaction.guild, key)
    if msg:
        try:
            await msg.edit(embed=forfeit_embed, view=None)
        except Exception:
            pass
        mirror = await get_mirror_message(interaction.guild, key)
        if mirror:
            try:
                await mirror.edit(embed=forfeit_embed)
            except Exception:
                pass
        scrim_messages.pop(key, None)
        scrim_message_ids.pop(key, None)
        save_scrim_messages()

    scrims_schedule = [s for s in scrims_schedule
                       if not (s["team1"].lower() == team1.lower() and s["team2"].lower() == team2.lower())]
    save_scrims()
    if winner in teams:
        teams[winner]["wins"]   = teams[winner].get("wins", 0) + 1
    if loser in teams:
        teams[loser]["losses"]  = teams[loser].get("losses", 0) + 1
    save_teams()
    await apply_seeding_result(interaction, winner, loser,
                               f"Updated after {loser.title()} forfeited vs {winner.title()}")

    label = "Auto-Forfeit" if auto else "Scrim Forfeit"
    result_embed = discord.Embed(description=(
        f"# 🚫 {label}\n>>> **{team1.title()}** vs **{team2.title()}**\n\n"
        f"**🏆 Winner:** {winner.title()} *(by {'auto-' if auto else ''}forfeit)*\n"
        f"**❌ Forfeited by:** {loser.title()}\n**Reason:** {reason}"),
        color=discord.Color.orange())
    result_embed.set_footer(text=f"{'Auto-forfeit' if auto else 'Forfeit'} logged by {interaction.user.display_name}")
    await interaction.channel.send(embed=result_embed)


# ── /end_scrim ────────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="end_scrim", description="End and record the score of a scrim", guild=Server_id)
@is_premium()
@app_commands.autocomplete(scrim=scrim_autocomplete)
async def cmd_end_scrim(interaction: discord.Interaction, scrim: str,
                        score1: int, score2: int, notes: str = ""):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    parts = scrim.split("|")
    if len(parts) != 4:
        await interaction.response.send_message("Invalid scrim.", ephemeral=True); return
    team1, team2, time, date = parts
    if team1 == team2:
        await interaction.response.send_message("Teams can't be the same.", ephemeral=True); return

    key = make_scrim_key(team1, team2)
    msg = await get_scrim_message(interaction.guild, key)

    result_str = (f"{team1.title()} wins" if score1 > score2
                  else f"{team2.title()} wins" if score2 > score1 else "Draw")
    completed_embed = discord.Embed(
        description=(
            "# **----------✅ SCRIM COMPLETED----------**\n"
            ">>> ## **Official Scrim For CGTC:**\n\n"
            f"**First Team:** {team1.title()}\n**Second Team:** {team2.title()}\n\n"
            f"**Result:** {result_str} **{score1} - {score2}**"),
        color=0x57F287)

    if msg:
        try:
            await msg.edit(embed=completed_embed, view=None)
        except Exception:
            pass
        mirror = await get_mirror_message(interaction.guild, key)
        if mirror:
            try:
                await mirror.edit(embed=completed_embed)
            except Exception:
                pass
        scrim_messages.pop(key, None)
        scrim_message_ids.pop(key, None)
        save_scrim_messages()

    global scrims_schedule
    scrims_schedule = [s for s in scrims_schedule
                       if not (s["team1"].lower() == team1 and s["team2"].lower() == team2)]
    save_scrims()

    if score1 == score2:
        t1, t2 = team1.lower(), team2.lower()
        for t in (t1, t2):
            if t in teams:
                teams[t]["draws"] = teams[t].get("draws", 0) + 1
        save_teams()
        if seeding and seeding.get("order") and not seeding.get("locked"):
            loss_pts = seeding.get("loss_points", 0)
            pts      = seeding.get("points", {})
            updated  = False
            for t in (t1, t2):
                if t in pts:
                    pts[t] = pts.get(t, 0) + loss_pts
                    updated = True
            if updated:
                order = sorted(pts, key=lambda k: pts[k], reverse=True)
                seeding["order"] = order
                seeding["points"] = pts
                save_seeding(seeding)
                seed_msg = await get_seeding_message(interaction.guild)
                if seed_msg:
                    await seed_msg.edit(embed=build_seeding_embed(
                        order, footer=f"Updated after {team1.title()} vs {team2.title()}", points=pts))
    else:
        winner = (team1 if score1 > score2 else team2).lower()
        loser  = (team2 if score1 > score2 else team1).lower()
        if winner in teams:
            teams[winner]["wins"]   = teams[winner].get("wins", 0) + 1
        if loser in teams:
            teams[loser]["losses"]  = teams[loser].get("losses", 0) + 1
        save_teams()
        await apply_seeding_result(interaction, winner, loser,
                                   f"Updated after {team1.title()} vs {team2.title()}")

    outcome = "🤝 Draw" if score1 == score2 else f"🏆 {team1.title() if score1 > score2 else team2.title()} Wins"
    result_embed = discord.Embed(description=(
        "# 🏆 Scrim Result\n"
        f">>> ### Match:\n**{team1.title()}** vs **{team2.title()}**\n"
        f"### Score:\n**{score1} - {score2}**\n### Result:\n**{outcome}**"),
        color=0xB3B3FC)
    if notes:
        result_embed.add_field(name="Notes", value=notes, inline=False)
    result_embed.set_footer(text="Good Game!")
    result_ch = interaction.guild.get_channel(Scrim_score_channel)
    await interaction.response.send_message("Scrim score logged.", ephemeral=True)
    if result_ch:
        await result_ch.send(embed=result_embed)

    t1_key, t2_key = team1.lower(), team2.lower()
    stale = [cid for cid, d in scrim_channels.items()
             if (d["t1_key"] == t1_key and d["t2_key"] == t2_key)
             or (d["t1_key"] == t2_key and d["t2_key"] == t1_key)]
    for cid in stale:
        ch = interaction.guild.get_channel(cid)
        if ch:
            try:
                for tkey in (t1_key, t2_key):
                    role = interaction.guild.get_role(teams.get(tkey, {}).get("team_role"))
                    if role:
                        await ch.set_permissions(role, view_channel=False)
            except Exception:
                pass
        scrim_channels.pop(cid, None)
    save_scrim_channels()


# ── /check_scrims ─────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="check_scrims", description="View upcoming scrims", guild=Server_id)
@is_premium()
async def cmd_check_scrims(interaction: discord.Interaction):
    if not scrims_schedule:
        await interaction.response.send_message("No scrims scheduled.", ephemeral=True); return
    lines = "\n".join(f"• **{s['team1']}** vs **{s['team2']}**\n  {s['date']} at {s['time']}"
                      for s in scrims_schedule)
    await interaction.response.send_message(
        embed=discord.Embed(title="Upcoming Scrims:", description=f">>> {lines}", color=0xB3B3FC),
        ephemeral=True)


# ── /create_scrim_channel ─────────────────────────────────────────────────────

@progorillacomp.tree.command(name="create_scrim_channel", description="Create a private scrim channel", guild=Server_id)
@is_premium()
@app_commands.autocomplete(first_team=team_autocomplete, second_team=team_autocomplete, category_name=category_autocomplete)
@app_commands.describe(first_team="First team", second_team="Second team", category_name="Category (default: Scheduling)")
async def cmd_create_scrim_channel(interaction: discord.Interaction, first_team: str, second_team: str, category_name: str = "Scheduling"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    t1, t2 = first_team.lower(), second_team.lower()
    if t1 == t2:
        await interaction.response.send_message("Teams can't be the same.", ephemeral=True); return
    if t1 not in teams:
        await interaction.response.send_message(f"**{first_team.title()}** doesn't exist.", ephemeral=True); return
    if t2 not in teams:
        await interaction.response.send_message(f"**{second_team.title()}** doesn't exist.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    category = discord.utils.get(interaction.guild.categories, name=category_name)
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    for tkey in (t1, t2):
        role = interaction.guild.get_role(teams[tkey]["team_role"])
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    # Allow commentators, casters, and refs to view but not send
    for role_id in (Commentator_role, Caster_role, Referee_role):
        role = interaction.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    for role in interaction.guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    channel = await interaction.guild.create_text_channel(
        name=f"「⛹️」{t1}-vs-{t2}", category=category, overwrites=overwrites,
        topic=f"Private scrim channel: {first_team.title()} vs {second_team.title()}")
    embed = discord.Embed(description=(
        f"# 🏓 Scrim Channel\n"
        f">>> ## **{first_team.title()}** vs **{second_team.title()}**\n\n"
        f"This is your private scrim scheduling channel.\n"
        f"You have 4 days to complete your scrim.\n"
        f"Type `/suggest_time` to suggest a time to the other captain.\n"
        f"To forfeit, type `/forfeit_scrim`."), color=0xB3B3FC)
    embed.set_footer(text="Good luck to both teams!")

    msg = ""
    for tkey in (t1, t2):
        role = interaction.guild.get_role(teams[tkey]["team_role"])
        if role:
            msg += role.mention + " "

    await channel.send(content=msg.strip(), embed=embed)
    scrim_channels[channel.id] = {"t1_key": t1, "t2_key": t2}
    save_scrim_channels()
    await interaction.followup.send(f"✅ Scrim channel created: {channel.mention}", ephemeral=True)


# ── /forfeit_scrim ────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="forfeit_scrim", description="Forfeit a scrim", guild=Server_id)
@is_premium()
@app_commands.autocomplete(scrim=scrim_autocomplete, forfeiting_team=team_autocomplete)
async def cmd_forfeit_scrim(interaction: discord.Interaction, scrim: str,
                            forfeiting_team: str, reason: str = "No reason provided"):
    uid      = interaction.user.id
    is_admin = interaction.user.guild_permissions.administrator
    parts = scrim.split("|")
    if len(parts) != 4:
        await interaction.response.send_message("Invalid scrim.", ephemeral=True); return
    team1, team2, time, date = parts
    fkey = forfeiting_team.lower()
    if fkey not in (team1.lower(), team2.lower()):
        await interaction.response.send_message(f"**{forfeiting_team.title()}** isn't in this scrim.", ephemeral=True); return

    # FIX: captains can only forfeit their own team, not the opponent's
    if not is_admin:
        forfeiting_team_data = teams.get(fkey, {})
        is_cap_of_forfeiting = (
            forfeiting_team_data.get("captain") == uid or
            forfeiting_team_data.get("co_captain") == uid
        )
        if not is_cap_of_forfeiting:
            await interaction.response.send_message(
                "You can only forfeit your own team.", ephemeral=True); return

    await interaction.response.send_message("Forfeit logged.", ephemeral=True)
    await _process_forfeit(interaction, team1, team2, forfeiting_team, reason, auto=False)


# ── /autoforfeit_scrim ────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="autoforfeit_scrim", description="Auto-forfeit a scrim (Admin only)", guild=Server_id)
@is_premium()
@app_commands.autocomplete(scrim=scrim_autocomplete, forfeiting_team=team_autocomplete)
async def cmd_autoforfeit_scrim(interaction: discord.Interaction, scrim: str, forfeiting_team: str, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    parts = scrim.split("|")
    if len(parts) != 4:
        await interaction.response.send_message("Invalid scrim.", ephemeral=True); return
    team1, team2, time, date = parts
    fkey = forfeiting_team.lower()
    if fkey not in (team1.lower(), team2.lower()):
        await interaction.response.send_message(f"**{forfeiting_team.title()}** isn't in this scrim.", ephemeral=True); return

    await interaction.response.send_message("Auto-forfeit logged.", ephemeral=True)
    await _process_forfeit(interaction, team1, team2, forfeiting_team, reason, auto=True)


# ── /send_files ───────────────────────────────────────────────────────────────

@progorillacomp.tree.command(name="send_files", description="Sends all JSON data files.", guild=Server_id)
async def send_files(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    files = [discord.File(p, filename=os.path.basename(p))
             for p in (Team_file, Scrim_file, Scrim_message_file,
                       Invite_file, Seeding_file, Scrim_channel_file, Player_history_file)
             if os.path.exists(p)]
    if not files:
        await interaction.followup.send("No data files found.", ephemeral=True); return
    await interaction.followup.send(
        embed=discord.Embed(
            description=f"# CGTC Data Backup\n>>> **{len(files)} files** attached.\n*Keep these safe!*",
            color=0xB3B3FC),
        files=files, ephemeral=True)


# ── Run ───────────────────────────────────────────────────────────────────────

progorillacomp.run(os.getenv('TOKEN'))
