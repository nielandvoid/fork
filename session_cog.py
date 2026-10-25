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
                description="Welcome to your mentoring session! This channel is only visible to the mentee, mentor(s), and TPP admins.",
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

        status_text = session_data["status"]
        
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

    @session_group.command(name="conclude", description="ends a session: removes mentor access, mentee keeps the channel")
    @app_commands.describe(
        session_id="Optional: Search by Session ID to conclude",
        channel="Optional: Search by channel to conclude",
        category="Optional: Category to move the concluded channel to",
        mentee_read_only="Optional: also stop the mentee from sending messages (default: mentee keeps full access)"
    )
    async def conclude(
        self,
        interaction: discord.Interaction,
        session_id: int = None,
        channel: discord.TextChannel = None,
        category: discord.CategoryChannel = None,
        mentee_read_only: bool = False
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("You do not have permission to conclude sessions. Only TPP admins can do this.", ephemeral=True)
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

        if session_data["status"] == "nuked":
            await interaction.followup.send(f"session `{session_data['session_id']}` was nuked, so there is nothing to conclude.", ephemeral=True)
            return
        if session_data["status"] == "concluded":
            await interaction.followup.send(f"session `{session_data['session_id']}` is already concluded.", ephemeral=True)
            return

        database.conclude_session(session_data["session_id"])
        target_channel = guild.get_channel(session_data["channel_id"])

        if not target_channel:
            await interaction.followup.send(f"session `{session_data['session_id']}` marked as concluded in DB (channel was already deleted).", ephemeral=True)
            return

        try:
            mentor_ids = {session_data["mentor_id"]}
            if session_data.get("mentor_2_id"):
                mentor_ids.add(session_data["mentor_2_id"])

            overwrites = {
                target: overwrite
                for target, overwrite in target_channel.overwrites.items()
                if getattr(target, "id", None) not in mentor_ids
            }

            mentee = guild.get_member(session_data["mentee_id"])
            if mentee:
                overwrites[mentee] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False if mentee_read_only else True,
                    read_message_history=True
                )

            edit_kwargs = {"overwrites": overwrites}
            if category:
                edit_kwargs["category"] = category
            await target_channel.edit(**edit_kwargs)

            embed = discord.Embed(
                title="Session Concluded",
                description="This mentoring session has ended. Mentors no longer have access to this channel.",
                color=discord.Color.from_rgb(180, 180, 180),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text="Fork @ The Peer Project")
            await target_channel.send(embed=embed)

            await interaction.followup.send(
                f"session `{session_data['session_id']}` (channel: {target_channel.mention}) has been concluded. mentor access removed; the mentee keeps access.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"marked as concluded in DB, but failed to update channel: {str(e)}", ephemeral=True)

    @session_group.command(name="reopen", description="reverts a conclusion: gives the mentors their access back and marks the session active")
    @app_commands.describe(
        session_id="Optional: Search by Session ID to reopen",
        channel="Optional: Search by channel to reopen",
        category="Optional: Category to move the reopened channel to"
    )
    async def reopen(
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
            await interaction.followup.send("You do not have permission to reopen sessions. Only TPP admins can do this.", ephemeral=True)
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
                await interaction.followup.send("This channel is not a mentoring session. Please specify a session ID or channel.", ephemeral=True)
                return

        if session_data["status"] != "concluded":
            await interaction.followup.send(
                f"session `{session_data['session_id']}` is `{session_data['status']}`, not concluded, so there is nothing to reopen.",
                ephemeral=True
            )
            return

        target_channel = guild.get_channel(session_data["channel_id"])
        if not target_channel:
            await interaction.followup.send(f"session `{session_data['session_id']}` is concluded, but its channel no longer exists. use `/session recreate` instead.", ephemeral=True)
            return

        try:
            mentee = guild.get_member(session_data["mentee_id"])
            mentor = guild.get_member(session_data["mentor_id"])
            mentor_2 = guild.get_member(session_data["mentor_2_id"]) if session_data.get("mentor_2_id") else None

            full_access = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
            overwrites = dict(target_channel.overwrites)
            restored = []
            for member in (mentee, mentor, mentor_2):
                if member:
                    overwrites[member] = full_access
            for member in (mentor, mentor_2):
                if member:
                    restored.append(member)

            edit_kwargs = {"overwrites": overwrites}
            if category:
                edit_kwargs["category"] = category
            await target_channel.edit(**edit_kwargs)

            database.reopen_session(session_data["session_id"])

            embed = discord.Embed(
                title="Session Reopened",
                description="This mentoring session has been reopened. Mentors have access to this channel again.",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text="Fork @ The Peer Project")
            await target_channel.send(content=" ".join(m.mention for m in restored) or None, embed=embed)

            missing = []
            if not mentor:
                missing.append(f"mentor (id: {session_data['mentor_id']})")
            if session_data.get("mentor_2_id") and not mentor_2:
                missing.append(f"co-mentor (id: {session_data['mentor_2_id']})")
            msg = f"session `{session_data['session_id']}` (channel: {target_channel.mention}) has been reopened."
            if missing:
                msg += f" could not restore access for {', '.join(missing)}: no longer in the server."
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed to reopen session: {str(e)}", ephemeral=True)

    @session_group.command(name="reconstruct", description="reconstructs an archived / existing session in the current channel")
    @app_commands.describe(
        session_id="The ID of the session to reconstruct",
        mentee="The mentee for this session",
        mentor="The primary mentor for this session",
        mentor_2="Optional: The secondary mentor for this session"
    )
    async def reconstruct(
        self,
        interaction: discord.Interaction,
        session_id: int,
        mentee: discord.Member,
        mentor: discord.Member,
        mentor_2: discord.Member = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("You do not have permission to reconstruct sessions. Only TPP admins can do this.", ephemeral=True)
            return

        try:
            database.reconstruct_session(
                session_id=session_id,
                channel_id=interaction.channel_id,
                mentee_id=mentee.id,
                mentor_id=mentor.id,
                mentor_2_id=mentor_2.id if mentor_2 else None
            )

          
            channel = interaction.channel
            topic = f"Mentoring session between Mentee {mentee.display_name} and Mentor {mentor.display_name}."
            if mentor_2:
                topic = f"Mentoring session between Mentee {mentee.display_name} and Co-Mentors {mentor.display_name} & {mentor_2.display_name}."

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

            await channel.edit(name=f"session-{session_id}", topic=topic, overwrites=overwrites)

            embed = discord.Embed(
                title="Session Reconstructed!",
                description="This mentoring session has been successfully reconstructed in this channel. Welcome back!",
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
            await interaction.followup.send(f"session `{session_id}` has been successfully reconstructed.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"failed to reconstruct session: {str(e)}", ephemeral=True)

    @session_group.command(name="recreate", description="recreates an archived / existing session with a brand new channel")
    @app_commands.describe(
        session_id="The ID of the session to recreate",
        category="The category to create the new channel in",
        mentee="Optional: Change the mentee for this session",
        mentor="Optional: Change the primary mentor for this session",
        mentor_2="Optional: Change the secondary mentor for this session",
        clear_co_mentor="Optional: Set True to remove the co-mentor completely"
    )
    async def recreate(
        self,
        interaction: discord.Interaction,
        session_id: int,
        category: discord.CategoryChannel,
        mentee: discord.Member = None,
        mentor: discord.Member = None,
        mentor_2: discord.Member = None,
        clear_co_mentor: bool = False
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("you do not have permission to recreate sessions.", ephemeral=True)
            return

        session_data = database.get_session_by_id(session_id)
        if not session_data:
            await interaction.followup.send(f"no session found with ID `{session_id}`.", ephemeral=True)
            return

        final_mentee = mentee or guild.get_member(session_data["mentee_id"])
        final_mentor = mentor or guild.get_member(session_data["mentor_id"])
        
        final_mentor_2 = None
        if not clear_co_mentor:
            final_mentor_2 = mentor_2 or (guild.get_member(session_data["mentor_2_id"]) if session_data.get("mentor_2_id") else None)

        if not final_mentee or not final_mentor:
            await interaction.followup.send("could not find the mentee or mentor in the server.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            final_mentee: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            final_mentor: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        if final_mentor_2:
            overwrites[final_mentor_2] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        try:
            topic = f"Mentoring session between Mentee {final_mentee.display_name} and Mentor {final_mentor.display_name}."
            if final_mentor_2:
                topic = f"Mentoring session between Mentee {final_mentee.display_name} and Co-Mentors {final_mentor.display_name} & {final_mentor_2.display_name}."

            channel = await guild.create_text_channel(
                name=f"session-{session_id}",
                category=category,
                overwrites=overwrites,
                topic=topic
            )

            database.reconstruct_session(
                session_id=session_id,
                channel_id=channel.id,
                mentee_id=final_mentee.id,
                mentor_id=final_mentor.id,
                mentor_2_id=final_mentor_2.id if final_mentor_2 else None
            )

            embed = discord.Embed(
                title="Session Recreated!",
                description="This mentoring session has been successfully recreated. Welcome back!",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="Session-ID", value=f"`{session_id}`", inline=True)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Mentee", value=final_mentee.mention, inline=True)
            if final_mentor_2:
                embed.add_field(name="Mentor", value=final_mentor.mention, inline=True)
                embed.add_field(name="Co-Mentor", value=final_mentor_2.mention, inline=True)
                embed.add_field(name="\u200b", value="\u200b", inline=True)
            else:
                embed.add_field(name="Mentor", value=final_mentor.mention, inline=True)
            embed.set_footer(text="Fork @ The Peer Project")

            ping_mentions = f"{final_mentee.mention} {final_mentor.mention}"
            if final_mentor_2:
                ping_mentions += f" {final_mentor_2.mention}"
            if mod_role:
                ping_mentions += f" {mod_role.mention}"

            await channel.send(content=ping_mentions, embed=embed)
            await interaction.followup.send(f"session `{session_id}` successfully recreated in {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"failed to recreate session: {str(e)}", ephemeral=True)

    @session_group.command(name="transcribe", description="generates a beautiful HTML transcript of a session")
    @app_commands.describe(
        session_id="optional: search by session-ID to transcribe",
        channel="optional: search by channel to transcribe"
    )
    async def transcribe(
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
            await interaction.followup.send("you do not have permission to transcribe sessions.", ephemeral=True)
            return

        target_channel = None
        label = "channel"

        if channel is not None:
            target_channel = channel
            session_data = database.get_session_by_channel(channel.id)
            label = f"session `{session_data['session_id']}`" if session_data else f"`#{channel.name}`"
            filename_part = f"session-{session_data['session_id']}" if session_data else channel.name
        elif session_id is not None:
            session_data = database.get_session_by_id(session_id)
            if not session_data:
                await interaction.followup.send(f"no session found with ID `{session_id}`.", ephemeral=True)
                return
            target_channel = guild.get_channel(session_data["channel_id"])
            label = f"session `{session_data['session_id']}`"
            filename_part = f"session-{session_data['session_id']}"
        else:
            target_channel = interaction.channel
            session_data = database.get_session_by_channel(interaction.channel_id)
            label = f"session `{session_data['session_id']}`" if session_data else f"`#{interaction.channel.name}`"
            filename_part = f"session-{session_data['session_id']}" if session_data else interaction.channel.name

        if not target_channel:
            await interaction.followup.send("could not find the channel to transcribe.", ephemeral=True)
            return

        import chat_exporter
        import io

        transcript = await chat_exporter.export(target_channel, bot=self.bot)
        if transcript is None:
            await interaction.followup.send("failed to generate transcript.", ephemeral=True)
            return

        file = discord.File(
            io.BytesIO(transcript.encode("utf-8")),
            filename=f"transcript-{filename_part}.html"
        )
        await interaction.followup.send(
            content=f"transcript generated for {label}.",
            file=file,
            ephemeral=True
        )

    @session_group.command(name="transcribe_all", description="generates HTML transcripts of all sessions and exports them in a zip file")
    @app_commands.describe(
        status="optional: filter by session status (e.g. active, archived, concluded, or all)"
    )
    async def transcribe_all(
        self,
        interaction: discord.Interaction,
        status: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("this command can only be used within a server.", ephemeral=True)
            return

        mod_role = self._resolve_moderator_role(guild)
        if not self._is_moderator(interaction.user, mod_role):
            await interaction.followup.send("you do not have permission to transcribe sessions.", ephemeral=True)
            return

        filter_status = None
        if status and status.lower() in ["active", "archived", "concluded", "nuked"]:
            filter_status = status.lower()

        sessions = database.get_all_sessions(status=filter_status)
        if not sessions:
            await interaction.followup.send("no sessions found to transcribe.", ephemeral=True)
            return

        import chat_exporter
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        exported_count = 0
        failed_count = 0
        processed_channel_ids = set()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for s in sessions:
                sid = s["session_id"]
                cid = s["channel_id"]
                processed_channel_ids.add(cid)
                target_channel = guild.get_channel(cid)
                if not target_channel:
                    failed_count += 1
                    continue

                try:
                    transcript = await chat_exporter.export(target_channel, bot=self.bot)
                    if transcript:
                        zip_file.writestr(f"session-{sid}.html", transcript)
                        exported_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1

            for chan in guild.text_channels:
                if chan.id not in processed_channel_ids:
                    chan_name = chan.name.lower()
                    if chan_name.startswith("archived-") or chan_name.startswith("archive-") or ("session" in chan_name):
                        try:
                            transcript = await chat_exporter.export(chan, bot=self.bot)
                            if transcript:
                                zip_file.writestr(f"{chan.name}.html", transcript)
                                exported_count += 1
                                processed_channel_ids.add(chan.id)
                        except Exception:
                            pass

        if exported_count == 0:
            await interaction.followup.send(f"failed to export any transcripts ({failed_count} channels failed/missing).", ephemeral=True)
            return

        zip_buffer.seek(0)
        zip_discord_file = discord.File(
            zip_buffer,
            filename=f"tpp-transcripts-{datetime.date.today().isoformat()}.zip"
        )

        msg = f"successfully generated transcripts for **{exported_count}** sessions (including archived channels)."
        if failed_count > 0:
            msg += f" ({failed_count} channels were deleted or inaccessible)"

        await interaction.followup.send(
            content=msg,
            file=zip_discord_file,
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(SessionCog(bot))

