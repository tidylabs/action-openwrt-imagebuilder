FROM debian:13.1-slim AS base

ENV LANG C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bzip2 \
        file \
        gawk \
        git \
        make \
        perl \
        patch \
        python3 \
        python3-pip \
        python3-setuptools \
        rsync \
        unzip \
        wget \
    && apt-get clean

FROM base AS dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-client \
        python3-build \
        python3-venv \
    && apt-get clean

FROM dev AS build

COPY . /openwrt_tools

RUN python3 -m build --outdir /dist /openwrt_tools

FROM base AS action

RUN --mount=type=bind,target=/dist,source=/dist,from=build \
    python3 -m pip install --break-system-packages /dist/openwrt_tools*.whl

ENTRYPOINT [ "openwrt-imagebuilder" ]
