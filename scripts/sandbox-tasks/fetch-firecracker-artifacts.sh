#!/usr/bin/env bash
set -euo pipefail

ARCH="$(uname -m)"
S3="https://s3.amazonaws.com/spec.ccfc.min"
STORE="${DATAWORC_SANDBOX_STORE:-$HOME/.local/share/dataworc/sandbox/images/firecracker}"

for c in curl python3 sha256sum md5sum unsquashfs mkfs.ext4 e2fsck debugfs truncate; do
  command -v "$c" >/dev/null 2>&1 || {
    echo "FAIL: missing '$c' (sudo apt install -y squashfs-tools e2fsprogs curl)"
    exit 1
  }
done

sudo -v

WORK="$(mktemp -d /tmp/dataworc-fc.XXXXXX)"

cleanup() {
  sudo rm -rf --one-file-system "$WORK"
}

trap cleanup EXIT

s3_list() {
python3 - "$S3" "$1" "$2" <<'PY'
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

base, prefix, mode = sys.argv[1:]
ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
token = None

while True:
    query = {
        "list-type": "2",
        "prefix": prefix,
    }

    if mode == "prefixes":
        query["delimiter"] = "/"

    if token:
        query["continuation-token"] = token

    url = base + "?" + urllib.parse.urlencode(query)

    with urllib.request.urlopen(url, timeout=30) as response:
        root = ET.fromstring(response.read())

    if mode == "prefixes":
        for item in root.findall("s3:CommonPrefixes/s3:Prefix", ns):
            print(item.text)
    else:
        for item in root.findall("s3:Contents", ns):
            print(
                item.findtext("s3:Key", namespaces=ns),
                item.findtext("s3:ETag", namespaces=ns).strip('"'),
                item.findtext("s3:Size", namespaces=ns),
                sep="\t",
            )

    if root.findtext("s3:IsTruncated", namespaces=ns) != "true":
        break

    token = root.findtext(
        "s3:NextContinuationToken",
        namespaces=ns,
    )
PY
}

pick_latest() {
  printf '%s\n' "$1" \
    | awk -F'\t' -v p="$2" -v re="$3" \
        'index($1,p)==1 {
           n=substr($1,length(p)+1)
           if (n ~ re) print
         }' \
    | sort -V \
    | tail -1
}

fetch() {
  local key="$1"
  local etag="$2"
  local destination="$3"

  curl -fL --retry 3 -o "$destination" "$S3/$key"

  if [[ "$etag" != *-* ]]; then
    local actual_md5
    actual_md5="$(md5sum "$destination" | cut -d' ' -f1)"

    if [ "$actual_md5" != "$etag" ]; then
      echo "FAIL: ETag/md5 mismatch for $key"
      exit 1
    fi

    echo "verified (S3 ETag md5): $key"
  else
    echo "WARN: multipart ETag for $key; sha256 will be recorded"
  fi
}

echo "===== DISCOVER CI ARTIFACT SET ====="

PREFIX="$(
  s3_list firecracker-ci/ prefixes \
    | grep -E '^firecracker-ci/[0-9]{8}-[^/]+/$' \
    | sort \
    | tail -1 \
    || true
)"

[ -n "$PREFIX" ] || {
  echo "FAIL: no firecracker-ci/<YYYYMMDD-...>/ prefix found"
  exit 1
}

CI_ID="$(basename "$PREFIX")"
DIRP="${PREFIX}${ARCH}/"

echo "prefix=$PREFIX"

DEST="$STORE/$CI_ID/$ARCH"

if [ -e "$DEST" ]; then
  if [ -f "$DEST/manifest.json" ]; then
    echo "ALREADY PRESENT: $DEST (delete it to rebuild)"
    exit 0
  fi

  echo "FAIL: incomplete destination already exists: $DEST"
  echo "Inspect or remove it before rebuilding."
  exit 1
fi

LISTING="$(s3_list "$DIRP" keys)"

KERNEL_LINE="$(
  pick_latest \
    "$LISTING" \
    "$DIRP" \
    '^vmlinux-[0-9]+\.[0-9]+\.[0-9]+$'
)"

ROOTFS_LINE="$(
  pick_latest \
    "$LISTING" \
    "$DIRP" \
    '^ubuntu-[0-9]+\.[0-9]+\.squashfs$'
)"

[ -n "$KERNEL_LINE" ] || {
  echo "FAIL: no vmlinux in $DIRP"
  exit 1
}

[ -n "$ROOTFS_LINE" ] || {
  echo "FAIL: no ubuntu-*.squashfs in $DIRP"
  exit 1
}

