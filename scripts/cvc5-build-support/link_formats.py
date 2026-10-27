"""Bounded byte readers for the fixed GNU link candidate, not a linker."""
from collections import Counter
import hashlib
import re
import struct

TEXT_LIMIT = 1024**2
ARG_LIMIT = 65536
MEMBER_LIMIT = 100000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def response(raw):
    """GNU @file subset: whitespace, quotes, backslash; no shell semantics.

    Unclosed quotes / terminal escapes are refused even if a GNU tool would
    tolerate them. Expansion and all path lookups belong to the caller.
    """
    require(type(raw) is bytes and len(raw) <= TEXT_LIMIT and b'\0' not in raw, 'response-byte-budget-or-nul')
    text = raw.decode('utf-8')
    tokens, word, quote, escaped, started = [], [], None, False, False
    for char in text:
        if escaped:
            word.append(char)
            escaped = False
        elif char == '\\':
            escaped, started = True, True
        elif quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in ('"', "'"):
            quote, started = char, True
        elif char in ' \t\n\r\v\f':
            if started:
                tokens.append(''.join(word))
                require(len(tokens) <= ARG_LIMIT, 'response-argument-budget')
                word, started = [], False
        else:
            word.append(char)
            started = True
    require(not escaped and quote is None, 'response-truncated-quote-or-escape')
    if started:
        tokens.append(''.join(word))
    require(len(tokens) <= ARG_LIMIT, 'response-argument-budget')
    return tokens


def object_header(raw):
    """Check retained ELF64 AArch64 REL shape / section bounds, not semantics."""
    require(len(raw) >= 64, 'object-header-truncated')
    h = struct.unpack_from('<16sHHIQQQIHHHHHH', raw)
    require(h[0][:7] == b'\x7fELF\x02\x01\x01' and h[1] == 1 and h[2] == 183
            and h[3] == 1 and h[8] == 64, 'object-abi-or-type')
    require(h[5] == 0 and h[10] == 0 and h[11] == 64 and 0 < h[12] <= 65535
            and 0 < h[13] < h[12] and h[6] >= 64 and h[6] + h[12] * 64 <= len(raw),
            'object-section-shape')
    rows = [struct.unpack_from('<IIQQQQIIQQ', raw, h[6] + n * 64) for n in range(h[12])]
    table = rows[h[13]]
    require(table[1] == 3 and table[4] + table[5] <= len(raw), 'object-string-table')
    names = raw[table[4]:table[4] + table[5]]
    for row in rows:
        require(row[0] < len(names), 'object-section-name-offset')
        end = names.find(b'\0', row[0], row[0] + 4097)
        require(end >= 0, 'object-section-name-truncated')
        name = names[row[0]:end]
        require(not name.startswith((b'.gnu.lto_', b'.llvm')), 'object-lto-not-supported')
        require(row[1] == 8 or row[4] + row[5] <= len(raw), 'object-section-bounds')


def archive(raw):
    """Ordinary GNU ar, including long names and distinct repeated members.

    Thin / BSD archives and unsupported table encodings fail closed. Special
    tables are retained with their hashes, not passed off as object members.
    """
    require(raw.startswith(b'!<arch>\n'), 'archive-not-regular-gnu-ar')
    offset, names, members, occurrences = 8, {}, [], Counter()
    table_seen = False
    while offset < len(raw):
        require(len(members) < MEMBER_LIMIT and offset + 60 <= len(raw), 'archive-header-budget-or-truncation')
        header = raw[offset:offset + 60]
        require(header[58:] == b'`\n', 'archive-header-marker')
        size = header[48:58].strip()
        require(size and size.isdigit(), 'archive-member-size')
        length = int(size)
        begin, end = offset + 60, offset + 60 + length
        require(end <= len(raw), 'archive-member-truncated')
        payload = raw[begin:end]
        label = header[:16].rstrip(b' ')
        if label in (b'/', b'//', b'/SYM64/'):
            name, kind = label.decode('ascii'), 'table'
            if label == b'//':
                require(not table_seen, 'archive-duplicate-name-table')
                table_seen = True
                pos = 0
                while pos < len(payload):
                    stop = payload.find(b'/\n', pos)
                    # GNU ar can pad the long-name table internally by one LF.
                    if stop < 0 and payload[pos:] == b'\n':
                        break
                    require(stop >= pos, 'archive-name-table-truncated')
                    names[pos] = payload[pos:stop].decode('utf-8')
                    pos = stop + 2
            else:
                require(not any(x['name'] == name for x in members), 'archive-duplicate-symbol-table')
        elif re.fullmatch(rb'/[0-9]+', label):
            index = int(label[1:])
            require(index in names, 'archive-long-name-offset')
            name, kind = names[index], 'object'
        else:
            require(label.endswith(b'/') and not label.startswith(b'#1/'), 'archive-name-encoding')
            name, kind = label[:-1].decode('utf-8'), 'object'
        if kind == 'object':
            require(name and '/' not in name and '\\' not in name and name not in ('.', '..')
                    and not any(ord(c) < 32 for c in name), 'archive-member-name')
            object_header(payload)
        occurrences[name] += 1
        members.append({'index': len(members), 'name': name, 'occurrence': occurrences[name],
                        'kind': kind, 'bytes': length, 'sha256': hashlib.sha256(payload).hexdigest()})
        offset = end
        if length % 2:
            require(offset < len(raw) and raw[offset:offset + 1] == b'\n', 'archive-padding')
            offset += 1
    require(any(x['kind'] == 'object' for x in members), 'archive-no-objects')
    return members


def script(raw):
    """Read only INPUT/GROUP/AS_NEEDED and comments; other ld syntax stops.

    Return tokens with grouping intact. This does not interpret a full linker
    script, symbol resolution, archive extraction or search side effects.
    """
    require(type(raw) is bytes and len(raw) <= TEXT_LIMIT and b'\0' not in raw, 'script-budget-or-nul')
    text = raw.decode('utf-8')
    tokens, pos = [], 0
    pattern = re.compile(r'\s+|/\*.*?\*/|[(),]|"[^"\n]*"|[^\s(),"]+', re.S)
    while pos < len(text):
        match = pattern.match(text, pos)
        require(match is not None, 'script-token')
        token = match.group()
        pos = match.end()
        if token.isspace() or (token.startswith('/*') and token.endswith('*/')):
            continue
        require(not token.startswith('/*'), 'script-truncated-comment')
        tokens.append(token[1:-1] if token.startswith('"') else token)
        require(len(tokens) <= ARG_LIMIT, 'script-token-budget')
    stack, expect_open, paths = [], False, []
    for token in tokens:
        if token in ('INPUT', 'GROUP', 'AS_NEEDED'):
            require(not expect_open and (token != 'AS_NEEDED' or bool(stack)), 'script-group-position')
            require(token == 'AS_NEEDED' or not stack, 'script-nested-command')
            expect_open = True
        elif token == '(':
            require(expect_open and len(stack) < 16, 'script-group-depth-or-open')
            stack.append(0)
            expect_open = False
        elif token == ')':
            require(not expect_open and stack and stack[-1] > 0, 'script-empty-or-unmatched-close')
            stack.pop()
            if stack:
                stack[-1] += 1
        elif token == ',':
            require(stack and not expect_open and stack[-1] > 0, 'script-comma')
        else:
            require(stack and not expect_open and token not in (';', '{', '}')
                    and not any(c in token for c in '$`*?;{}\\'), 'script-unsupported-command-or-path')
            paths.append(token)
            stack[-1] += 1
    require(not stack and not expect_open and paths, 'script-truncated-or-empty')
    return {'tokens': tokens, 'inputs': paths}
