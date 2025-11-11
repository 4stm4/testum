FROM nginx:alpine

# Copy loading page
COPY index.html /usr/share/nginx/html/index.html

# Simple nginx config - just serve static files
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
