#!/bin/bash

set -e

pacman -Sy --noconfirm git pyalpm python-commonmark python-pip python-build python-installer python-setuptools python-markdown-it-py python-hatchling

# bug fix: https://github.com/docker/for-mac/issues/7331
pacman -U --noconfirm https://archive.archlinux.org/packages/f/fakeroot/fakeroot-1.34-1-x86_64.pkg.tar.zst
fakeroot --version

git clone https://aur.archlinux.org/pikaur.git
chmod 777 -R pikaur
cd pikaur
sudo -u nobody makepkg
pacman -U --noconfirm *.pkg.*

exit $?

