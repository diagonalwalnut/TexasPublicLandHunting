#!/usr/bin/env bash
# Obtain and install a Let's Encrypt certificate ON THE INSTANCE, then add the
# port-443 vhost and a daily renewal hook. Run this AFTER DNS for $DOMAIN points
# at this instance's public IP (otherwise HTTP-01 validation will fail).
#
#   ssh ec2-user@HOST 'sudo bash /opt/tplh/setup-tls.sh'
set -euo pipefail

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

: "${DOMAIN:?}" "${ADMIN_EMAIL:?}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
ACME_ROOT="${ACME_ROOT:-/var/www/tplh/acme}"
DOMAIN_ALIASES="${DOMAIN_ALIASES:-}"

if [[ $EUID -ne 0 ]]; then echo "FATAL: run as root (use sudo)"; exit 1; fi
log() { printf '==> %s\n' "$*"; }

log "installing certbot + mod_ssl"
dnf -y install certbot mod_ssl

# Build -d args (primary + any aliases that already resolve to us).
domain_args=(-d "$DOMAIN")
for a in $DOMAIN_ALIASES; do domain_args+=(-d "$a"); done

log "requesting certificate for: $DOMAIN $DOMAIN_ALIASES"
certbot certonly --webroot -w "$ACME_ROOT" \
  "${domain_args[@]}" \
  -m "$ADMIN_EMAIL" --agree-tos --non-interactive --keep-until-expiring

LIVE="/etc/letsencrypt/live/$DOMAIN"
[[ -f "$LIVE/fullchain.pem" ]] || { echo "FATAL: certificate not issued"; exit 1; }

log "writing port-443 vhost"
alias_line=""
[[ -n "$DOMAIN_ALIASES" ]] && alias_line="    ServerAlias ${DOMAIN_ALIASES}"
cat > /etc/httpd/conf.d/tplh-ssl.conf <<CONF
<VirtualHost *:443>
    ServerName ${DOMAIN}
${alias_line}
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

# Daily renewal with an Apache reload hook (certbot stores the webroot params).
cat > /etc/cron.d/tplh-certbot <<'CRON'
# Renew Let's Encrypt certs for TPLH and reload Apache on success.
0 3 * * * root certbot renew -q --deploy-hook "systemctl reload httpd"
CRON

log "HTTPS is live: https://${DOMAIN}/"
log "The app's .htaccess now upgrades any HTTP request to HTTPS."
