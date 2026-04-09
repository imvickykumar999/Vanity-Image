# `Onion Vanity`

A Flask web app for generating vanity Tor onion addresses using `mkp224o`.
This repository includes a Docker image published to Docker Hub.

>      Deploy on Railway via Docker : https://hub.docker.com/r/imvickykumar999/onion-vanity
>    
>[![ss1](https://github.com/user-attachments/assets/b7cdf340-b7cf-4c1e-8501-a4f4040a28d1)](https://youtu.be/f460WY3IMcw)
>[![ss2](https://github.com/user-attachments/assets/2235d3c8-46b0-4085-9bec-26953d0d9312)](https://onion.imvickykumar999.dpdns.org/)

## Docker Hub

Pull the image from Docker Hub:

```bash
docker pull imvickykumar999/onion-vanity:latest
```

## Run the container

Start the app in a Docker container:

```bash
docker run -d --name onion-vanity -p 2000:2000 imvickykumar999/onion-vanity:latest
```

Then open your browser at:

```
http://localhost:2000
```

## Stop and remove the container

```bash
docker stop onion-vanity
docker rm onion-vanity
```

## Notes

- The app exposes port `2000`.
- Generated onion folders are stored inside the container at `/app/mkp224o/onions`.
- If you want to persist generated data, mount a host directory to `/app/mkp224o/onions`.

Example with persistent host volume:

```bash
docker run -d --name onion-vanity -p 2000:2000 -v "$PWD/onions":/app/mkp224o/onions imvickykumar999/onion-vanity:latest
```

## Fixing host permissions

If the host `onions` folder is root-owned from a previous container run, you can reset ownership before starting the container:

```bash
sudo chown -R $(id -u):$(id -g) onions
```

To build the image with your host user ID and keep generated files writable on the host, rebuild with:

```bash
docker build --build-arg USER_ID=$(id -u) --build-arg GROUP_ID=$(id -g) -t imvickykumar999/onion-vanity:latest .

docker push imvickykumar999/onion-vanity:latest
```
