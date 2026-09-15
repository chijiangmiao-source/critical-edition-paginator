# 前端镜像：构建静态资源，由 nginx 提供并把 /api 反代到后端
FROM node:22-alpine AS build

WORKDIR /srv
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/web-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/dist /usr/share/nginx/html
EXPOSE 80
