FROM traefik:v3.7.14@sha256:e849695bc5c317da0cec22bfee4794fd9e15871fe554f864d31b625983e883ff
# Apply the Alpine package fix identified by the local offline scan.
RUN apk upgrade --no-cache zlib
USER 65532:65532
