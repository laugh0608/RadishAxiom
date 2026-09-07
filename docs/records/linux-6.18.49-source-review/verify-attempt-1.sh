#!/usr/bin/env bash
# Review-only verifier. /inputs is read-only; /tmp is an ephemeral tmpfs.
set -euo pipefail
umask 077
mkdir /tmp/gnupg
export GNUPGHOME=/tmp/gnupg

check_key() {
  local key_file="$1" expected="$2" actual
  actual=$(gpg --batch --with-colons --import-options show-only --import "$key_file" \
    | awk -F: '$1 == "fpr" { print $10; exit }')
  test "$actual" = "$expected"
  printf 'PINNED_PRIMARY_FINGERPRINT %s\n' "$actual"
  gpg --batch --import "$key_file"
}

check_key /inputs/gregkh.asc 647F28654894E3BD457199BE38DBBDC86092693E
check_key /inputs/sashal.asc E27E5D8A3403A2EF66873BBCDEA66FF797772CDC
printf '%s  %s\n' \
  ae826f33111fea6f1d279dde7299d7463c8dfd204aeb75a8fb5432bc60a28191 \
  /inputs/linux-6.18.49.tar.xz | sha256sum --check --strict

# The publisher signs the decompressed tar, not the xz transport bytes.
xz -dc /inputs/linux-6.18.49.tar.xz \
  | gpg --batch --no-auto-key-retrieve --status-fd 1 \
      --verify /inputs/linux-6.18.49.tar.sign - > /tmp/signature.status
cat /tmp/signature.status
awk '
  $1 == "[GNUPG:]" && $2 == "VALIDSIG" &&
    ($3 == "647F28654894E3BD457199BE38DBBDC86092693E" ||
     $NF == "647F28654894E3BD457199BE38DBBDC86092693E" ||
     $3 == "E27E5D8A3403A2EF66873BBCDEA66FF797772CDC" ||
     $NF == "E27E5D8A3403A2EF66873BBCDEA66FF797772CDC") { valid++ }
  $1 == "[GNUPG:]" && $2 ~ /^(BADSIG|ERRSIG|EXPSIG|EXPKEYSIG|REVKEYSIG|NO_PUBKEY)$/ { bad++ }
  END { exit !(valid == 1 && bad == 0) }
' /tmp/signature.status
printf 'PINNED_SIGNATURE_CHECK_PASSED\n'
