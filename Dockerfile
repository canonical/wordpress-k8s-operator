ARG DIST_RELEASE
FROM ubuntu:${DIST_RELEASE}
ARG DIST_RELEASE
ARG VERSION

LABEL maintainer="wordpress-charmers@lists.launchpad.net"
LABEL org.label-schema.version=${DIST_RELEASE}-${VERSION}

# HTTPS_PROXY used when we RUN curl to download Wordpress itself
ARG BUILD_DATE
ARG HTTPS_PROXY
ARG VERSION

# Used by Launchpad OCI Recipe to tag version
LABEL org.label-schema.version=${VERSION:-5.6}

# Launchpad OCI image builds don't support dynamic arg parsing. Skip until
# https://bugs.launchpad.net/launchpad/+bug/1902010 is resolved.
#LABEL org.label-schema.build-date=${BUILD_DATE}

ENV APACHE_CONFDIR=/etc/apache2
ENV APACHE_ENVVARS=/etc/apache2/envvars

# Avoid interactive prompts
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Update all packages, remove cruft, install required packages, configure apache
RUN apt-get update && apt-get -y dist-upgrade \
        && apt-get --purge autoremove -y \
        && apt-get install -y apache2 \
            bzr \
            curl \
            git \
            libapache2-mod-php \
            libgmp-dev \
            php \
            php-curl \
            php-gd \
            php-gmp \
            php-mysql \
            php-symfony-yaml \
            php-xml \
            pwgen \
            python3 \
            python3-yaml \
            ssl-cert \
        && sed -ri 's/^export ([^=]+)=(.*)$/: ${\1:=\2}\nexport \1/' "$APACHE_ENVVARS" \
        && . "$APACHE_ENVVARS" \
        && for dir in "$APACHE_LOCK_DIR" "$APACHE_RUN_DIR" "$APACHE_LOG_DIR"; do rm -rvf "$dir"; mkdir -p "$dir"; chown "$APACHE_RUN_USER:$APACHE_RUN_GROUP" "$dir"; chmod 777 "$dir";  done \
        && ln -sfT /dev/stderr "$APACHE_LOG_DIR/error.log" \
        && ln -sfT /dev/stdout "$APACHE_LOG_DIR/access.log" \
        && ln -sfT /dev/stdout "$APACHE_LOG_DIR/other_vhosts_access.log" \
        && chown -R --no-dereference "$APACHE_RUN_USER:$APACHE_RUN_GROUP" "$APACHE_LOG_DIR"

# Configure PHP and apache2 - mod_php requires us to use mpm_prefork
COPY ./image-builder/files/docker-php.conf $APACHE_CONFDIR/conf-available/docker-php.conf
COPY ./image-builder/files/docker-php-swift-proxy.conf $APACHE_CONFDIR/conf-available/docker-php-swift-proxy.conf
RUN a2enconf docker-php \
    && a2dismod mpm_event \
    && a2enmod headers \
    && a2enmod mpm_prefork \
    && a2enmod proxy \
    && a2enmod proxy_http \
    && a2enmod rewrite

# Install the main Wordpress code, this will be our only site so /var/www/html is fine
RUN curl -o wordpress.tar.gz -fSL "https://wordpress.org/wordpress-${VERSION}.tar.gz" \
    && tar -xzf wordpress.tar.gz -C /usr/src/ \
    && rm wordpress.tar.gz \
    && chown -R www-data:www-data /usr/src/wordpress \
    && rm -rf /var/www/html \
    && mv /usr/src/wordpress /var/www/html

COPY ./image-builder/files/ /files/
COPY ./image-builder/src/fetcher.py .
RUN mkdir -p /files/themes /files/plugins
RUN ./fetcher.py
# Copy our collected themes and plugins into the appropriate paths
RUN cp -r /files/plugins/* /var/www/html/wp-content/plugins/
RUN cp -r /files/themes/* /var/www/html/wp-content/themes/

# wp-info.php contains template variables which our ENTRYPOINT script will populate
RUN install -D /files/wp-info.php /var/www/html/wp-info.php
RUN install -D /files/wp-config.php /var/www/html/wp-config.php
RUN chown -R www-data:www-data /var/www/html

# Copy our helper scripts and their wrapper into their own directory
RUN install /files/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN install -t /srv/wordpress-helpers/ -D /files/_add_option.php \
    /files/_enable_plugin.php \
    /files/_get_option.php \
    /files/plugin_handler.py \
    /files/ready.sh

# Make the wrapper executable
RUN chmod 0755 /srv/wordpress-helpers/plugin_handler.py
RUN chmod 0755 /srv/wordpress-helpers/ready.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

RUN rm -r /files

# Port 80 only, TLS will terminate elsewhere
EXPOSE 80

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD apachectl -D FOREGROUND
