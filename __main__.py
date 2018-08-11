import asyncio
import contextlib
import functools
import logging
import os
import sys
import time
import traceback
import types
import warnings

import asyncpg
import click
import uvloop
from ruamel import yaml

from bot import Bot


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def get_config():
    with open('config.yaml') as file:
        config = yaml.YAML().load(file)

    def convert(item):
        if isinstance(item, dict):
            for key, value in item.items():
                item[key] = convert(value)
            return types.SimpleNamespace(**item)
        return item

    return convert(config)


@contextlib.contextmanager
def setup_logging():
    logger_discord = logging.getLogger('discord')
    logger_discord.setLevel(logging.WARNING)

    logger_warnings = logging.getLogger('py.warnings')
    logger_warnings.setLevel(logging.WARNING)
    logging.captureWarnings(True)
    warnings.filterwarnings('always')

    handler = logging.FileHandler(filename='discord.log', encoding='utf-8')
    formatter = logging.Formatter(
        '[{asctime}] [{levelname}] {name}: {message}', style='{')
    formatter.datefmt = '%Y-%m-%d %H:%M:%S'
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)

    logger_discord.addHandler(handler)
    logger_warnings.addHandler(handler)

    yield

    logging.shutdown()


@click.group(invoke_without_command=True)
@click.pass_context
@setup_logging()
def main(ctx):
    if ctx.invoked_subcommand is not None:
        return

    config = get_config()
    bot = Bot(config=config)

    for extension in config.extensions:
        try:
            bot.load_extension(f'extensions.{extension}')
        except Exception:
            with contextlib.redirect_stdout(sys.stderr):
                print(f'Failed to load extension {extension}.')
                # Try to only show the traceback starting from the extension
                tb = sys.exc_info()[2]
                frames = traceback.extract_tb(tb)
                for i, frame in enumerate(frames):
                    filename = os.path.normpath(frame.filename)
                    ext_path = os.path.join('extensions', extension)
                    if filename.startswith(ext_path):
                        traceback.print_exc(limit=i - len(frames))
                        break
                else:
                    traceback.print_exc()
                print()

    bot.run(config.settings.token)


@main.group()
@click.pass_context
def db(ctx):
    config = get_config()
    loop = asyncio.get_event_loop()
    connection = loop.run_until_complete(asyncpg.connect(config.settings.dsn))
    ctx.obj = types.SimpleNamespace(loop=loop, connection=connection)
    ctx.call_on_close(functools.partial(
        loop.run_until_complete, connection.close()))


async def execute_file(path, *, connection):
    with open(path) as file:
        query = file.read()
    await connection.execute(query)


async def execute_extensions(extensions, *, all=False, file, connection):
    if all:
        extensions = [extension for extension in os.listdir('extensions')
                      if os.path.exists(os.path.join(
                          'extensions', extension, 'sql', file))]
    async with connection.transaction():
        for extension in extensions:
            path = os.path.join('extensions', extension, 'sql', file)
            await execute_file(path, connection=connection)


@db.command()
@click.argument('extensions', nargs=-1)
@click.option('--all', is_flag=True)
@click.pass_obj
def create(obj, *args, **kwargs):
    obj.loop.run_until_complete(execute_extensions(
        *args, **kwargs, file='create.sql', connection=obj.connection))


@db.command()
@click.argument('extensions', nargs=-1)
@click.option('--all', is_flag=True)
@click.confirmation_option()
@click.pass_obj
def drop(obj, *args, **kwargs):
    obj.loop.run_until_complete(execute_extensions(
        *args, **kwargs, file='drop.sql', connection=obj.connection))


@db.command()
@click.argument('extension')
@click.pass_obj
def migrate(obj, extension):
    path = os.path.join('extensions', extension, 'sql', 'migrations')
    migrations = os.listdir(path)
    migration = sorted(migrations, reverse=True)[0]
    click.confirm(f"Is {migration} the right migration?", abort=True, err=True)
    obj.loop.run_until_complete(execute_file(
        migration, connection=obj.connection))


if __name__ == '__main__':
    main()
