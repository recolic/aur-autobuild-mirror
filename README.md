# recolic's AUR mirror

> https://recolic.net/s/mirrors

Create your own mirror site, to auto-build your favorite AUR packages and free your m3-6Y30 toy CPU from heavy compilation work!

## Deploy

1. Build docker image

```
cd docker-pikaur
docker build -t your-name/pikaur .
```

2. Put this directory to your server. Assume you're placing this directory to `/srv/my-mirror-site`

3. Create a directory `mirrors/output` (you can name it as anything you want), and modify the `build_outdir` variable in aur-sync.sh. Also change the `recolic-aur` after the `repo-add` command, to your repo name. 

You should know how to publish the directory to your web server. 

4. Add a crontab line and enjoy! 

```
# Trigger recolic-aur rebuild twice a month at 6 AM UTC+8, means 22:00 UTC. 
0 22 2,17 * * cd /srv/mirrors && nohup ./aur-sync.sh >> /var/log/aursync.log 2>&1 & disown
```

