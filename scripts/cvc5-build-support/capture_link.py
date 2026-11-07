#!/usr/bin/env python3
"""Record one linker invocation and STOP; never execute the supplied program.

The file is a tool observation in the build workspace, not a protected receipt.
An external controller must retain the nonzero exit, collect all descendants,
freeze inputs and review the command before any separately authorized link.
"""
import argparse
import json
import os
from pathlib import Path
import sys

FORMAT = 'radishaxiom-private-cvc5-link-capture'
EXIT_INTERCEPTED = 78
BYTE_LIMIT = 1024 * 1024
ARG_LIMIT = 65536
# The recipe starts from a closed environment. Make / the shell may add only
# these bookkeeping names. Unknown names fail before values are serialized.
ENV_KEYS = frozenset('PATH HOME TMPDIR LANG LC_ALL TZ SOURCE_DATE_EPOCH '
                     'PYTHONNOUSERSITE PYTHONDONTWRITEBYTECODE PKG_CONFIG_LIBDIR PKG_CONFIG_SYSROOT_DIR '
                     'AWK SHELL CONFIG_SHELL AR AS LD NM RANLIB '
                     'PWD OLDPWD SHLVL MAKEFLAGS MFLAGS MAKELEVEL _'.split())


def observation(argv, cwd, environment):
    if not 1 <= len(argv) <= ARG_LIMIT:
        raise ValueError('capture-argument-count')
    if set(environment) - ENV_KEYS:
        raise ValueError('capture-environment-key-not-allowed')
    values = [cwd, *argv, *environment.keys(), *environment.values()]
    size = 0
    for value in values:
        if not isinstance(value, str) or '\x00' in value:
            raise ValueError('capture-string')
        size += len(value.encode('utf-8')) + 1
        if size > BYTE_LIMIT:
            raise ValueError('capture-byte-budget')
    value = {'format': FORMAT, 'version': '0.2', 'target': 'cvc5-bin',
             'scope': 'untrusted-tool-observation', 'driver_executed': False,
             'exit_code': EXIT_INTERCEPTED, 'argv': list(argv), 'cwd': cwd,
             'environment': dict(sorted(environment.items()))}
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    if len(raw) > BYTE_LIMIT:
        raise ValueError('capture-encoded-byte-budget')
    return raw


def write_capture(path, raw):
    if (not path.is_absolute() or not path.parent.is_dir()
            or path.parent.resolve() != path.parent or path.is_symlink()):
        raise ValueError('capture-output-path')
    # O_EXCL prevents a second invocation from replacing the first record.
    # A partial file on any write failure is intentionally left for diagnosis.
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if '--' not in args:
            raise ValueError('capture-missing-command-separator')
        boundary = args.index('--')
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        parser.add_argument('--output', required=True, type=Path)
        options = parser.parse_args(args[:boundary])
        raw = observation(args[boundary + 1:], os.getcwd(), dict(os.environ))
        write_capture(options.output, raw)
    except (ValueError, OSError, UnicodeError) as exc:
        # Do not echo untrusted argv, environment values or credential paths.
        reason = str(exc) if type(exc) is ValueError and str(exc).startswith('capture-') else type(exc).__name__
        print('link capture failed: ' + reason + '; retained data is not a successful build', file=sys.stderr)
        return 1
    print('link intercepted; driver not executed; build remains incomplete')
    return EXIT_INTERCEPTED


if __name__ == '__main__':
    sys.exit(main())
