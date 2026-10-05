# SAM "makefile" build method for the Bref PHP function.
# `sam build` invokes the build-<LogicalId> target with ARTIFACTS_DIR set to the
# directory that becomes the Lambda package root (/var/task at runtime). We copy
# the source + composer manifests there and install production dependencies, so
# vendor/ ships with the function. Handler src/index.php then requires
# ../vendor/autoload.php (i.e. /var/task/vendor/autoload.php).

build-ApiFunction:
	@command -v php >/dev/null 2>&1 || { \
	  echo "php is not installed, so composer cannot run." >&2; \
	  echo "On AWS CloudShell:" >&2; \
	  echo "  sudo dnf install -y php-cli php-xml php-mbstring php-sodium unzip" >&2; \
	  echo "Then rerun sam build from deploy/aws/tier4." >&2; \
	  exit 127; \
	}
	@command -v composer >/dev/null 2>&1 || { \
	  echo "composer is not on PATH. From deploy/aws/tier4:" >&2; \
	  echo "  mkdir -p \"$$HOME/bin\"" >&2; \
	  echo "  php -r \"copy('https://getcomposer.org/installer','composer-setup.php');\"" >&2; \
	  echo "  php composer-setup.php --install-dir=\"$$HOME/bin\" --filename=composer && rm composer-setup.php" >&2; \
	  echo "  export PATH=\"$$HOME/bin:$$PATH\"" >&2; \
	  exit 127; \
	}
	cp -r src "$(ARTIFACTS_DIR)/src"
	cp composer.json composer.lock "$(ARTIFACTS_DIR)/"
	cd "$(ARTIFACTS_DIR)" && composer install --no-dev --optimize-autoloader --no-interaction --no-progress
