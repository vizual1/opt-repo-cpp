FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    curl \
    python3 \
    python3-pip \
    pkg-config \
    gcc g++ \
    clang \
    lcov \ 
    gcovr \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install PyGithub \ 
    openai

WORKDIR /app

COPY . .

CMD ["bash"]
