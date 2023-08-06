#!/bin/bash

http_upstreams=(
    # http upstreams has no auto-update
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-zh_tw-10.0.19043.1055-1-any.pkg.tar.zst'
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-zh_cn-10.0.19043.1055-1-any.pkg.tar.zst'
    'https://raw.githubusercontent.com/fphoenix88888/ttf-mswin10-arch/master/ttf-ms-win10-10.0.19043.1055-1-any.pkg.tar.zst'
)
repo_upstreams=(
    # Take care of the tailing "/"!!!
    zfs-dkms@https://archzfs.com/archzfs/x86_64/
    zfs-utils@https://archzfs.com/archzfs/x86_64/
    linux-surface@https://pkg.surfacelinux.com/arch/
    linux-surface-headers@https://pkg.surfacelinux.com/arch/
    iptsd@https://pkg.surfacelinux.com/arch/
    surface-ipts-firmware@https://pkg.surfacelinux.com/arch/
    libwacom-surface@https://pkg.surfacelinux.com/arch/
)

# Please place simple, important, SMALL packages first. Place error-prone packages last. 
aur_upstreams=(
    pikaur
    frpc
    frps
    azure-cli
    create_ap
    asix-ax88179-dkms
    snakesocks
    teamviewer
    remarkable
    goland
    goland-jre
    clion
    clion-jre
    gnome-terminal-transparency
    shared-bootdir-helper
    chrome-gnome-shell
    oreo-cursors-git
)

build_outdir="mirrors/recolic-aur"
repo_name=recolic-aur

function sync_aur () {
    echo "Running aur autobuild..."

    # Use the external loop to force pikaur to skip failed packages. 
    for ele in "${aur_upstreams[@]}"; do
        # pikaur would skip if the package is already up-to-date. 
        sudo docker run -i --cpus 1.2 --rm -v "$(pwd)/$build_outdir":/home/builder/.cache/pikaur/pkg recolic/pikaur      bash -c "chown builder -R /home/builder/.cache/pikaur/pkg && sudo -u builder pikaur -Syw --noconfirm $ele"
        [[ $? != 0 ]] && echo "WARNING: Failed to build $ele"
    done
}

function sync_http () {
    cd $build_outdir
    has_error=0
    for item in "${http_upstreams[@]}"; do
        aria2c --conditional-get --allow-overwrite "$item" || has_error=$?
    done
    cd -
    return $has_error
}

function sync_repo () {
    cd $build_outdir
    has_error=0
    for item in "${repo_upstreams[@]}"; do
        IFS='@' read nm repo_url <<< "$item"
        pkgs_in_repo=`curl "$repo_url" | sed 's/^.*href="//g' | sed 's/".*$//g' | grep -F pkg.tar | grep -v 'sig$'`
        pkg_relurl=`echo "$pkgs_in_repo" | grep -E "^$nm(-[0-9a-zA-Z_\\.:]*){3}.pkg.tar.*$"`
        [[ "$pkg_relurl" == *.blob ]] && pkg_relurl=`curl "$repo_url$pkg_relurl" | sed 's@^.*/@@g'`
        echo DEBUG: down "$repo_url$pkg_relurl"
        aria2c --conditional-get --allow-overwrite "$repo_url$pkg_relurl" || has_error=$?
    done
    cd -
    return $has_error
}

function dedup_and_build_index () {
    # deduplicate
    cd $build_outdir
    # ls output is sorted alphabet-ly
    prev_pkgName=""
    prev_fname=""
    for f in `ls *.pkg.tar.*`; do
        curr_pkgName=`echo "$f" | sed -E 's/(-[0-9a-zA-Z_\\.:]*){3}.pkg.tar.*$//g'`
        [[ "$prev_pkgName" = "$curr_pkgName" ]] && echo "DEDUP: removing $prev_fname..." && rm "$prev_fname"
        prev_fname="$f"
        prev_pkgName="$curr_pkgName"
    done
    cd -

    # build index.db
    sudo docker run -i --rm -v "$(pwd)/$build_outdir":/home/builder/.cache/pikaur/pkg recolic/pikaur      bash -c "chown builder -R /home/builder/.cache/pikaur/pkg && cd /home/builder/.cache/pikaur/pkg && repo-add $repo_name.db.tar.gz *.pkg.tar.*"
    return $?
}

# Must update arch toolchain
docker pull recolic/pikaur

mkdir -p "$build_outdir"
sync_aur || echo AUR-gg
sync_repo || echo REPO-gg
sync_http || echo HTTP-gg
dedup_and_build_index || echo BINDEX-gg

