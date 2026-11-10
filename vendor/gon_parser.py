# GON reader from MewTree (MIT), see MewTree-LICENSE.txt
def _tokens(t):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c.isspace() or c == ",": i += 1
        elif t.startswith("//", i):
            i = t.find("\n", i); i = n if i < 0 else i
        elif t.startswith("/*", i):
            i = t.find("*/", i + 2); i = n if i < 0 else i + 2
        elif c in "{}[]": yield c; i += 1
        elif c == '"':
            j = i + 1
            while j < n and t[j] != '"': j += 2 if t[j] == "\\" else 1
            yield t[i + 1:j]; i = j + 1
        else:
            j = i
            while j < n and not t[j].isspace() and t[j] not in '{}[],"' and not t.startswith("//", j): j += 1
            yield t[i:j]; i = j


def parse_gon(text):
    toks = list(_tokens(text)); pos = 0
    def val():
        nonlocal pos
        tk = toks[pos]; pos += 1
        if tk == "{": return obj("}")
        if tk == "[":
            out = []
            while toks[pos] != "]": out.append(val())
            pos += 1; return out
        return tk
    def obj(end):
        nonlocal pos
        r = {}
        while pos < len(toks) and toks[pos] != end:
            k = toks[pos]; pos += 1; r[k] = val()
        pos += 1; return r
    return obj(None)


