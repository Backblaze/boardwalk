FROM python:3.10 AS build
WORKDIR /build
COPY . .
RUN make build

FROM python:3.10-slim
COPY --from=build /build/dist ./dist
RUN python3 -m pip install ./dist/boardwalk-*.whl && mkdir /var/boardwalk && rm -rf ./dist
WORKDIR /var/boardwalk
ENTRYPOINT ["python3", "-m"]
