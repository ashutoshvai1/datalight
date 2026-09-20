FROM node:24-alpine AS build
WORKDIR /app
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN pnpm build
FROM nginx:1.28-alpine
ENV MAX_UPLOAD_BYTES=268435456
COPY --chmod=755 apps/web/upload-limit.envsh /docker-entrypoint.d/19-upload-limit.envsh
COPY apps/web/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
