# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /radar ./cmd/server

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=build /radar /radar
EXPOSE 8080
USER nobody:nobody
ENV RADAR_WEBHOOK_SECRET=""
ENTRYPOINT ["/radar", "-addr", ":8080"]
