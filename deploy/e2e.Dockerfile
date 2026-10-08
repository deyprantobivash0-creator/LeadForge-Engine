FROM mcr.microsoft.com/playwright:v1.58.2-noble@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d
WORKDIR /tests
ENV E2E_EVIDENCE_DIR=/evidence
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/playwright.config.js ./
COPY frontend/e2e/ ./e2e/
CMD ["npx", "--no-install", "playwright", "test"]
