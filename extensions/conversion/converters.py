import asyncio

from discord.ext import commands

from .utils import url_regex


class ImageURL(commands.Converter):

    def __init__(self, *, embed=True, member=False, emoji=False):
        if not (embed or member or emoji):
            raise TypeError

        self.check_embed = embed
        self.check_member = member
        self.check_emoji = emoji

    async def convert(self, ctx, argument):
        if self.check_embed and url_regex.fullmatch(argument) is not None:
            if ctx.message.embeds:
                embed = ctx.message.embeds[0]
            else:
                def check(_, message):
                    return message.id == ctx.message.id and message.embeds
                try:
                    _, message = await ctx.bot.wait_for(
                        'message_edit', timeout=2, check=check)
                except asyncio.TimeoutError:
                    raise commands.BadArgument

                embed = message.embeds[0]
            if embed.type != 'image':
                raise commands.CheckFailure

            return embed.thumbnail.proxy_url

        if self.check_member:
            converter = commands.MemberConverter()
            try:
                member = await converter.convert(ctx, argument)
            except commands.BadArgument:
                pass
            else:
                return member.avatar_url

        if self.check_emoji:
            converter = commands.PartialEmojiConverter()
            try:
                emoji = await converter.convert(ctx, argument)
            except commands.BadArgument:
                pass
            else:
                return emoji.url

        raise commands.BadArgument
