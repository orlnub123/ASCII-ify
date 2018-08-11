import asyncio
import enum

from discord.ext import commands

from .emoji import Emoji


class Action(enum.Enum):

    MOVE = enum.auto()
    SHOW = enum.auto()


class Context(commands.Context):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = self.bot.pool

    async def confirm(self, question=None, *, command=None):
        question = "Are you sure you want to" if question is None else question
        command = self.command if command is None else command
        short_doc = command.short_doc[0].lower() + command.short_doc[1:-1]
        message = await self.send(f"{question} {short_doc}?")

        emojis = list(map(str, [Emoji.white_check_mark, Emoji.x]))
        for emoji in emojis:
            await message.add_reaction(emoji)

        def check(reaction, user):
            return (reaction.message.id == message.id and
                    user == self.author and reaction.emoji in emojis)
        try:
            reaction, _ = await self.bot.wait_for(
                'reaction_add', timeout=30, check=check)
        except asyncio.TimeoutError:
            return False
        else:
            return Emoji(reaction.emoji) is Emoji.white_check_mark
        finally:
            await message.delete()

    async def paginate(self, items, *, moves={}, embed=False):
        if embed:
            if len(items) > 1:
                for i, item in enumerate(items):
                    item.set_author(name=f'Page {i + 1}/{len(items)}')
            message = await self.send(embed=items[0])
        else:
            message = await self.send(items[0])

        if len(items) > 2:
            moves = {
                Emoji.track_previous: (lambda page: 0, Action.MOVE),
                Emoji.arrow_backward: (lambda page: page - 1, Action.MOVE),
                Emoji.arrow_forward: (lambda page: page + 1, Action.MOVE),
                Emoji.track_next: (lambda page: len(items) - 1, Action.MOVE),
                **moves
            }
        elif len(items) > 1:
            moves = {
                Emoji.arrow_backward: (lambda page: page - 1, Action.MOVE),
                Emoji.arrow_forward: (lambda page: page + 1, Action.MOVE),
                **moves
            }

        async def add_moves():
            for emoji in map(str, moves):
                await message.add_reaction(emoji)
        self.bot.loop.create_task(add_moves())

        async def handle(reaction):
            nonlocal page

            async def move(page):
                if embed:
                    await message.edit(embed=items[page])
                else:
                    await message.edit(items[page])

            func, action = moves[Emoji(reaction.emoji)]
            if action is Action.MOVE:
                page = min(max(func(page), 0), len(items) - 1)
                await move(page)
                await message.remove_reaction(reaction, self.author)
            elif action is Action.SHOW:
                self.bot.loop.create_task(func(message))

                async def remove():
                    def check_(reaction_, user):
                        return (check(reaction_, user) and
                                reaction_.emoji == reaction.emoji)
                    await self.bot.wait_for('reaction_remove', check=check_)
                    await move(page)

                async def add():
                    await self.bot.wait_for('reaction_add', check=check)
                    await message.remove_reaction(reaction, self.author)

                _, pending = await asyncio.wait(
                    [remove(), add()], timeout=60,
                    return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()

        page = 0
        while True:
            def check(reaction, user):
                return (reaction.message.id == message.id and
                        user == self.author and Emoji(reaction.emoji) in moves)
            try:
                reaction, _ = await self.bot.wait_for(
                    'reaction_add', timeout=60, check=check)
            except asyncio.TimeoutError:
                await message.clear_reactions()
                break
            else:
                self.bot.loop.create_task(handle(reaction))
