#!/bin/bash

[ "$1" = "" ] && echo '(Helper for MSFT FTE) Usage:
1. Download official onboard script at
   - https://aka.ms/onboardlinuxmde (search for "WindowsDefender")
2. unzip and run it like'"
     sudo $0 onboarding-script-prod-manual.sh
" && exit 1

set -e
original_script="$1"

echo "Patching $original_script and checking common mistake ..."
sed -i 's/echo "arch"/echo debian/' "$original_script"
systemctl enable --now mdatp
touch /etc/opt/microsoft/mdatp/.permission-test && rm -f /etc/opt/microsoft/mdatp/.permission-test || exit 2
[ "$EUID" -eq 0 ] || exit 3

echo "Launching $original_script ..."
bash "$original_script"

