import io
import json
import os

import pyfiglet
from discord.ext import commands
from PIL import Image

from utils import invoke

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


    @commands.group(invoke_without_command=True)
    async def convert(self, ctx, *, argument=None):
        """Dynamically convert the message based on its composition."""
        if argument is None and not ctx.message.attachments:
            raise commands.BadArgument

        if argument is not None and not url_regex.fullmatch(argument):
            command = self.text
        else:
            command = self.art
        await invoke(command, ctx)

    @convert.command()
    @commands.cooldown(4, 24, commands.BucketType.user)
    async def art(self, ctx, url: ImageURL(member=True, emoji=True) = None):
        """Convert an image into ASCII art."""
        if url is None:
            attachments = ctx.message.attachments
            if len(attachments) != 1 or attachments[0].height is None:
                raise commands.BadArgument

            url = attachments[0].proxy_url
        elif ctx.message.attachments:
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
        await ctx.author.send(f'```{art}```')

    @convert.command()
    @commands.cooldown(4, 24, commands.BucketType.user)
    async def text(self, ctx, *, text):
        """Convert text into ASCII text."""
        for font in ('big', 'standard', 'small'):
            render = pyfiglet.figlet_format(text, font=font)
            if len(render) <= 2000 - 6:
                break
        else:
            raise commands.CheckFailure
        await ctx.author.send(f'```{render}```')


def setup(bot):
    bot.add_cog(Conversion(bot))
