FROM docker.io/library/debian:13-slim

# Install CA certificates using the signed Debian package repositories.
RUN apt-get \
      -o APT::Update::Error-Mode=any \
      -o Acquire::http::Pipeline-Depth=0 \
      -o Acquire::Retries=2 \
      update && \
    apt-get \
      -o Acquire::Retries=2 \
      install -y --no-install-recommends ca-certificates && \
    test -s /etc/ssl/certs/ca-certificates.crt

# Switch the official Debian 13 repositories to HTTPS and install build dependencies.
RUN sed -i \
      's|URIs: http://|URIs: https://|g' \
      /etc/apt/sources.list.d/debian.sources && \
    ! grep -q 'URIs: http://' \
      /etc/apt/sources.list.d/debian.sources && \
    apt-get \
      -o APT::Update::Error-Mode=any \
      -o Acquire::Retries=2 \
      update && \
    DEBIAN_FRONTEND=noninteractive apt-get \
      -o Acquire::Retries=2 \
      install -y --no-install-recommends \
      bc bison build-essential cmake cpio device-tree-compiler file flex \
      git kmod libelf-dev libncurses-dev libssl-dev pkg-config python3 python3-pip rsync squashfs-tools \
      u-boot-tools unzip wget xz-utils && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/fre3nder-x2000
RUN chmod 0755 /usr/local/bin/fre3nder-x2000

ENTRYPOINT ["/usr/local/bin/fre3nder-x2000"]