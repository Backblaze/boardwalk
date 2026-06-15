FROM docker.io/python:3.13-alpine3.24 AS build
WORKDIR /build
COPY . .
RUN apk update && \
    apk upgrade && \
    pip install --root-user-action ignore uv==0.11.21 && \
    uv build

FROM docker.io/python:3.13-alpine3.24
COPY --from=build /build/dist ./dist
RUN adduser -D -u 1000 not-root && \
    apk update && \
    apk upgrade && \
    pip install --root-user-action ignore ./dist/boardwalk-*.whl && \
    rm -rf ./dist

USER not_root
WORKDIR /var/boardwalk
ENTRYPOINT ["python3", "-m"]
