#!/usr/bin/env bash
# Issue the ORIGIN TLS certificate ON THE INSTANCE (Tier 3) and add the port-443
# vhost + a daily renewal hook. This cert secures the CloudFront -> origin hop and
# is for API_ORIGIN_DOMAIN only. The PUBLIC certificate (for DOMAIN / www) is an
# ACM cert on CloudFront, created by provision-cdn.sh.
#
# Run AFTER API_ORIGIN_DOMAIN's A record points at this instance's Elastic IP:
#   ssh ec2-user@HOST 'sudo bash /opt/tplh/setup-tls.sh'
set -euo pipefail

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

ORIGIN_DOMAIN="${API_ORIGIN_DOMAIN:-}"
[[ -n "$ORIGIN_DOMAIN" ]] || { echo "FATAL: API_ORIGIN_DOMAIN not set in config.env"; exit 1; }
: "${ADMIN_EMAIL:?}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
ACME_ROOT="${ACME_ROOT:-/var/www/tplh/acme}"

if [[ $EUID -ne 0 ]]; then echo "FATAL: run as root (use sudo)"; exit 1; fi
log() { printf '==> %s\n' "$*"; }

log "installing certbot + mod_ssl"
dnf -y install certbot mod_ssl

log "requesting certificate for origin: $ORIGIN_DOMAIN"
certbot certonly --webroot -w "$ACME_ROOT" \
  -d "$ORIGIN_DOMAIN" \
  -m "$ADMIN_EMAIL" --agree-tos --non-interactive --keep-until-expiring

LIVE="/etc/letsencrypt/live/$ORIGIN_DOMAIN"
[[ -f "$LIVE/fullchain.pem" ]] || { echo "FATAL: certificate not issued"; exit 1; }

log "writing port-443 origin vhost"
cat > /etc/httpd/conf.d/tplh-ssl.conf <<CONF
<VirtualHost *:443>
    ServerName ${ORIGIN_DOMAIN}
    DocumentRoot ${APP_ROOT}/current

    SSLEngine on
    SSLCertificateFile ${LIVE}/fullchain.pem
    SSLCertificateKeyFile ${LIVE}/privkey.pem

    <Directory ${APP_ROOT}/current>
        AllowOverride All
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>

    ErrorLog logs/tplh_ssl_error.log
    CustomLog logs/tplh_ssl_access.log combined
</VirtualHost>
CONF

log "reloading Apache"
apachectl configtest
systemctl reload httpd

cat > /etc/cron.d/tplh-certbot <<'CRON'
# Renew Let's Encrypt origin cert for TPLH and reload Apache on success.
0 3 * * * root certbot renew -q --deploy-hook "systemctl reload httpd"
CRON

log "Origin HTTPS is live: https://${ORIGIN_DOMAIN}/ (used by CloudFront)."
log "Set the CloudFront /api origin to ${ORIGIN_DOMAIN} with HTTPS-only (provision-cdn.sh does this)."
