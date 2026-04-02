import re

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False)
    return _reader

def fix_indian_plate(text):
    if len(text) >= 10:
        text = list(text)
        for i in [2, 3, 6, 7, 8, 9]:
            if i < len(text):
                if text[i] == 'O': text[i] = '0'
                if text[i] == 'I': text[i] = '1'
                if text[i] == 'L': text[i] = '4'
        return "".join(text)
    return text

def get_text(image):
    results = get_reader().readtext(image)
    texts = []
    for (_, text, conf) in results:
        clean = re.sub(r'[^A-Z0-9]', '', text.upper())
        clean = fix_indian_plate(clean)
        if len(clean) >= 6:
            texts.append((clean, round(conf, 2)))
    return texts
