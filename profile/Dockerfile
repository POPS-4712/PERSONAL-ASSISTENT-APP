# Servicio de perfil: solo Node, sin dependencias. Multi-arquitectura.
FROM node:22-alpine

ENV NODE_ENV=production
WORKDIR /app

COPY server.mjs ./
COPY public ./public

EXPOSE 7777
USER node
CMD ["node", "server.mjs"]
