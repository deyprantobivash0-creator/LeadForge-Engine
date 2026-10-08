FROM mcr.microsoft.com/playwright:v1.58.2-noble@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d
RUN npm install --prefix /tmp/leadforge-browser --ignore-scripts --no-audit --no-fund playwright@1.58.2 \
    && node -e "const p=require('/tmp/leadforge-browser/node_modules/playwright/package.json'); if(p.version!=='1.58.2')process.exit(1)" \
    && npm ls --prefix /tmp/leadforge-browser --all
