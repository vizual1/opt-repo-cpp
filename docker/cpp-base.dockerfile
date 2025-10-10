FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential cmake git ninja-build pkg-config wget curl ca-certificates ccache meson \
    qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
    qt6-base-dev qt6-tools-dev-tools \
    libboost-all-dev libbenchmark-dev \
    libgtest-dev libgmock-dev libgflags-dev libgoogle-glog-dev \
    libeigen3-dev libsdl2-dev \
    libprotobuf-dev protobuf-compiler \
    libgrpc-dev libgrpc++-dev \
    libopencv-dev \
    catch2 doctest-dev \
    python3 python3-pip python3-venv \
    unzip zip tar xz-utils perl software-properties-common gnupg \
    gdb valgrind strace lsof time binutils linux-tools-common linux-tools-generic \
    cppcheck doxygen graphviz lcov \
    zlib1g-dev libssl-dev libcurl4-openssl-dev \
    liblz4-dev libzstd-dev \
    extra-cmake-modules cmake-data gettext \
    bison flex libreadline-dev \
    libgl1-mesa-dev libx11-dev libxext-dev libxft-dev \
    libxinerama-dev libxi-dev libxrandr-dev libxrender-dev \
    libxcursor-dev libxcomposite-dev libxdamage-dev \
    libfontconfig1-dev libxkbcommon-dev libxkbcommon-x11-dev \
    libdbus-1-dev gfortran \
    libtool autoconf automake \
    libudev-dev libcap-dev libmount-dev \
    libselinux1-dev libseccomp-dev \
    liblzma-dev zstd libsystemd-dev \
    libglib2.0-dev libgirepository1.0-dev gobject-introspection \
    libxml2-dev libatspi2.0-dev at-spi2-core \
    libfmt-dev libspdlog-dev \
    nlohmann-json3-dev \
    libsqlite3-dev \
    libpng-dev \
    libyaml-cpp-dev \
    libopenblas-dev \
    && wget https://apt.llvm.org/llvm.sh && chmod +x llvm.sh \
    && ./llvm.sh 16 all \
    && rm llvm.sh \
    && pip3 install gcovr conan \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/microsoft/vcpkg.git /opt/vcpkg && \
    cd /opt/vcpkg && \
    ./bootstrap-vcpkg.sh -disableMetrics
ENV PATH="/opt/vcpkg:$PATH"
RUN vcpkg install doctest cpr range-v3 magic-enum sdl3 --clean-after-build

RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang-16 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-16 100

RUN apt-get update && apt-get install -y --no-install-recommends python3-venv \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      PyGithub \
      openai \
      cmakeast
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace

CMD ["/bin/bash"]
