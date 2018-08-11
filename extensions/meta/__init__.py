import inspect
import operator

import discord
from discord.ext import commands

from utils import Action, Emoji, acquire, get_color, ignore

from .converters import Prefix


class Meta:

    def __init__(self, bot):
        self.bot = bot
        self._old_help = bot.remove_command('help')

    # Prevent saved help command from getting added
    def __dir__(self):
        return (item for item in super().__dir__() if item != '_old_help')

    def __unload(self):
        self.bot.remove_command('help')
        self.bot.add_command(self._old_help)

    async def _add_guild(self, guild, *, connection):
        await connection.execute("""
            INSERT INTO meta.guilds (id) VALUES ($1)
            ON CONFLICT DO NOTHING;
        """, guild.id)

    @acquire()
    async def on_ready(self, connection):
        for guild in self.bot.guilds:
            await self._add_guild(guild, connection=connection)

    @acquire()
    async def on_guild_join(self, guild, connection):
        await self._add_guild(guild, connection=connection)

    @commands.command()
    @ignore
    async def help(self, ctx, command=None):
        """Show information about commands."""

        def get_commands(cog):
            # Preserve definition order
            for command in vars(type(cog)).values():
                if not isinstance(command, commands.Command) or command.hidden:
                    continue
                yield command

        async def handle_help():
            embeds = []
            cogs = sorted(self.bot.cogs.items(), key=operator.itemgetter(0))
            for name, cog in cogs:
                if getattr(cog, 'hidden', False):
                    continue
                embed = discord.Embed(title=name,
                                      description=inspect.getdoc(cog),
                                      color=color)
                for command in get_commands(cog):
                    embed.add_field(name=command.signature,
                                    value=command.short_doc, inline=False)
                embeds.append(embed)

            async def info(message):
                embed = discord.Embed(title='Information',
                                      description="What do these symbols "
                                                  "mean?",
                                      color=color)
                embed.add_field(name='<argument>', value="This means the "
                                "argument is __required__", inline=False)
                embed.add_field(name='[argument]', value="This means the "
                                "argument is __optional__", inline=False)
                embed.set_footer(text="(Don't type the brackets)")
                await message.edit(embed=embed)

            moves = {Emoji.information_source: (info, Action.SHOW)}
            await ctx.paginate(embeds, moves=moves, embed=True)

        async def handle_help_cog(cog):
            embed = discord.Embed(title=type(cog).__name__,
                                  description=inspect.getdoc(cog),
                                  color=color)
            for command in get_commands(cog):
                embed.add_field(name=command.signature,
                                value=command.short_doc, inline=False)
            await ctx.send(embed=embed)

        async def handle_help_command(command):
            embed = discord.Embed(title=command.signature,
                                  description=command.help, color=color)
            await ctx.send(embed=embed)

        color = get_color(ctx)

        if command is None:
            await handle_help()
            return

        cog = self.bot.get_cog(command)
        if cog is not None and not getattr(cog, 'hidden', False):
            await handle_help_cog(cog)
            return

        command = self.bot.get_command(command)
        if command is not None and not command.hidden:
            await handle_help_command(command)
            return

        raise commands.BadArgument

    @commands.group(invoke_without_command=True)
    @ignore
    async def prefix(self, ctx):
        """Show the current prefix."""
        if ctx.guild is not None:
            prefix = await ctx.pool.fetchval("""
                SELECT prefix FROM meta.guilds WHERE id = $1;
            """, ctx.guild.id)
        else:
            prefix = None

        embed = discord.Embed(title='Prefix', color=get_color(ctx))
        if prefix is not None:
            embed.description = prefix
            embed.set_footer(text='(Mention not included)')
        else:
            embed.description = ctx.me.mention
        await ctx.send(embed=embed)

    @prefix.command(name='set')
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def prefix_set(self, ctx, prefix: Prefix):
        """Set a custom prefix."""
        await ctx.pool.execute("""
            UPDATE meta.guilds SET prefix = $1 WHERE id = $2;
        """, prefix, ctx.guild.id)
        self.bot.command_prefix.invalidate(ctx.guild)

    @prefix.command(name='delete')
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def prefix_delete(self, ctx):
        """Delete the custom prefix."""
        await ctx.pool.execute("""
            UPDATE meta.guilds SET prefix = NULL WHERE id = $1;
        """, ctx.guild.id)
        self.bot.command_prefix.invalidate(ctx.guild)


def setup(bot):
    bot.add_cog(Meta(bot))
