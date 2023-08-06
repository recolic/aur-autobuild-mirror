#!/bin/bash
pacman -Sy --noconfirm git pyalpm python-commonmark python-pip python-build python-installer python-setuptools python-markdown-it-py python-hatchling &&
git clone https://aur.archlinux.org/pikaur.git &&
chmod 777 -R pikaur &&
cd pikaur &&
sudo -u nobody makepkg &&
pacman -U --noconfirm *.pkg.*
exit $?

