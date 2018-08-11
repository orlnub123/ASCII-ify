import os
import json


here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'emoji_data.json'), encoding='utf-8') as file:
    _emoji_data = json.load(file)


def _get_emoji_data():
    for category_name, category in _emoji_data.items():
        for emoji in category:
            for name in emoji['names']:
                yield (name, (
                    category_name, emoji['surrogates'],
                    emoji.get('hasDiversity', False)
                ))
