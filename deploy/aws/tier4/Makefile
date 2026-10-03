# SAM "makefile" build method for the Bref PHP function.
# `sam build` invokes the build-<LogicalId> target with ARTIFACTS_DIR set to the
# directory that becomes the Lambda package root (/var/task at runtime). We copy
# the source + composer manifests there and install production dependencies, so
# vendor/ ships with the function. Handler src/index.php then requires
# ../vendor/autoload.php (i.e. /var/task/vendor/autoload.php).

build-ApiFunction:
	cp -r src "$(ARTIFACTS_DIR)/src"
	cp composer.json composer.lock "$(ARTIFACTS_DIR)/"
	cd "$(ARTIFACTS_DIR)" && composer install --no-dev --optimize-autoloader --no-interaction --no-progress
