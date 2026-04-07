
git add .
git commit -m "changes"
git push

docker stop onion-vanity
docker rm onion-vanity

docker build --build-arg USER_ID=$(id -u) --build-arg GROUP_ID=$(id -g) -t imvickykumar999/onion-vanity:latest .
docker push imvickykumar999/onion-vanity:latest

docker pull imvickykumar999/onion-vanity:latest
docker run -d --name onion-vanity -p 2000:2000 imvickykumar999/onion-vanity:latest
