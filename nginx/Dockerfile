FROM nginx:alpine

# Copy custom configuration
COPY default.conf.template /etc/nginx/templates/

# Copy loading page as index.html
COPY loading.html /usr/share/nginx/html/index.html

# Expose port 80
EXPOSE 80

# Use default nginx entrypoint
CMD ["nginx", "-g", "daemon off;"]
