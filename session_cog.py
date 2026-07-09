import discord
from discord.ext import commands
from discord import app_commands
import database
from config import Config
import datetime

class SessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    session_group = app_commands.Group(name="session", description="Manage mentoring sessions")

    def _resolve_moderator_role(self, guild: discord.Guild) -> discord.Role:
        mod_setting = Config.MODERATOR_ROLE
        if mod_setting.isdigit():
            role = guild.get_role(int(mod_setting))
            if role:
                return role
        for role in guild.roles:
            if role.name.lower() == mod_setting.lower():
                return role
        return None

    def _is_moderator(self, member: discord.Member, mod_role: discord.Role) -> bool:
        if member.guild_permissions.administrator:
            return True
        if mod_role and mod_role in member.roles:
            return True
        return False

    @session_group.command(name="initiate", description="Initiate a private session between a mentee and a mentor")
    @app_commands.describe(
        mentee="The mentee for this session",
        mentor="The mentor for this session",
        category="The category to create the session channel in"
    )
    async def initiate(
        self,
        interaction: discord.Interaction,
        mentee: discord.Member,
        mentor: discord.Member,
        category: discord.CategoryChannel
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("you do not have permission to initiate a session. only moderators can do this.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            mentee: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            mentor: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        try:
            channel = await guild.create_text_channel(
                name="session-temp",
                category=category,
                overwrites=overwrites,
                topic=f"Mentoring session between Mentee {mentee.display_name} and Mentor {mentor.display_name}."
            )
            session_id = database.create_session(
                channel_id=channel.id,
                mentee_id=mentee.id,
                mentor_id=mentor.id
            )
            await channel.edit(name=f"session-{session_id}")

            embed = discord.Embed(
                title="new mentoring session initiated",
                description="welcome to your private mentoring channel! this channel is only visible to the mentee, mentor, and moderators.",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="session id", value=f"`{session_id}`", inline=True)
            embed.add_field(name="channel", value=channel.mention, inline=True)
            embed.add_field(name="mentee", value=mentee.mention, inline=True)
            embed.add_field(name="mentor", value=mentor.mention, inline=True)
            embed.set_footer(text="peer project • peerproject.in")

            ping_mentions = f"{mentee.mention} {mentor.mention}"
            if mod_role:
                ping_mentions += f" {mod_role.mention}"

            await channel.send(content=ping_mentions, embed=embed)
            await interaction.followup.send(
                f"session `{session_id}` successfully initiated! created channel {channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"failed to initiate session: {str(e)}", ephemeral=True)

    @session_group.command(name="info", description="View info for a session")
    @app_commands.describe(
        session_id="Optional: Search by Session ID",
        channel="Optional: Search by channel"
    )
    async def info(
        self,
        interaction: discord.Interaction,
        session_id: int = None,
        channel: discord.TextChannel = None
    ):
        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.")
            return

        session_data = None
        if session_id is not None:
            session_data = database.get_session_by_id(session_id)
            if not session_data:
                await interaction.followup.send(f"no session found with ID `{session_id}`.")
                return
        elif channel is not None:
            session_data = database.get_session_by_channel(channel.id)
            if not session_data:
                await interaction.followup.send(f"no session found associated with channel {channel.mention}.")
                return
        else:
            session_data = database.get_session_by_channel(interaction.channel_id)
            if not session_data:
                await interaction.followup.send("this channel is not an active mentoring session. please specify a session id or channel.")
                return

        mentee_id = session_data["mentee_id"]
        mentor_id = session_data["mentor_id"]
        chan_id = session_data["channel_id"]

        mentee = guild.get_member(mentee_id)
        mentor = guild.get_member(mentor_id)
        session_chan = guild.get_channel(chan_id)

        mentee_str = mentee.mention if mentee else f"left server (id: {mentee_id})"
        mentor_str = mentor.mention if mentor else f"left server (id: {mentor_id})"
        chan_str = session_chan.mention if session_chan else f"#deleted-channel (id: {chan_id})"

        status_text = "active" if session_data["status"] == "active" else "nuked"
        
        embed = discord.Embed(
            title=f"session info: {session_data['session_id']}",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="session id", value=f"`{session_data['session_id']}`", inline=True)
        embed.add_field(name="status", value=status_text, inline=True)
        embed.add_field(name="channel", value=chan_str, inline=False)
        embed.add_field(name="mentee", value=mentee_str, inline=True)
        embed.add_field(name="mentor", value=mentor_str, inline=True)
        embed.add_field(name="created at", value=str(session_data["created_at"]).lower(), inline=False)
        embed.set_footer(text="peer project • peerproject.in")

        await interaction.followup.send(embed=embed)

    @session_group.command(name="nuke", description="Deletes the session channel and marks it as nuked in database")
    @app_commands.describe(
        session_id="Optional: Search by Session ID to nuke",
        channel="Optional: Search by channel to nuke"
    )
    async def nuke(
        self,
        interaction: discord.Interaction,
        session_id: int = None,
        channel: discord.TextChannel = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("you do not have permission to nuke sessions. only moderators can do this.", ephemeral=True)
            return

        session_data = None
        if session_id is not None:
            session_data = database.get_session_by_id(session_id)
            if not session_data:
                await interaction.followup.send(f"no session found with ID `{session_id}`.", ephemeral=True)
                return
        elif channel is not None:
            session_data = database.get_session_by_channel(channel.id)
            if not session_data:
                await interaction.followup.send(f"no session found associated with channel {channel.mention}.", ephemeral=True)
                return
        else:
            session_data = database.get_session_by_channel(interaction.channel_id)
            if not session_data:
                await interaction.followup.send("this channel is not an active mentoring session. please specify a session id or channel.", ephemeral=True)
                return

        database.nuke_session(session_data["session_id"])
        target_channel = guild.get_channel(session_data["channel_id"])
        
        if target_channel:
            try:
                if target_channel.id == interaction.channel_id:
                    await interaction.followup.send("nuking this channel now...", ephemeral=True)
                    await target_channel.delete(reason=f"Session {session_data['session_id']} nuked by {interaction.user}")
                else:
                    await target_channel.delete(reason=f"Session {session_data['session_id']} nuked by {interaction.user}")
                    await interaction.followup.send(f"session `{session_data['session_id']}` (channel: {target_channel.name}) has been nuked.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"marked as nuked in DB, but failed to delete channel: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"session `{session_data['session_id']}` marked as nuked in DB (channel was already deleted).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SessionCog(bot))
