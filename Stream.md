## Useful Commands to manage your new service
You can use the following standard systemd commands anytime you need to control the stream:

**Check the status:**
```bash
sudo systemctl status youtube-stream.service
```

**Restart the stream:**
```bash
sudo systemctl restart youtube-stream.service
```

**Stop the stream completely:**
```bash
sudo systemctl stop youtube-stream.service
```

**View the stream logs in real-time:**
*(This replaces your `stream.log` file, and manages log rotation automatically!)*
```bash
sudo journalctl -u youtube-stream.service -f
```
