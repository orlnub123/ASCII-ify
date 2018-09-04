import asyncio
import contextlib
import sys
import time

import aiohttp
import asyncpg
import discord
from discord.ext import commands

from utils import Context, Emoji, cache


@cache(maxsize=None, ignore=['bot'], on={'message': '.guild'})
async def command_prefix(bot, message):
    if message.guild is not None:
        prefix = await bot.pool.fetchval("""
            SELECT prefix FROM meta.guilds WHERE id = $1;
        """, message.guild.id)
    else:
        prefix = None

    if prefix is not None:
        return commands.when_mentioned_or(prefix)(bot, message)
    else:
        return commands.when_mentioned(bot, message)


class Bot(commands.Bot):

    def __init__(self, *, config, **kwargs):
        super().__init__(command_prefix=command_prefix,
                         status=discord.Status.invisible, **kwargs)
        self.connect_event = asyncio.Event()
        self.ready_event = asyncio.Event()
        self.config = config
        self.pool = self.loop.run_until_complete(
            asyncpg.create_pool(config.settings.dsn, init=self.init_connection,
                                setup=self.setup_connection))
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.cooldowns = []
        self.loop.create_task(self.display())

    async def display(self):
        await self.wait_until_ready()
        with contextlib.redirect_stdout(sys.stderr):
            print("Ready: {0} ({0.id})".format(self.user))
            if not self.config.admins:
                return

            print("Admins:")
            for id in self.config.admins:
                admin = self.get_user(id) or await self.get_user_info(id)
                print(" - {0} ({0.id})".format(admin))

    async def init_connection(self, connection):
        inits = [extension.init_connection(self, connection)
                 for extension in self.extensions.values()
                 if hasattr(extension, 'init_connection')]
        await asyncio.gather(*inits)

    async def setup_connection(self, connection):
        setups = [extension.setup_connection(self, connection)
                  for extension in self.extensions.values()
                  if hasattr(extension, 'setup_connection')]
        await asyncio.gather(*setups)

    def load_extension(self, name):
        super().load_extension(name)
        extension = self.extensions[name]
        if hasattr(extension, 'init_connection'):
            self.loop.create_task(self.pool.expire_connections())

    def is_connected(self):
        return self.connect_event.is_set()

    async def wait_until_connect(self):
        await self.connect_event.wait()

    async def close(self):
        if self.is_closed():
            return

        self.connect_event.clear()
        self.ready_event.clear()
        await self.session.close()
        await super().close()

    async def on_connect(self):
        self.connect_event.set()
        self.ready_event.clear()

    async def on_ready(self):
        self.ready_event.set()
        await self.change_presence(status=discord.Status.online,
                                   activity=discord.Game("with characters"))

    async def on_error(self, *args, **kwargs):
        error = sys.exc_info()[1]
        if not isinstance(error, discord.Forbidden):
            await super().on_error(*args, **kwargs)

    async def on_command_completion(self, ctx):
        if not getattr(ctx, 'ignore', False):
            await ctx.message.add_reaction(str(Emoji.white_check_mark))

    async def on_command_error(self, ctx, error):
        ignored = (commands.CommandNotFound, commands.DisabledCommand)
        if getattr(error, 'ignore', False) or isinstance(error, ignored):
            return

        if isinstance(error, commands.UserInputError):
            await ctx.message.add_reaction(str(Emoji.question))
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.command in self.cooldowns:
                return
            self.cooldowns.append(ctx.command)

            await ctx.message.add_reaction(str(Emoji.no_entry))
            remaining = error.retry_after
            interval = remaining / 12
            start_time = time.time()
            while remaining > 0:
                # Start at 12 instead of 1
                number = 12 - int(remaining / interval) or 12
                clock = Emoji['clock' + str(number)]
                await ctx.message.add_reaction(str(clock))
                delay = min(max(interval, 2), remaining)
                await asyncio.sleep(delay)
                await ctx.message.remove_reaction(str(clock), ctx.me)
                remaining = error.retry_after - (time.time() - start_time)
            await ctx.message.add_reaction(str(Emoji.repeat))
            await ctx.message.remove_reaction(str(Emoji.no_entry), ctx.me)
            self.cooldowns.remove(ctx.command)
        elif (isinstance(error, commands.CheckFailure) or (
              isinstance(error, commands.CommandInvokeError) and
              isinstance(error.original, discord.Forbidden))):
            await ctx.message.add_reaction(str(Emoji.no_entry_sign))
        else:
            await ctx.message.add_reaction(str(Emoji.bangbang))
            await super().on_command_error(ctx, error)

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def on_message(self, message):
        if message.author.bot or not self.ready_event.is_set():
            return

        await self.process_commands(message)
