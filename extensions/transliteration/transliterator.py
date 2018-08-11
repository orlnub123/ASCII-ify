import unidecode


def is_unicode(string):
    try:
        string.encode('ascii')
    except UnicodeEncodeError:
        return True
    else:
        return False


def transliterate(string, *, check=True):
    if check and not is_unicode(string):
        return string

    transliteration = map(unidecode.unidecode_expect_nonascii, string)
    return ''.join(char for char in transliteration if '[?]' not in char)
