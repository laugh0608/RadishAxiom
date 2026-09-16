#!/usr/bin/env python3
"""Compare six fixed recipe inputs with the retained complete Debian Sources; no fetch or acceptance."""
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TARGETS = [
    ('binutils', 'binutils-2.44.tar.gz', 'binutils', 'different-compression'),
    ('gcc', 'gcc-9.4.0.tar.xz', 'gcc-9', 'version-absent'),
    ('gmp', 'gmp-6.3.0.tar.xz', 'gmp', 'dfsg-repack'),
    ('mpc', 'mpc-1.3.1.tar.gz', 'mpclib3', 'same-version-format-candidate'),
    ('mpfr', 'mpfr-4.2.2.tar.xz', 'mpfr4', 'same-version-format-candidate'),
    ('linux-headers', 'linux-headers-4.19.88.tar.xz', 'linux', 'version-and-artifact-differ'),
]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect():
    recipe = load('inspect-musl-cross-make.py')
    inputs = load('prepare-musl-verification-inputs.py')
    store = ROOT / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912'
    prepared, _ = inputs.prepare(store)
    archive = ROOT / '.tmp/musl-cross-make-review-c38a1c1/musl-cross-make-3635262.tar.gz'
    full = recipe.inspect(archive, recipe.SOURCE_SHA, include_text=True)
    recorded = json.loads((HERE / 'musl-cross-make-inventory-2026-09-10.json').read_bytes())
    reduced = {**full, 'files': [{k: v for k, v in row.items() if k != 'text'} for row in full['files']]}
    inputs.require(reduced == recorded, 'fixed recipe inventory drift')
    files = {row['path']: row for row in full['files']}
    names = {package for _, _, package, _ in TARGETS}
    index_identity = prepared['host_only']['Sources.xz']
    selected = {name: [] for name in names}
    # Exhaust the validated complete stream, including the absence claim for gcc-9.
    for row in inputs.auth.chain.index_stanzas(store / 'objects' / index_identity['sha256'], index_identity):
        if row['package'] in selected:
            selected[row['package']].append({key: row[key] for key in
                                             ('package', 'version', 'directory', 'checksums-sha256')})
    results = []
    for name, filename, package, reason in TARGETS:
        statement = files['hashes/' + filename + '.sha1']
        digest, declared = statement['text'].split()
        inputs.require(re.fullmatch(r'[0-9a-f]{40}', digest) is not None and declared == filename,
                       'unexpected recipe digest declaration')
        candidates = []
        for row in selected[package]:
            originals = {path: value for path, value in inputs.auth.chain.checksums(row['checksums-sha256']).items()
                         if '.orig.tar.' in path}
            candidates.append({**{key: row[key] for key in ('package', 'version', 'directory')},
                               'originals': originals})
        results.append({'dependency': name, 'recipe_archive': filename, 'recipe_sha1_statement_only': digest,
                        'recipe_statement_file': {k: statement[k] for k in ('path', 'bytes', 'sha256')},
                        'index_source_package': package, 'index_candidates': candidates,
                        'review_category': reason, 'source_bytes_acquired_this_batch': False,
                        'byte_equivalence_checked': False, 'source_acceptance': 'not-assessed'})
    return {'kind': 'diagnostic-musl-remaining-source-review-v1', 'recipe_commit': recipe.COMMIT,
            'recipe_archive': full['archive'], 'sources': index_identity, 'dependencies': results,
            'review_categories_are_manual': True, 'cryptography_reexecuted': False,
            'musl_acceptance_does_not_transfer': True,
            'methods': {name: inputs.identity((HERE / name).read_bytes()) for name in
                        ('inspect-musl-remaining-sources.py', 'inspect-musl-cross-make.py',
                         'prepare-musl-verification-inputs.py')},
            'chain_method': inputs.identity((ROOT / 'scripts/inspect-debian-source-chain.py').read_bytes())}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
