FROM node:22.22.2-alpine@sha256:8ea2348b068a9544dae7317b4f3aafcdc032df1647bb7d768a05a5cad1a7683f AS build
WORKDIR /app
RUN apk upgrade --no-cache
# npm 12.2 requires Node >=22.22.2; unused bundled package tools are not needed.
RUN wget -O /tmp/npm.tgz https://registry.npmjs.org/npm/-/npm-12.2.0.tgz \
    && node -e "const fs=require('fs'),crypto=require('crypto');if(crypto.createHash('sha512').update(fs.readFileSync('/tmp/npm.tgz')).digest('base64')!=='ZsJjKpTnlmSXOLLXiU1xDCzC4Wlok4IwZmh/aw2KUuXytU7q6qMv/cUT7MoeSf95Slwuw/lRXYefGzGCspHPNQ==')process.exit(1)" \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && mkdir /usr/local/lib/node_modules/npm \
    && tar -xzf /tmp/npm.tgz -C /usr/local/lib/node_modules/npm --strip-components=1 \
    && rm -f /tmp/npm.tgz /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx \
    && rm -rf /opt/yarn-v1.22.22 \
    && rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && npm --version
COPY deploy/patch-npm.mjs /tmp/patch-npm.mjs
RUN node /tmp/patch-npm.mjs && rm /tmp/patch-npm.mjs
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Public build configuration: relative same-origin API, never credentials.
ENV VITE_API_BASE_URL=/
RUN npm run lint && npm run build

FROM nginx:1.28.3-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236
# The upstream image pins r1 in apk/world; remove unused modules and replace
# the binary with Alpine's security-patched package of the same Nginx version.
RUN apk del nginx nginx-module-acme nginx-module-geoip nginx-module-image-filter nginx-module-njs nginx-module-xslt \
    && apk add --no-cache nginx=1.28.3-r7 \
    && apk upgrade --no-cache
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
USER 101:101
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
