import enum
import types

from .utils import _get_emoji_data


class Modifier(enum.Enum):

    light = '\N{EMOJI MODIFIER FITZPATRICK TYPE-1-2}'
    medium_light = '\N{EMOJI MODIFIER FITZPATRICK TYPE-3}'
    medium = '\N{EMOJI MODIFIER FITZPATRICK TYPE-4}'
    medium_dark = '\N{EMOJI MODIFIER FITZPATRICK TYPE-5}'
    dark = '\N{EMOJI MODIFIER FITZPATRICK TYPE-6}'


class Category(enum.Enum):

    People = 'people'
    Nature = 'nature'
    Food = 'food'
    Activities = 'activity'
    Travel = 'travel'
    Objects = 'objects'
    Symbols = 'symbols'
    Flags = 'flags'


class _EmojiMeta(enum.EnumMeta):

    # Can't do this in Emoji.__new__ as the name gets set after it
    def __new__(meta, name, bases, namespace):
        emoji_class = super().__new__(meta, name, bases, namespace)
        for emoji in emoji_class:
            if not emoji.diverse:
                continue
            for modifier in Modifier:
                value = emoji.value + modifier.value
                modified_emoji = emoji_class.__new_member__(
                    emoji_class, emoji.category, value, True)
                modified_emoji._name_ = emoji._name_
                modified_emoji._modifier_ = modifier
                setattr(emoji, modifier.name, modified_emoji)
                # Support value get while supporting compatibility with < 3.6
                emoji_class._value2member_map_[value] = modified_emoji
        return emoji_class


class Emoji(enum.Enum, metaclass=_EmojiMeta):

    def __new__(cls, category, value, diverse):
        emoji = object.__new__(cls)
        emoji.category = Category(category) if category is not None else None
        emoji._value_ = value
        emoji.diverse = diverse
        return emoji

    def __str__(self):
        return self.value

    @types.DynamicClassAttribute
    def modifier(self):
        if self.diverse:
            return getattr(self, '_modifier_', None)
        return None


def _get_all_emoji_data():
    yield from _get_emoji_data()
    # Data doesn't include skin tones
    for i, modifier in enumerate(Modifier, 1):
        name = 'skin-tone-{}'.format(i)
        yield (name, (None, modifier.value, False))


Emoji = Emoji('Emoji', _get_all_emoji_data())
