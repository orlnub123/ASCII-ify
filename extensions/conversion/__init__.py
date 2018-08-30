import io
import json
import os
import types

import discord
import pyfiglet
from discord.ext import commands
from PIL import Image

from utils import Emoji, acquire, cache, ignore, invoke

from .converters import ImageURL
from .utils import url_regex


class Conversion:

    def __init__(self, bot):
        self.bot = bot
        here = os.path.abspath(os.path.dirname(__file__))
        with open(os.path.join(here, 'consolas_data.json')) as file:
            chars = json.load(file)
            del chars['`']  # Don't bother dealing with backticks
        self.chars = chars

    @cache(maxsize=None, ignore=['connection'])
    async def get_config(self, guild, *, connection):
        record = await connection.fetchrow("""
            SELECT * FROM conversion.guilds WHERE id = $1;
        """, guild.id)
        return types.SimpleNamespace(**record)

    async def send(self, ctx, *args, **kwargs):
        if ctx.guild is not None:
            async with self.bot.pool.acquire() as connection:
                config = await self.get_config(ctx.guild,
                                               connection=connection)
            pm = config.pm
        else:
            pm = False

        if pm:
            await ctx.author.send(*args, **kwargs)
            try:
                await ctx.message.add_reaction(str(Emoji.white_check_mark))
            except discord.Forbidden:
                pass
        else:
            await ctx.send(*args, **kwargs)

    async def _add_guild(self, guild, *, connection):
        await connection.execute("""
            INSERT INTO conversion.guilds (id)
            VALUES ($1)
            ON CONFLICT DO NOTHING;
        """, guild.id)

    @acquire()
    async def on_ready(self, connection):
        for guild in self.bot.guilds:
            await self._add_guild(guild, connection=connection)

    @acquire()
    async def on_guild_join(self, guild, connection):
        await self._add_guild(guild, connection=connection)

    @commands.group(invoke_without_command=True)
    @ignore
    async def convert(self, ctx, *, argument=None):
        """Dynamically convert the message based on its composition."""
        if argument is None and not ctx.message.attachments:
            raise commands.BadArgument

        if argument is not None and not url_regex.fullmatch(argument):
            command = self.text
        else:
            command = self.art
        await invoke(command, ctx)

    @convert.command(name='last')
    @ignore
    async def convert_last(self, ctx):
        """Convert the last message."""
        try:
            message = await ctx.history(limit=1, before=ctx.message).next()
        except discord.NoMoreItems:
            raise commands.BadArgument

        embed = message.embeds[-1] if message.embeds else None
        attachment = message.attachments[-1] if message.attachments else None
        if embed is not None:
            if embed.type != 'image':
                raise commands.BadArgument
            await invoke(self.art, ctx, content=embed.url, embeds=[embed])
        elif attachment is not None:
            await invoke(self.art, ctx, content='', attachments=[attachment])
        else:
            await invoke(self.text, ctx, content=message.content)

    @convert.group(invoke_without_command=True)
    @commands.cooldown(4, 24, commands.BucketType.user)
    @ignore
    async def art(self, ctx, url: ImageURL(member=True, emoji=True) = None):
        """Convert an image into ASCII art."""
        attachments = ctx.message.attachments
        if url is None:
            if len(attachments) != 1 or attachments[0].height is None:
                raise commands.BadArgument
            url = attachments[0].proxy_url
        elif attachments:
            raise commands.TooManyArguments

        async with self.bot.session.head(url) as response:
            allowed_types = ['image/png', 'image/jpeg', 'image/webp']
            if response.headers['content-type'] not in allowed_types:
                raise commands.BadArgument

        async with self.bot.session.get(url) as response:
            data = await response.read()

        def convert():
            image = Image.open(io.BytesIO(data)).convert('L')

            max_length = 2000 - 6  # Offset backticks
            aspect = image.width / (image.height / 2)  # Negate stretching
            y = (max_length / aspect) ** 0.5
            x = y * aspect
            # Offset newlines
            while x * y + y - 1 > max_length:
                y -= 1
                x = y * aspect
            image = image.resize(map(int, [x, y]), Image.BILINEAR)

            output = []
            pixels = image.load()
            for y in range(image.height):
                row = []
                for x in range(image.width):
                    key = lambda char: abs(pixels[x, y] - self.chars[char])
                    char = sorted(self.chars, key=key)[0]
                    row.append(char)
                output.append(''.join(row))
            return '\n'.join(output)

        art = await self.bot.loop.run_in_executor(None, convert)
        await self.send(ctx, f'```{art}```')

    @art.command(name='last')
    @commands.cooldown(4, 24, commands.BucketType.user)
    @ignore
    async def art_last(self, ctx):
        """Convert the last message containing an image."""
        async for message in ctx.history(limit=25, before=ctx.message):
            for embed in message.embeds:
                if embed.type == 'image':
                    await invoke(self.art, ctx, content=embed.url,
                                 embeds=[embed])
                    return
            for attachment in message.attachments:
                if attachment.height is not None:
                    await invoke(self.art, ctx, content='',
                                 attachments=[attachment])
                    return
        else:
            raise commands.BadArgument

    @convert.group(invoke_without_command=True)
    @commands.cooldown(4, 24, commands.BucketType.user)
    @ignore
    async def text(self, ctx, *, text):
        """Convert text into ASCII text."""
        for font in ('big', 'standard', 'small'):
            render = pyfiglet.figlet_format(text, font=font)
            if len(render) <= 2000 - 6:
                break
        else:
            raise commands.CheckFailure
        if not render:
            raise commands.BadArgument
        await self.send(ctx, f'```{render}```')

    @text.command(name='last')
    @commands.cooldown(4, 24, commands.BucketType.user)
    @ignore
    async def text_last(self, ctx):
        """Convert the last message containing text."""
        async for message in ctx.history(limit=25, before=ctx.message):
            if message.content:
                await invoke(self.text, ctx, content=message.content)
                break
        else:
            raise commands.BadArgument

    @convert.command()
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def pm(self, ctx, toggle: bool):
        """Configure conversions to be sent via private message."""
        await self.bot.pool.execute("""
            UPDATE conversion.guilds
            SET pm = $1
            WHERE id = $2;
        """, toggle, ctx.guild.id)
        self.get_config.invalidate(ctx.guild)


def setup(bot):
    bot.add_cog(Conversion(bot))
