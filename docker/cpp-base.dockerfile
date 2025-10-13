FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    PATH="/opt/vcpkg:/opt/venv/bin:$PATH"

# base build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config wget curl ca-certificates ccache meson \
    software-properties-common gnupg \
    python3 python3-pip python3-venv python3-setuptools python3-wheel python3-dev \
    git curl zip unzip tar \
    autoconf autoconf-archive automake libtool \
    libmount-dev libblkid-dev libcap-dev libselinux1-dev \
    liblzma-dev zlib1g-dev libzstd-dev liblz4-dev \
    libudev-dev libseccomp-dev libgcrypt20-dev libgnutls28-dev libssl-dev \
    gettext libffi-dev libcurl4-openssl-dev libpcre2-dev \ 
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir meson ninja

# core c++ libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-all-dev \
    libgtest-dev libgmock-dev \
    catch2 doctest-dev \
    qtbase5-dev qtbase5-dev-tools \
    qt6-base-dev qt6-tools-dev-tools \
    libfmt-dev libspdlog-dev nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

# useful libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libeigen3-dev libprotobuf-dev protobuf-compiler libgrpc-dev libgrpc++-dev \
    bison flex \
    && rm -rf /var/lib/apt/lists/*

# LLVM/Clang 16
RUN wget https://apt.llvm.org/llvm.sh && chmod +x llvm.sh \
    && ./llvm.sh 16 all \
    && rm llvm.sh \
    && update-alternatives --install /usr/bin/cc cc /usr/bin/clang-16 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-16 100

# vcpkg
RUN git clone https://github.com/microsoft/vcpkg.git /opt/vcpkg && \
    /opt/vcpkg/bootstrap-vcpkg.sh -disableMetrics

# python virtual env
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
        gcovr PyGithub openai cmakeast

WORKDIR /workspace
CMD ["/bin/bash"]
