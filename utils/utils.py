import copy
import types

import discord
from discord.ext import commands


def _is_method(func, args, *, command=False):
    if not args:
        return False

    method = getattr(args[0], func.__name__, None)
    if method is None:
        return False

    if command:
        return method.instance is not None
    else:
        return isinstance(method, types.MethodType)


async def invoke(command, ctx):
    if isinstance(command, commands.Command):
        command = command.qualified_name

    message = copy.copy(ctx.message)
    view = commands.view.StringView(message.content)
    view.skip_string(ctx.prefix)
    word = None
    while word != ctx.invoked_with:
        if view.eof:
            raise RuntimeError
        word = view.get_word()
    message.content = ctx.prefix + command + view.read_rest()

    ctx = await ctx.bot.get_context(message)
    if await ctx.bot.can_run(ctx, call_once=True):
        await ctx.command.invoke(ctx)


def get_color(ctx):
    if ctx.guild is not None and ctx.me.color.value:
        return ctx.me.color
    else:
        return discord.Color.blurple()
