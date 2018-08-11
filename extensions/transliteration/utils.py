import asyncio
import collections
import warnings

import discord


class MemberDefaultDict(collections.defaultdict):

    def __init__(self, *args, track=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.track = track

    def __getitem__(self, member):
        key = self._get_key(member)
        return super().__getitem__(key)

    def __setitem__(self, member, value):
        key = self._get_key(member)
        super().__setitem__(key, value)

        if self.track:
            loop = asyncio.get_event_loop()
            loop.create_task(self._track_item(key, value))

    def __delitem__(self, member):
        key = self._get_key(member)
        super().__delitem__(key)

    def __contains__(self, member):
        key = self._get_key(member)
        return super().__contains__(key)

    def _get_key(self, member):
        if isinstance(member, discord.Member):
            return (member.id, member.guild.id)
        else:
            return member

    async def _track_item(self, key, value):
        await asyncio.sleep(60)
        if key in self and value in self[key]:
            warnings.warn(f"Potential memory leak from value {value!r} in key "
                          f"{key!r}", ResourceWarning)
