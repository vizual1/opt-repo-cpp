# Build
1.  ```bash
    docker build -t cpptool .
    docker build --progress=plain -t cpptool .
2.  ```bash
    docker run -it -v "%cd%":/app cpptool
    docker run -it -v ${PWD}:/app cpptool
    ```

docker build -t cpp18 -f docker/Dockerfile.18.04 .
docker build -t cpp20 -f docker/Dockerfile.20.04 .
docker build -t cpp22 -f docker/Dockerfile.22.04 .
docker build -t cpp24 -f docker/Dockerfile.24.04 .

