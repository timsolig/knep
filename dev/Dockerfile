# Utvecklingsmiljö för Claude Code på Raspberry Pi (arm64).
# Claude arbetar bara i /work (repot) och /data (radararkivet).
FROM debian:bookworm-slim

ARG UID=1000
ARG GID=1000

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git tmux build-essential less procps unzip \
 && install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g "$GID" dev && useradd -m -u "$UID" -g "$GID" -s /bin/bash dev
USER dev
ENV PATH=/home/dev/.local/bin:$PATH

# Installera från hemkatalogen, inte från / (installeraren söker igenom katalogen den startas i)
WORKDIR /home/dev
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && curl -fsSL https://claude.ai/install.sh | bash

WORKDIR /work
CMD ["sleep", "infinity"]
