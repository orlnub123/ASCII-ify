from .enums import Emoji, Category, Modifier


def convert(text):
    import re
    text = list(text)
    start = 0
    pattern = re.compile(':([a-z0-9_+-]+):')
    while True:
        match = pattern.search(''.join(text), start)
        if match is None:
            break
        start, end = match.span()
        try:
            text[start:end] = str(Emoji[match.group(1)])
        except KeyError:
            pass
        start += 1
    return ''.join(text)


def parse(text):
    import operator
    text = list(text)
    positions = {}
    emojis = sorted(Emoji, key=lambda emoji: len(str(emoji)), reverse=True)
    for emoji in emojis:
        value = emoji.value
        while True:
            position = ''.join(text).find(value)
            if position != -1:
                positions[position] = emoji
                length = len(value)
                text[position:position + length] = ' ' * length
            else:
                break
    return dict(sorted(positions.items(), key=operator.itemgetter(0))).values()
