import argparse
import random

from PIL import Image, ImageDraw, ImageFont


def avatar(args):
    random.seed(int(''.join(str(ord(char)) for char in 'ASCII-ify')))

    background = Image.new('L', (1024, 1024), color=63)
    A = Image.new('LA', background.size)
    A_font = ImageFont.truetype('consola.ttf', size=1024)
    A_draw = ImageDraw.Draw(A)
    xy = ((1024 - 553) / 2 - 5, (1024 - 654) / 2 - 107)
    A_draw.text(xy, text='A', font=A_font)

    mask = Image.new('L', background.size)
    mask_font = ImageFont.truetype('consolab.ttf', size=64)
    mask_draw = ImageDraw.Draw(mask)
    for y in range(1024 // mask_font.size):
        for x in range(int(1024 / mask_font.size * (1521 / 1126))):
            xy = (x * mask_font.size * (1126 / 1521) + 21,
                  y * mask_font.size + 4.5)
            char = chr(random.randrange(33, 127))
            mask_draw.text(xy, text=char, fill=255, font=mask_font)

    background.paste(A, mask=mask)
    background.save(args.output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    avatar(args)


if __name__ == '__main__':
    main()
