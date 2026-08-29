# Imagen oficial de Playwright: trae Chromium y sus dependencias ya instaladas,
# con soporte multi-arquitectura (x64 y ARM64).
FROM mcr.microsoft.com/playwright:v1.48.2-jammy

ENV NODE_ENV=production
WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY server.mjs ./

EXPOSE 3000
# El navegador no debe correr como root en esta imagen.
USER pwuser
CMD ["node", "server.mjs"]
