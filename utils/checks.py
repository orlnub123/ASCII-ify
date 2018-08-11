from discord.ext import commands


def confirm(*args, **kwargs):
    @commands.check
    async def check(ctx):
        if not await ctx.confirm(*args, **kwargs):
            raise commands.CheckFailure(ignore=True)
        return True
    return check


@commands.check
def ignore(ctx):
    ctx.ignore = True
    return True
