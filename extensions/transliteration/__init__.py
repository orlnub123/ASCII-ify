import enum
import types

import asyncpg
import discord
from discord.ext import commands

from utils import acquire, cache, confirm

from .checks import not_automated
from .transliterator import is_unicode, transliterate
from .utils import MemberDefaultDict


class TransliterationType(enum.Enum):

    USERNAME = 'username'
    NICKNAME = 'nickname'


class Transliteration:

    def __init__(self, bot):
        self.bot = bot
        self._recent_edits = MemberDefaultDict(list, track=True)

    def __local_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage

        permissions = ctx.author.permissions_in(ctx.channel)
        if not permissions.manage_nicknames:
            raise commands.MissingPermissions(['manage_nicknames'])

        return True

    async def transliterate_member(self, member, *, reason=None, manual=False,
                                   connection):
        if not is_unicode(member.display_name):
            return

        if member.nick is not None:
            names = [member.nick, member.name]
        else:
            names = [member.name]
        for i, name in enumerate(names):
            transliteration = transliterate(name, check=i)
            if transliteration:
                break
        else:
            transliteration = '#' + member.discriminator

        if member.nick is not None:
            type = TransliterationType.NICKNAME
        else:
            type = TransliterationType.USERNAME
        await connection.execute("""
            INSERT INTO transliteration.transliterations (
                user_id, guild_id, type, original, manual
            )
            VALUES ($1, $2, $3, $4, $5);
        """, member.id, member.guild.id, type, member.display_name, manual)

        self._recent_edits[member].append(member.display_name)
        await member.edit(nick=transliteration[:32], reason=reason)

    async def revert_member(self, member, *, reason=None, connection):
        if member.nick is None or is_unicode(member.nick):
            return

        record = await connection.fetchrow("""
            SELECT type, original, created_at
            FROM transliteration.transliterations
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY created_at DESC LIMIT 1;
        """, member.id, member.guild.id)
        if record is None:
            return
        type, original, trans_date = record
        nick_date = await connection.fetchval("""
            SELECT created_at
            FROM transliteration.nicknames
            WHERE user_id = $1 AND guild_id = $2 AND ignore = FALSE
            ORDER BY created_at DESC LIMIT 1;
        """, member.id, member.guild.id)

        if nick_date is None or trans_date > nick_date:
            self._recent_edits[member].append(member.display_name)
            if type is TransliterationType.NICKNAME:
                await member.edit(nick=original, reason=reason)
            else:
                await member.edit(nick=None, reason=reason)

    @cache(maxsize=None, ignore=['connection'])
    async def get_config(self, guild, *, connection):
        record = await connection.fetchrow("""
            SELECT * FROM transliteration.guilds WHERE id = $1;
        """, guild.id)
        return types.SimpleNamespace(**record)

    async def _add_guild(self, guild, *, connection):
        await connection.execute("""
            INSERT INTO transliteration.guilds (id)
            VALUES ($1)
            ON CONFLICT DO NOTHING;
        """, guild.id)

    async def _add_member(self, member, *, connection):
        try:
            await connection.execute("""
                INSERT INTO transliteration.users (id)
                VALUES ($1);
            """, member.id)
        except asyncpg.UniqueViolationError:
            username = await connection.fetchval("""
                SELECT username
                FROM transliteration.usernames
                WHERE user_id = $1
                ORDER BY created_at DESC LIMIT 1;
            """, member.id)
            add_username = username is None or member.name != username
        else:
            add_username = True
        if add_username:
            await connection.execute("""
                INSERT INTO transliteration.usernames (user_id, username)
                VALUES ($1, $2);
            """, member.id, member.name)

        try:
            await connection.execute("""
                INSERT INTO transliteration.members (user_id, guild_id)
                VALUES ($1, $2);
            """, member.id, member.guild.id)
        except asyncpg.UniqueViolationError:
            if member.nick is not None:
                nickname = await connection.fetchval("""
                    SELECT nickname
                    FROM transliteration.nicknames
                    WHERE user_id = $1 AND guild_id = $2
                    ORDER BY created_at DESC LIMIT 1;
                """, member.id, member.guild.id)
                add_nickname = nickname is None or member.nick != nickname
            else:
                add_nickname = False
        else:
            add_nickname = member.nick is not None
        if add_nickname:
            await connection.execute("""
                INSERT INTO transliteration.nicknames (
                    user_id, guild_id, nickname
                )
                VALUES ($1, $2, $3);
            """, member.id, member.guild.id, member.nick)

    @acquire()
    async def on_ready(self, connection):
        for guild in self.bot.guilds:
            await self._add_guild(guild, connection=connection)
            config = await self.get_config(guild, connection=connection)
            for member in guild.members:
                await self._add_member(member, connection=connection)
                if config.automate:
                    reason = "Automatic transliteration"
                    await self.transliterate_member(
                        member, reason=reason, connection=connection)

    @acquire()
    async def on_guild_join(self, guild, connection):
        await self._add_guild(guild, connection=connection)
        for member in guild.members:
            await self._add_member(member, connection=connection)

    @acquire()
    async def on_member_join(self, member, connection):
        await self._add_member(member, connection=connection)
        config = await self.get_config(member.guild, connection=connection)
        if config.automate:
            reason = "Automatic transliteration on join"
            await self.transliterate_member(
                member, reason=reason, connection=connection)

    async def on_member_update(self, before, after):
        name_change = after.name != before.name
        nick_change = after.nick != before.nick
        if not (name_change or nick_change):
            return

        async with self.bot.pool.acquire() as connection:
            if name_change:
                await connection.execute("""
                    INSERT INTO transliteration.usernames (user_id, username)
                    VALUES ($1, $2);
                """, after.id, after.name)
            if nick_change and after.nick is not None:
                edits = self._recent_edits[before]
                try:
                    edits.remove(before.display_name)
                except ValueError:
                    ignore = False
                else:
                    ignore = True
                if not edits:
                    del self._recent_edits[before]
                await connection.execute("""
                    INSERT INTO transliteration.nicknames (
                        user_id, guild_id, nickname, ignore
                    )
                    VALUES ($1, $2, $3, $4);
                """, after.id, after.guild.id, after.nick, ignore)

            if after.display_name != before.display_name:
                config = await self.get_config(after.guild,
                                               connection=connection)
                if config.automate:
                    if nick_change:
                        if after.nick is not None:
                            change = "nickname change"
                        else:
                            change = "nickname remove"
                    else:
                        change = "username change"
                    reason = f"Automatic transliteration on {change}"
                    await self.transliterate_member(
                        after, reason=reason, connection=connection)

    @commands.group(invoke_without_command=True)
    @acquire(command=True)
    async def transliterate(self, ctx, member: discord.Member):
        """Transliterate a member's name."""
        reason = "Transliteration by {0} ({0.id})".format(ctx.author)
        await self.transliterate_member(
            member, reason=reason, manual=True, connection=ctx.connection)

    @transliterate.command(name='all')
    @commands.has_permissions(manage_guild=True)
    @confirm()
    @acquire(command=True)
    async def transliterate_all(self, ctx):
        """Transliterate all members' names."""
        for member in ctx.guild.members:
            reason = "Mass transliteration by {0} ({0.id})".format(ctx.author)
            await self.transliterate_member(
                member, reason=reason, manual=True, connection=ctx.connection)

    @commands.group(invoke_without_command=True)
    @not_automated
    @acquire(command=True)
    async def revert(self, ctx, member: discord.Member):
        """Revert the transliteration of a member's name."""
        reason = "Transliteration revert by {0} ({0.id})".format(ctx.author)
        await self.revert_member(
            member, reason=reason, connection=ctx.connection)

    @revert.command(name='all')
    @commands.has_permissions(manage_guild=True)
    @not_automated
    @confirm()
    @acquire(command=True)
    async def revert_all(self, ctx):
        """Revert the transliterations of all members' names."""
        for member in ctx.guild.members:
            reason = ("Mass transliteration revert by {0} ({0.id})"
                      .format(ctx.author))
            await self.revert_member(
                member, reason=reason, connection=ctx.connection)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def automate(self, ctx, toggle: bool):
        """Configure transliterations to be done automatically."""
        await ctx.pool.execute("""
            UPDATE transliteration.guilds
            SET automate = $1
            WHERE id = $2;
        """, toggle, ctx.guild.id)
        self.get_config.invalidate(ctx.guild)

        command = self.transliterate_all if toggle else self.revert_all
        if await ctx.confirm("Do you also want to", command=command):
            await ctx.invoke(command)


def setup(bot):
    bot.add_cog(Transliteration(bot))


async def init_connection(connection):
    import operator
    await connection.set_type_codec(
        'transliteration_type',
        encoder=operator.attrgetter('value'),
        decoder=TransliterationType)
