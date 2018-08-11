from discord.ext import commands

from utils import acquire


@commands.check
@acquire()
async def not_automated(ctx, connection):
    config = await ctx.cog.get_config(ctx.guild, connection=connection)
    return not config.automate
