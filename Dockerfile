FROM debian:12.9-slim

ENV LANG C.UTF-8

RUN apt-get update \
    && apt-get install -y \
        bzip2 \
        file \
        gawk \
        git \
        make \
        perl \
        python3-distutils \
        python3-zstandard \
        rsync \
        unzip \
        wget \
    && apt-get clean

COPY imagebuilder.py /imagebuilder.py

ENTRYPOINT [ "/imagebuilder.py" ]
