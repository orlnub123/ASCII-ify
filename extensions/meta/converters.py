from discord.ext import commands


class Prefix(commands.Converter):

    async def convert(self, ctx, prefix):
        if not prefix:
            raise commands.BadArgument
        if len(prefix) > 5:
            raise commands.CheckFailure

        return prefix
