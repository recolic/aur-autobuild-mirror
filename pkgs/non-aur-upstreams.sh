# created by GPT-5.6
#!/bin/bash
set -euo pipefail

http_upstreams=(
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-zh_tw-10.0.19043.1055-1-any.pkg.tar.zst'
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-zh_cn-10.0.19043.1055-1-any.pkg.tar.zst'
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-10.0.19043.1055-1-any.pkg.tar.zst'
)
repo_upstreams=(
    'zfs-dkms@https://archzfs.com/archzfs/x86_64/archzfs.db'
    'zfs-utils@https://archzfs.com/archzfs/x86_64/archzfs.db'
    # 'linux-surface@https://pkg.surfacelinux.com/arch/linux-surface.db'
    # 'linux-surface-headers@https://pkg.surfacelinux.com/arch/linux-surface.db'
    # 'iptsd@https://pkg.surfacelinux.com/arch/linux-surface.db'
    # 'surface-ipts-firmware@https://pkg.surfacelinux.com/arch/linux-surface.db'
    # 'libwacom-surface@https://pkg.surfacelinux.com/arch/linux-surface.db'
)

known=$(cat)
mkdir -p "$1"
cd "$1"

download() {
    local url=$1 filename=${1##*/}
    [[ "$filename" =~ ^[a-zA-Z0-9@._+-]+\.pkg\.tar\.(zst|xz|gz|bz2|lrz|lzo|Z)$ ]] || { echo "Invalid upstream package: $url" >&2; return 1; }
    if ! grep -Fxq -- "$filename" <<< "$known"; then
        curl --fail --location --silent --show-error --retry 3 --connect-timeout 30 --max-time 600 --output "$filename" "$url"
    fi
    printf '%s\n' "$filename"
}

for url in "${http_upstreams[@]}"; do
    download "$url"
done
for item in "${repo_upstreams[@]}"; do
    name=${item%%@*}
    database=${item#*@}
    filename=$(curl --fail --location --silent --show-error --retry 3 --connect-timeout 30 --max-time 120 "$database" | bsdtar -xOf - '*/desc' | awk -v name="$name" '/^%FILENAME%$/ {getline filename} /^%NAME%$/ {getline; if ($0 == name) print filename}')
    [[ -n "$filename" && "$filename" != *$'\n'* ]] || { echo "Expected one upstream package for $name in $database" >&2; exit 1; }
    download "${database%/*}/$filename"
done
