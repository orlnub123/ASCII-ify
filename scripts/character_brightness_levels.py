import argparse
import json
import statistics

from PIL import Image, ImageDraw, ImageFont


def character_brightness_levels(args):
    font = ImageFont.truetype(args.font, 14)
    data = {}
    for char in map(chr, range(33, 127)):
        image = Image.new("RGB", (8, 14))  # Doesn't support L
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), char, font=font, spacing=5)
        image = image.convert('L')
        average = statistics.mean(image.getdata())
        data[char] = average

    minimum = min(data.values())
    multiplier = 255 / (max(data.values()) - minimum)
    for char, average in data.items():
        average -= minimum
        average *= multiplier
        data[char] = average

    json.dump(data, args.output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('font')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'),
                        required=True)
    args = parser.parse_args()
    character_brightness_levels(args)


if __name__ == '__main__':
    main()
