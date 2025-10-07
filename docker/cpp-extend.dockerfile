FROM cpp-base:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libleptonica-dev \
    libudev-dev \
    libssl-dev \
    libprotobuf-dev protobuf-compiler \
    libssl-dev libcurl4-openssl-dev \
    libgtk-3-dev \
    libpoppler-glib-dev \
    libzip-dev \
    librsvg2-dev \
    gettext \
    libglib2.0-dev \
    libxml2-dev \
    bcc \
    libsqlite3-dev \
    libsdl2-dev libsdl2-image-dev \
    libegl1-mesa-dev \
    libx11-dev libxext-dev libxrandr-dev libxrender-dev libxinerama-dev libxcomposite-dev \
    libcairo2-dev \
    lua5.4 \
    liblua5.4-dev \
    libmbedtls-dev \
    libasio-dev \
    libre2-dev \
    libgoogle-glog-dev \
    nvidia-cuda-toolkit \
    libzmq3-dev \
    libfreetype6-dev \
    qt6-base-dev qt6-tools-dev qt6-tools-dev-tools \
    #qt6-svg-dev qt6-linguist-tools \
    libsuitesparse-dev libblas-dev liblapack-dev \
    qtbase5-dev qttools5-dev \
    libeigen3-dev \
    libgmp-dev \
    libasound2-dev \
    libgsl-dev \
    libfastcdr-dev \
    libglm-dev \
    libsnappy-dev \
    libpng-dev \
    pybind11-dev \
    libvolk2-dev \
    libmsgpack-dev \
    libccd-dev \
    libfcl-dev \
    libopenshot-audio-dev \
    doxygen \
    libproj-dev \
    libsfml-dev \
    libc-ares-dev \
    libfftw3-dev \
    libabsl-dev \
    libcap-dev \
    libdbus-1-dev \
    libpipewire-0.3-dev \
    ffmpeg \
    libopencv-dev \
    # TODO: test
    #libautomotive-dlt-dev \
    libsystemd-dev \
    graphviz \
    libbenchmark-dev \
    libvulkan-dev \
    vulkan-validationlayers-dev \
    spirv-tools \
    glslang-tools \
    spirv-headers \
    libhdf5-dev \
    spacenavd libspnav-dev \
    #libgtsam-dev \
    libva-dev \
    libjsoncpp-dev \
    libunwind-dev \
    python3-dev \
    swig \
    libminizip-dev \
    libleveldb-dev \
    libmysqlclient-dev \
    bpfcc-tools \
    #libbcc-dev \
    #linux-headers-$(uname -r) \
    libimlib2-dev \
    gperf \
    libdw-dev \
    binutils-dev \
    libdwarf-dev \
    #assimp \
    libassimp-dev \
    libuv1-dev \
    libavif-dev \
    #libwt-dev \
    coinor-libipopt-dev \
    libsimbody-dev \
    #libdart6.6-dev \
    libbullet-dev \
    libfreeimage-dev \
    libopenal-dev \
    libavdevice-dev \
    libogre-1.9-dev \
    #libogre-1.9-RTShaderSystem-dev \
    libusb-1.0-0-dev \
    libtinyxml-dev \
    libtinyxml2-dev \
    libtar-dev \
    libgoogle-perftools-dev \
    libgts-dev \
    #player player-dev \
    libsdformat9-dev \
    liborc-0.4-dev \
    libuhd-dev uhd-host \
    libsdl2-mixer-dev \
    libpostproc-dev \
    meson \
    libarchive-dev \
    libglfw3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

CMD ["/bin/bash"]
