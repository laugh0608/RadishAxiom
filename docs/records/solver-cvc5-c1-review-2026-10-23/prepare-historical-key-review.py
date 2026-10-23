#!/usr/bin/env python3
"""Read one retained keyring package and describe a historical verification candidate."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'docs/records/rust-linux-input-review'


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, OLD / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    trust = load('inspect-musl-trust-inputs.py')
    keys = load('inspect-musl-verification-keys.py')
    store = ROOT / 'artifacts/source-inputs/musl-verifier-2fb2e70-20260912'
    manifest = (store / 'manifest.json').read_bytes()
    trust.require(trust.identity(manifest)['sha256'] == '3937d4570faa72ec359dbedf8fdc9c62aa5f26942cc08ee29d1a809e03a54ae9', 'retention manifest changed')
    raw = (store / 'objects' / trust.DEB_SHA).read_bytes()
    trust.require(trust.identity(raw) == {'bytes': 178572, 'sha256': trust.DEB_SHA}, 'keyring package changed')
    _, contents = trust.read_tar(trust.ar_members(raw)['data.tar.xz'])
    removed = contents['usr/share/keyrings/debian-archive-removed-keys.gpg']
    primary, signer = '80D15823B7FD1561F9F7BCDDDC30D7C23CBBABEE', '0146DC6D4A0B2914BDED34DB648ACFD622F3D138'
    key = keys.key_blocks(removed)[primary]
    keys.status.SIGNERS[primary] = (signer, '1')
    inventory = keys.inventory(key, primary)
    plan = {'format': 'radishaxiom-private-cvc5-historical-key-candidate', 'version': '0.1',
            'method': trust.identity(Path(__file__).read_bytes()), 'package': trust.identity(raw),
            'retained_object': str((store / 'objects' / trust.DEB_SHA).relative_to(ROOT)),
            'removed_ring': trust.identity(removed), 'missing_key_block': trust.identity(key),
            'primary': primary, 'signer': signer, 'self_certification_packets': len(inventory['self_bodies']),
            'required_signatures': {
                primary: signer,
                '1F89983E0081FDE018F3CC9673A4F27B8DD47936': 'A7236886F3CCCAAD148A27F80E98404D386FA1D9',
                '4D64FEC119C2029067D6E791F8D2585B8783D481': '4D64FEC119C2029067D6E791F8D2585B8783D481'},
            'acceptance': 'proposed-not-accepted', 'cryptography_executed': False,
            'new_network_download': False, 'system_keyring_changed': False,
            'execution_proposal': {'positive': 'all-three-original-signatures-required; no signature removed',
                'key_checks': 'self-certifications, expiry, retained revocations, required cross-certifications',
                'negative': ['tampered-cleartext', 'each-of-three-required-keys-missing', 'bad-archive-cross-certification'],
                'same_image_and_container_isolation': True, 'seconds_per_command': 30,
                'estimated_seconds': 300, 'cleanup': 'only-new-owned-containers; retain-all-logs'},
            'remaining_trust': ['historical-role-profile-approval', 'retired-key-identity-and-status',
                                'HTTPS-and-retained-package-identity-basis', 'no-all-channel-current-revocation-proof']}
    (HERE / 'historical-key-candidate.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({k:plan[k] for k in ['primary','signer','missing_key_block','self_certification_packets','acceptance']}))


if __name__ == '__main__':
    main()
