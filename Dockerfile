FROM python:3.10 AS build
WORKDIR /build
COPY . .
RUN make build

FROM python:3.10-slim
COPY --from=build /build/dist ./dist
RUN groupadd -g 1000 not_root && useradd -u 1000 -g 1000 not_root \
    && python3 -m pip install ./dist/boardwalk-*.whl \
    && rm -rf ./dist

USER not_root
WORKDIR /var/boardwalk
ENTRYPOINT ["python3", "-m"]