IFS=$'\t' read -r KERNEL_KEY KERNEL_ETAG KERNEL_SIZE <<<"$KERNEL_LINE"
IFS=$'\t' read -r ROOTFS_KEY ROOTFS_ETAG ROOTFS_SIZE <<<"$ROOTFS_LINE"

UBUNTU_VERSION="$(
  basename "$ROOTFS_KEY" .squashfs \
    | grep -oE '[0-9]+\.[0-9]+'
)"

KERNEL_VERSION="$(
  basename "$KERNEL_KEY" \
    | sed 's/^vmlinux-//'
)"

echo "kernel=$KERNEL_KEY"
echo "rootfs=$ROOTFS_KEY (ubuntu $UBUNTU_VERSION)"

echo "===== DOWNLOAD + VERIFY ====="

fetch "$KERNEL_KEY" "$KERNEL_ETAG" "$WORK/vmlinux"
fetch "$ROOTFS_KEY" "$ROOTFS_ETAG" "$WORK/ubuntu.squashfs"

echo "===== CONVERT SQUASHFS -> EXT4 ====="

sudo unsquashfs \
  -no-progress \
  -d "$WORK/rootfs" \
  "$WORK/ubuntu.squashfs" \
  >/dev/null

USED_BYTES="$(
  sudo du -sb "$WORK/rootfs" \
    | cut -f1
)"

SIZE_MB=$(
  (
    USED_BYTES * 13 / 10 / 1048576 + 256
  )
)

truncate -s "${SIZE_MB}M" "$WORK/rootfs.ext4"

sudo mkfs.ext4 \
  -q \
  -F \
  -d "$WORK/rootfs" \
  "$WORK/rootfs.ext4"

sudo e2fsck \
  -fn \
  "$WORK/rootfs.ext4"

[ "$(sudo stat -c '%u:%g' "$WORK/rootfs/etc/passwd")" = "0:0" ] || {
  echo "FAIL: rootfs ownership not preserved"
  exit 1
}

echo "===== VERIFY FINAL EXT4 CONTENTS ====="

PASSWD_STAT="$(
  sudo debugfs \
    -R 'stat /etc/passwd' \
    "$WORK/rootfs.ext4" \
    2>/dev/null \
    || true
)"

printf '%s\n' "$PASSWD_STAT"

if grep -Eq \
  'User:[[:space:]]+0[[:space:]]+Group:[[:space:]]+0([^0-9]|$)' \
  <<<"$PASSWD_STAT"
then
  echo "PASS: /etc/passwd is root:root inside final ext4"
else
  echo "FAIL: /etc/passwd is not root:root inside final ext4"
  exit 1
fi

echo "===== INSTALL (outside repo) ====="

rm -rf "$DEST.partial"
mkdir -p "$DEST.partial"

install -m 0444 \
  "$WORK/vmlinux" \
  "$DEST.partial/vmlinux"

install -m 0444 \
  "$WORK/rootfs.ext4" \
  "$DEST.partial/rootfs.ext4"

python3 - "$DEST.partial/manifest.json" <<PY
import datetime
import json
import sys

manifest = {
    "schema": "dataworc.sandbox.firecracker_image.v1",
    "created_utc": datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(),
    "arch": "$ARCH",
    "source": "$S3",
    "ci_artifact_prefix": "$PREFIX",
    "kernel": {
        "key": "$KERNEL_KEY",
        "version": "$KERNEL_VERSION",
        "etag": "$KERNEL_ETAG",
        "size_bytes": int("$KERNEL_SIZE"),
        "sha256": "$(sha256sum "$WORK/vmlinux" | cut -d' ' -f1)",
    },
    "rootfs_upstream": {
        "key": "$ROOTFS_KEY",
        "ubuntu_version": "$UBUNTU_VERSION",
        "etag": "$ROOTFS_ETAG",
        "size_bytes": int("$ROOTFS_SIZE"),
        "sha256": "$(sha256sum "$WORK/ubuntu.squashfs" | cut -d' ' -f1)",
    },
    "rootfs_ext4": {
        "file": "rootfs.ext4",
        "size_mb": $SIZE_MB,
        "sha256": "$(sha256sum "$WORK/rootfs.ext4" | cut -d' ' -f1)",
        "ownership": "preserved via root unsquashfs",
        "e2fsck": "clean",
    },
    "modifications": [],
    "network": "none (no SSH keys, no TAP)",
}

with open(sys.argv[1], "w", encoding="utf-8") as output:
    json.dump(manifest, output, indent=2)
    output.write("\n")
PY

mv "$DEST.partial" "$DEST"

echo
echo "PASS"
ls -l "$DEST"
cat "$DEST/manifest.json"
