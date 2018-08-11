import asyncio
import collections
import functools
import inspect
import warnings

from discord.ext import commands

from .utils import _is_method


# Can't be a check as ctx.args gets populated later
def required_varargs(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if _is_method(func, args, command=True):
            ctx = args[1]
            clean_args = args[2:]
        else:
            ctx = args[0]
            clean_args = args[1:]
        for i, param in enumerate(ctx.command.clean_params.values()):
            if param.kind == param.VAR_POSITIONAL:
                if len(clean_args) <= i:
                    raise commands.MissingRequiredArgument(param)
                break
        await func(*args, **kwargs)
    return wrapper


def cache(*, ignore=None, on=None, unbind=True, typed=False, **kwargs):
    def decorator(func):
        func_args = ()
        func_kwargs = {}
        versions = collections.defaultdict(int)
        make_key = functools.partial(functools._make_key, typed=typed)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal func_args, func_kwargs
            func_args = args
            func_kwargs = kwargs

            signature = inspect.signature(func)
            bound = signature.bind(*args, **kwargs)
            sentinel = object()
            if unbind and _is_method(func, args):
                instance = next(iter(bound.arguments))
                bound.arguments[instance] = sentinel
            for name in signature.parameters:
                if on is not None and name in on:
                    locals = {name: bound.arguments[name]}
                    bound.arguments[name] = eval(name + on[name], locals)
                if ignore is not None and name in ignore:
                    bound.arguments[name] = sentinel
            args = tuple(arg for arg in bound.args if arg is not sentinel)
            kwargs = {name: value for name, value in bound.kwargs.items()
                      if value is not sentinel}

            version = versions[make_key(args, kwargs)]
            return cache(*args, _version=version, **kwargs)

        @functools.lru_cache(typed=typed, **kwargs)
        def cache(*_args, _version, **_kwargs):
            result = func(*func_args, **func_kwargs)
            if asyncio.iscoroutinefunction(func):
                result = asyncio.get_event_loop().create_task(result)
            return result

        def cache_clear():
            cache.cache_clear()
            versions.clear()

        def invalidate(*args, **kwargs):
            key = make_key(args, kwargs)
            if key not in versions:
                warning = "Attempting to invalidate an uncreated key"
                warnings.warn(warning, RuntimeWarning)
            versions[key] += 1

        wrapper.cache_info = cache.cache_info
        wrapper.cache_clear = cache_clear
        wrapper.invalidate = invalidate
        return wrapper
    return decorator


def acquire(*, command=False, pool=None, **kwargs):
    def decorator(func):
        assert asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*func_args, **func_kwargs):
            nonlocal pool
            if pool is None:
                # Might also be ctx or possibly bot
                instance = func_args[0]
                try:
                    pool = instance.pool
                except AttributeError:
                    pool = instance.bot.pool

            async with pool.acquire(**kwargs) as connection:
                if command:
                    if _is_method(func, func_args, command=True):
                        ctx = func_args[1]
                    else:
                        ctx = func_args[0]
                    ctx.connection = connection
                else:
                    func_kwargs['connection'] = connection
                return await func(*func_args, **func_kwargs)

        return wrapper
    return decorator
