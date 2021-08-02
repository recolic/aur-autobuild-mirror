# docker run -ti -v (pwd)/recolic-aur:/home/builder/.cache/pikaur/pkg recolic/pikaur      bash -c 'chown builder -R /home/builder/.cache/pikaur/pkg && sudo -u builder pikaur -Sw --noconfirm $pkgs'
# You must reuse the container (commit it as new image) after running first build. There may be tons of dependencies to be downloaded. 

FROM archlinux:base-devel

COPY install-pikaur.sh /
RUN bash /install-pikaur.sh
RUN useradd -m builder && echo 'builder ALL=(ALL) NOPASSWD: ALL' | EDITOR='tee -a' visudo
# To prevent docker from creating a root-only dir
RUN sudo -u builder mkdir -p /home/builder/.cache/pikaur/build
RUN echo "WAIT! This repo is not finished. I'll copy latest code from laptop tonight. " && generate-error


