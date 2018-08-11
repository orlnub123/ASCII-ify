from discord.ext import commands


class Command(commands.Converter):

    def __init__(self, group=False):
        self.group = group

    async def convert(self, ctx, argument):
        command = ctx.bot.get_command(argument)
        if command is None:
            raise commands.BadArgument
        if self.group and not isinstance(command, commands.Group):
            raise commands.BadArgument

        return command
