# docker run -ti -v (pwd)/recolic-aur:/home/builder/.cache/pikaur/pkg recolic/pikaur      bash -c 'chown builder -R /home/builder/.cache/pikaur/pkg && sudo -u builder pikaur -Sw --noconfirm $pkgs'
# You can reuse the container (commit it as new image) after running first build. There may be tons of dependencies to be downloaded. 

FROM archlinux:base-devel

COPY install-pikaur.sh /
RUN bash /install-pikaur.sh
RUN pacman -S --noconfirm go
RUN useradd -m builder && echo 'builder ALL=(ALL) NOPASSWD: ALL' | EDITOR='tee -a' visudo
# To prevent docker from creating a root-only dir
RUN sudo -u builder mkdir -p /home/builder/.cache/pikaur/build && \
    sed -i 's/check_pgpsigs() {/check_pgpsigs() { return 0/g' /usr/share/makepkg/integrity/verify_signature.sh && \
    sed -i 's/SigLevel.*$/SigLevel = Never/' /etc/pacman.conf
# makepkg auto-key-retrieve is not working. This is my only solution. 
# pacman will complain about expired GPG keys if the image is not updated. Disable the SigLevel verify to avoid these error. 


