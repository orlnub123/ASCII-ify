import asyncio
import time

import discord
from discord.ext import commands

from utils import get_color, ignore


class Statistics:

    def __init__(self, bot):
        self.bot = bot
        self.stats_task = bot.loop.create_task(self.update_stats(delay=3600))
        self.latency_task = bot.loop.create_task(self.update_latency(delay=60))

    def __unload(self):
        self.stats_task.cancel()
        self.latency_task.cancel()

    async def update_stats(self, *, delay):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            url = f'https://discordbots.org/api/bots/{self.bot.user.id}/stats'
            headers = {'Authorization': self.bot.config.settings.dbl_token}
            data = {'server_count': len(self.bot.guilds)}
            await self.bot.session.post(url, headers=headers, data=data)
            await asyncio.sleep(delay)

    async def update_latency(self, *, delay):
        await self.bot.wait_until_connect()
        while not self.bot.is_closed():
            url = f'https://discordapp.com/api/v6/users/@me'
            headers = {'Authorization': f'Bot {self.bot.http.token}'}
            start_time = time.perf_counter()
            async with self.bot.session.get(url, headers=headers) as response:
                end_time = time.perf_counter()
                if response.status == 200:
                    await self.bot.pool.execute("""
                        INSERT INTO statistics.api_latencies (latency)
                        VALUES ($1);
                    """, end_time - start_time)
            await asyncio.sleep(delay)

    async def on_socket_response(self, response):
        if not self.bot.is_connected():
            return
        if response.get('op') == self.bot.ws.HEARTBEAT_ACK:
            await self.bot.pool.execute("""
                INSERT INTO statistics.gateway_latencies (latency)
                VALUES ($1);
            """, self.bot.latency)

    async def on_command(self, ctx):
        ctx.id_event = asyncio.Event()
        guild_id = ctx.guild.id if ctx.guild is not None else None
        command = ctx.command.qualified_name
        cog = type(ctx.cog).__name__ if ctx.cog is not None else None
        id = await self.bot.pool.fetchval("""
            INSERT INTO statistics.commands (
                user_id, channel_id, guild_id, command, cog
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id;
        """, ctx.author.id, ctx.channel.id, guild_id, command, cog)
        ctx.command_id = id
        ctx.id_event.set()

    async def on_command_completion(self, ctx):
        await ctx.id_event.wait()
        await self.bot.pool.execute("""
            UPDATE statistics.commands
            SET completed = TRUE
            WHERE id = $1;
        """, ctx.command_id)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        await ctx.id_event.wait()
        await self.bot.pool.execute("""
            INSERT INTO statistics.errors (command, type)
            VALUES ($1, $2);
        """, ctx.command_id, type(error).__name__)

    @commands.group(invoke_without_command=True)
    @ignore
    async def stats(self, ctx):
        """List bot-wide statistics."""
        records = await self.bot.pool.fetch("""
            SELECT command, count(*)
            FROM statistics.commands
            GROUP BY command
            ORDER BY count DESC;
        """)
        member_count = sum(guild.member_count for guild in self.bot.guilds)
        command_count = sum(record['count'] for record in records)
        embed = discord.Embed(title='Statistics', color=get_color(ctx))
        embed.add_field(name='General', value='\n'.join([
            f'Servers: **{len(self.bot.guilds)}**',
            f'Members: **{member_count}**',
            f'Commands Used: **{command_count}**']))
        embed.add_field(name='Top Commands', value='\n'.join(
            f"{i}. **{record['command']}** ({record['count']} uses)"
            for i, record in enumerate(records[:5], 1)))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Statistics(bot))
