# Static deploy of the prebuilt, committed site/ (run scripts/build_static.sh first). Nothing secret is copied.
FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY site/ /srv/
EXPOSE 8080
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
