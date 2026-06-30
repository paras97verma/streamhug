# Build Stage
FROM node:20-slim AS build-stage
WORKDIR /app

# Copy package files and install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ .
# We build using Vite; make sure VITE_API_URL is empty so it uses relative paths (routed by Nginx)
ENV VITE_API_URL=""
RUN npm run build

# Production Stage
FROM nginx:alpine AS production-stage

# Copy Nginx custom configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
