FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build git wget curl unzip pkg-config \
    gdb valgrind lcov python3 python3-pip \
    software-properties-common gnupg \
    && wget https://apt.llvm.org/llvm.sh && chmod +x llvm.sh \
    && ./llvm.sh 16 all \
    && rm llvm.sh \
    && pip3 install gcovr \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang-16 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-16 100 \
    && update-alternatives --install /usr/bin/clang clang /usr/bin/clang-16 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-16 100

RUN apt-get update && apt-get install -y --no-install-recommends python3-venv \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      PyGithub \
      openai

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace

ENV CMAKE_C_COMPILER=clang-16
ENV CMAKE_CXX_COMPILER=clang++-16
ENV CMAKE_CXX_FLAGS="-fprofile-instr-generate -fcoverage-mapping -O0 -g"
ENV CMAKE_EXE_LINKER_FLAGS="-fprofile-instr-generate"

CMD ["/bin/bash"]
