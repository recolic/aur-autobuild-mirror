# recolic's AUR mirror

> https://recolic.net/s/mirrors

Create your own mirror site, to auto-build your favorite AUR packages and free your m3-6Y30 toy CPU from heavy compilation work!

## Deploy

### Use my docker image

1. Put this repo to your server. Assume you're placing this directory to `/srv/my-mirror-site`

2. Modify the `build_outdir` and `repo_name` variable in aur-sync.sh. 

You should know how to publish the output directory with your web server. 

3. Add a crontab line and enjoy! 

```
# Trigger recolic-aur rebuild twice a month at 6 AM UTC+8, means 22:00 UTC. 
0 22 2,17 * * cd /srv/mirrors && nohup ./aur-sync.sh >> /var/log/aursync.log 2>&1 & disown
```

### Build your own docker image

1. Build docker image

```
cd docker-pikaur
docker build -t your-name/pikaur .
```

2. Move `your-name/pikaur` to your server, modify `aur-sync.sh` manually, and continue following `Use my docker image` guide.

