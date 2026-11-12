# arch-builder

[![Package Builder](https://github.com/recolic/aur-autobuild-mirror/actions/workflows/archlinux-pkgs.yml/badge.svg)](https://github.com/recolic/aur-autobuild-mirror/actions/workflows/archlinux-pkgs.yml)

just an archlinux-pkg builder for my personal need...

## Usage

Add to `/etc/pacman.conf`:

```ini
[recoarch]
SigLevel = Never
Server = https://github.com/recolic/aur-autobuild-mirror/releases/download/archlinux-packages
```
