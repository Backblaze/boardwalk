FROM python:3.11 AS build
WORKDIR /build
COPY . .
RUN python3 -m pip install --user pipx \
    && PATH=PATH:/root/.local/bin pipx install poetry \
    && PATH=PATH:/root/.local/bin poetry build

FROM python:3.11-slim
COPY --from=build /build/dist ./dist
ENV DEBIAN_FRONTEND=noninteractive
RUN groupadd -g 1000 not_root && useradd -u 1000 -g 1000 not_root \
    && apt-get -y update \
    && apt-get -y install aptitude \
    && apt-get -y dist-upgrade \
    && apt-get -y autoremove \
    && apt-get -y autoclean \
    && apt-get -y clean \
    && aptitude -y purge '~o' \
    && apt-get -y remove --purge aptitude \
    && python3 -m pip install ./dist/boardwalk-*.whl \
    && rm -rf ./dist

USER not_root
WORKDIR /var/boardwalk
ENTRYPOINT ["python3", "-m"]
