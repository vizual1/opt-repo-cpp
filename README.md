# Build
1.  ```bash
    docker build -t cpptool .
2.  ```bash
    docker run -it -v "%cd%":/app cpptool
    docker run -it -v ${PWD}:/app cpptool
    ```
    
docker build --progress=plain -t cpptool .

