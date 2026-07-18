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
        mentor_2="The optional second mentor for co-mentoring",
        category="The category to create the session channel in"
    )
    async def initiate(
        self,
        interaction: discord.Interaction,
        mentee: discord.Member,
        mentor: discord.Member,
        category: discord.CategoryChannel,
        mentor_2: discord.Member = None
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
        if mentor_2:
            overwrites[mentor_2] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        try:
            topic = f"Mentoring session between Mentee {mentee.display_name} and Mentor {mentor.display_name}."
            if mentor_2:
                topic = f"Mentoring session between Mentee {mentee.display_name} and Co-Mentors {mentor.display_name} & {mentor_2.display_name}."

            channel = await guild.create_text_channel(
                name="session-temp",
                category=category,
                overwrites=overwrites,
                topic=topic
            )
            session_id = database.create_session(
                channel_id=channel.id,
                mentee_id=mentee.id,
                mentor_id=mentor.id,
                mentor_2_id=mentor_2.id if mentor_2 else None
            )
            await channel.edit(name=f"session-{session_id}")

            embed = discord.Embed(
                title="Mentoring Session Initiated!",
                description="Welcome to your private mentoring session! This channel is only visible to the mentee, mentor(s), and TPP admins.",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="Session-ID", value=f"`{session_id}`", inline=True)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Mentee", value=mentee.mention, inline=True)
            if mentor_2:
                embed.add_field(name="Mentor", value=mentor.mention, inline=True)
                embed.add_field(name="Co-Mentor", value=mentor_2.mention, inline=True)
                embed.add_field(name="\u200b", value="\u200b", inline=True)
            else:
                embed.add_field(name="Mentor", value=mentor.mention, inline=True)
            embed.set_footer(text="Fork @ The Peer Project")

            ping_mentions = f"{mentee.mention} {mentor.mention}"
            if mentor_2:
                ping_mentions += f" {mentor_2.mention}"
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
                await interaction.followup.send("This channel is not an active mentoring session. Please specify a session ID or channel.")
                return

        mentee_id = session_data["mentee_id"]
        mentor_id = session_data["mentor_id"]
        mentor_2_id = session_data.get("mentor_2_id")
        chan_id = session_data["channel_id"]

        mentee = guild.get_member(mentee_id)
        mentor = guild.get_member(mentor_id)
        mentor_2 = guild.get_member(mentor_2_id) if mentor_2_id else None
        session_chan = guild.get_channel(chan_id)

        mentee_str = mentee.mention if mentee else f"left server (id: {mentee_id})"
        mentor_str = mentor.mention if mentor else f"left server (id: {mentor_id})"
        
        mentor_2_str = None
        if mentor_2_id:
            mentor_2_str = mentor_2.mention if mentor_2 else f"left server (id: {mentor_2_id})"

        chan_str = session_chan.mention if session_chan else f"#deleted-channel (id: {chan_id})"

        status_text = "active" if session_data["status"] == "active" else "nuked"
        
        embed = discord.Embed(
            title=f"session info: {session_data['session_id']}",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="session-ID", value=f"`{session_data['session_id']}`", inline=True)
        embed.add_field(name="status", value=status_text, inline=True)
        embed.add_field(name="channel", value=chan_str, inline=False)
        embed.add_field(name="mentee", value=mentee_str, inline=True)
        embed.add_field(name="mentor", value=mentor_str, inline=True)
        if mentor_2_str:
            embed.add_field(name="co-mentor", value=mentor_2_str, inline=True)
        embed.add_field(name="created at", value=str(session_data["created_at"]).lower(), inline=False)
        embed.set_footer(text="Fork @ The Peer Project")

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
            await interaction.followup.send("You do not have permission to nuke sessions. Only TPP admins can do this.", ephemeral=True)
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
                await interaction.followup.send("This channel is not an active mentoring session. Please specify a session ID or channel.", ephemeral=True)
                return

        database.nuke_session(session_data["session_id"])
        target_channel = guild.get_channel(session_data["channel_id"])
        
        if target_channel:
            try:
                if target_channel.id == interaction.channel_id:
                    await interaction.followup.send("nuking `{session_data['session_id']}` (channel: {target_channel.name})", ephemeral=True)
                    await target_channel.delete(reason=f"Session {session_data['session_id']} nuked by {interaction.user}")
                else:
                    await target_channel.delete(reason=f"Session {session_data['session_id']} nuked by {interaction.user}")
                    await interaction.followup.send(f"session `{session_data['session_id']}` (channel: `#{target_channel.name}`) has been nuked.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"marked as nuked in DB, but failed to delete channel: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"session `{session_data['session_id']}` marked as nuked in DB (channel was already deleted).", ephemeral=True)

    @session_group.command(name="archive", description="archives the session by making it read-only and optionally moving it to a category")
    @app_commands.describe(
        session_id="Optional: Search by Session ID to archive",
        channel="Optional: Search by channel to archive",
        category="Optional: Category to move the archived channel to"
    )
    async def archive(
        self,
        interaction: discord.Interaction,
        session_id: int = None,
        channel: discord.TextChannel = None,
        category: discord.CategoryChannel = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("You do not have permission to archive sessions. Only TPP admins can do this.", ephemeral=True)
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
                await interaction.followup.send("This channel is not an active mentoring session. Please specify a session ID or channel.", ephemeral=True)
                return

        database.archive_session(session_data["session_id"])
        target_channel = guild.get_channel(session_data["channel_id"])

        if target_channel:
            try:
                mentee = guild.get_member(session_data["mentee_id"])
                mentor = guild.get_member(session_data["mentor_id"])
                mentor_2 = guild.get_member(session_data["mentor_2_id"]) if session_data.get("mentor_2_id") else None

                if mentee:
                    await target_channel.set_permissions(mentee, read_messages=True, send_messages=False, read_message_history=True)
                if mentor:
                    await target_channel.set_permissions(mentor, read_messages=True, send_messages=False, read_message_history=True)
                if mentor_2:
                    await target_channel.set_permissions(mentor_2, read_messages=True, send_messages=False, read_message_history=True)

                old_name = target_channel.name
                new_name = f"archived-{session_data['session_id']}"
                
                edit_kwargs = {"name": new_name}
                if category:
                    edit_kwargs["category"] = category

                await target_channel.edit(**edit_kwargs)

                embed = discord.Embed(
                    title="Session Archived",
                    description="This mentoring session has been archived and is now read-only.",
                    color=discord.Color.from_rgb(180, 180, 180),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.set_footer(text="Fork @ The Peer Project")
                await target_channel.send(embed=embed)

                await interaction.followup.send(f"session `{session_data['session_id']}` (channel: `#{old_name}`) has been archived as `#{new_name}`.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"marked as archived in DB, but failed to update channel: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"session `{session_data['session_id']}` marked as archived in DB (channel was already deleted).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SessionCog(bot))
