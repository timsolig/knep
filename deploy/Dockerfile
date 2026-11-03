# Driften (arm64): verktygen för att checka ut och köra knep. Själva koden ligger inte i
# bilden; drift.sh följer main på GitHub och installerar varje ny commit i volymen /srv/knep.
# Bilden behöver bara byggas om när den här filen eller drift.sh ändras.
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
# build-essential: pysteps kompileras när uv.lock byter version; libgomp1: OpenMP i pysteps
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential ca-certificates curl git libgomp1 \
 && rm -rf /var/lib/apt/lists/*
COPY deploy/drift.sh /usr/local/bin/knep-drift
RUN useradd -m knep && install -d -o knep /srv/knep
USER knep
ENV UV_COMPILE_BYTECODE=1
WORKDIR /srv/knep
CMD ["knep-drift"]
