#!/bin/bash
export DISPLAY=:99
source /home/priyanka/projects/americangemexpo_blog/.env

killall -9 Xvfb 2>/dev/null
Xvfb :99 -screen 0 1920x1080x24 &
sleep 2

# Start chromium pointing to localhost:3000
chromium-browser --no-sandbox --window-size=1920,1080 --kiosk "http://localhost:2000" &
sleep 5

# Start x11vnc as requested
x11vnc -display :99 -bg -nopw -listen 0.0.0.0 -xkb

# Stream X11 screen to YouTube via FFmpeg
ffmpeg -f x11grab -video_size 1920x1080 -framerate 30 -i :99.0 -f lavfi -i anoisesrc=a=0.005:c=white:r=44100 -ac 2 -c:v libx264 -preset veryfast -b:v 6800k -minrate 6800k -maxrate 6800k -bufsize 13600k -nal-hrd cbr -pix_fmt yuv420p -g 60 -c:a aac -b:a 128k -f flv "rtmp://a.rtmp.youtube.com/live2/$YOUTUBE_STREAM_KEY"
