from discord.ext import commands

from .converters import Command


class Admin:

    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

    async def __local_check(self, ctx):
        return (await self.bot.is_owner(ctx.author) or
                ctx.author.id in self.bot.config.admins)

    @commands.command()
    async def load(self, ctx, extension):
        self.bot.load_extension(f'extensions.{extension}')

    @commands.command()
    async def unload(self, ctx, extension):
        self.bot.unload_extension(f'extensions.{extension}')

    @commands.command()
    async def reload(self, ctx, extension):
        self.bot.unload_extension(f'extensions.{extension}')
        self.bot.load_extension(f'extensions.{extension}')

    @commands.group(invoke_without_command=True)
    async def disable(self, ctx, *, command: Command):
        command.enabled = False

    @disable.command(name='recursive')
    async def disable_recursive(self, ctx, *, group: Command(group=True)):
        group.enabled = False
        for command in group.walk_commands():
            command.enabled = False

    @commands.group(invoke_without_command=True)
    async def enable(self, ctx, *, command: Command):
        command.enabled = True

    @enable.command(name='recursive')
    async def enable_recursive(self, ctx, *, group: Command(group=True)):
        group.enabled = True
        for command in group.walk_commands():
            command.enabled = True


def setup(bot):
    bot.add_cog(Admin(bot))
