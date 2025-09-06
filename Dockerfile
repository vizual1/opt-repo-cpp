FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    ninja-build \
    meson \
    git \
    curl \
    python3 \
    python3-pip \
    unzip \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    gcc g++ \
    clang \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install conan
RUN pip3 install PyGithub

WORKDIR /app

COPY . .

CMD ["bash"]
