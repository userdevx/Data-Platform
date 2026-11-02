FROM python:3.12-slim-trixie@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libtcl8.6=8.6.16+dfsg-1 \
        libtk8.6=8.6.16-1 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -c 'import tkinter; print("BUILD_TK_OK", tkinter.TkVersion)' \
    && mkdir -p /usr/local/share \
    && dpkg-query -W -f='${Package}=${Version}\n' \
        libtcl8.6 libtk8.6 \
        > /usr/local/share/builder-tk-packages.txt

RUN groupadd --gid 10001 builder \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --no-create-home \
        --home-dir /nonexistent \
        --shell /usr/sbin/nologin builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
USER 10001:10001
CMD ["python3"]
