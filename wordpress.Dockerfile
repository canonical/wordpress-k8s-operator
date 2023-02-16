FROM ubuntu:20.04

ARG VERSION=5.9.3
ENV APACHE_CONFDIR=/etc/apache2
ENV APACHE_ENVVARS=/etc/apache2/envvars

LABEL maintainer="wordpress-charmers@lists.launchpad.net"

# Update all packages, remove cruft, install required packages, configure apache
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections && \
    apt-get update \
        && apt-get --purge autoremove -y \
        && apt-get install -y apache2 \
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
            unzip && \
        sed -ri 's/^export ([^=]+)=(.*)$/: ${\1:=\2}\nexport \1/' "$APACHE_ENVVARS" && \
        . "$APACHE_ENVVARS" && \
        for dir in "$APACHE_LOCK_DIR" "$APACHE_RUN_DIR" "$APACHE_LOG_DIR";  \
          do  \
            rm -rvf "$dir";  \
            mkdir -p "$dir";  \
            chown "$APACHE_RUN_USER:$APACHE_RUN_GROUP" "$dir";  \
            chmod u=rwx,g=rx,o=rx "$dir"; \
        done && \
        ln -sfT /dev/stdout "$APACHE_LOG_DIR/other_vhosts_access.log" && \
        chown -R --no-dereference "$APACHE_RUN_USER:$APACHE_RUN_GROUP" "$APACHE_LOG_DIR"

# Configure PHP and apache2 - mod_php requires us to use mpm_prefork
COPY ./files/docker-php.conf $APACHE_CONFDIR/conf-available/docker-php.conf
COPY ./files/docker-php-swift-proxy.conf $APACHE_CONFDIR/conf-available/docker-php-swift-proxy.conf
# Configure apache 2 to enable /server-status endpoint
COPY ./files/apache2.conf $APACHE_CONFDIR/apache2.conf
# To allow logging to container and logfile
COPY ./files/000-default.conf $APACHE_CONFDIR/sites-available/000-default.conf

RUN a2enconf docker-php && \
    a2dismod mpm_event && \
    a2enmod headers && \
    a2enmod mpm_prefork && \
    a2enmod proxy && \
    a2enmod proxy_http && \
    a2enmod rewrite && \
    a2enmod ssl

RUN curl -sSOL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && \
    chmod +x wp-cli.phar && \
    mv wp-cli.phar /usr/local/bin/wp && \
    mkdir /var/www/.wp-cli && \
    chown www-data:www-data /var/www/.wp-cli

RUN chown -R www-data:www-data /var/www/html

USER www-data:www-data

WORKDIR /var/www/html

RUN wp core download --version=${VERSION}

RUN set -e; \
    cd ./wp-content/plugins; \
    for plugin in  \
        404page \
        all-in-one-event-calendar \
        coschedule-by-todaymade \
        elementor \
        essential-addons-for-elementor-lite \
        favicon-by-realfavicongenerator \
        feedwordpress \
        fruitful-shortcodes \
        genesis-columns-advanced \
        line-break-shortcode \
        no-category-base-wpml \
        post-grid \
        powerpress \
        redirection \
        relative-image-urls \
        rel-publisher \
        safe-svg \
        show-current-template \
        simple-301-redirects \
        simple-custom-css \
        social-media-buttons-toolbar \
        so-widgets-bundle \
        svg-support \
        syntaxhighlighter \
        wordpress-importer \
        wordpress-seo \
        wp-font-awesome \
        wp-lightbox-2 \
        wp-markdown \
        wp-mastodon-share \
        wp-polls \
        wp-statistics ;\
    do \
        curl -sSL "https://downloads.wordpress.org/plugin/${plugin}.latest-stable.zip" -o "${plugin}.zip"; \
        unzip "${plugin}.zip"; \
        rm "${plugin}.zip"; \
    done; \
    curl -sSL "https://downloads.wordpress.org/plugin/openid.3.5.0.zip" -o "openid.zip"; \
    unzip "openid.zip"; \
    rm "openid.zip"; \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress-launchpad-integration/+git/wordpress-launchpad-integration wordpress-launchpad-integration; \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/openstack-objectstorage-k8s openstack-objectstorage-k8s; \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress-teams-integration/+git/wordpress-teams-integration wordpress-teams-integration; \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-plugin-xubuntu-team-members xubuntu-team-members; \
    rm -rf */.git

RUN cd ./wp-content/themes && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-fruitful fruitful && \
    git clone https://git.launchpad.net/~canonical-sysadmins/ubuntu-community-webthemes/+git/light-wordpress-theme light-wordpress-theme && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-mscom mscom && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-thematic thematic && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-twentyeleven twentyeleven && \
    git clone https://git.launchpad.net/~canonical-sysadmins/ubuntu-cloud-website/+git/ubuntu-cloud-website ubuntu-cloud-website && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-community ubuntu-community && \
    git clone https://git.launchpad.net/~canonical-sysadmins/ubuntu-community-wordpress-theme/+git/ubuntu-community-wordpress-theme ubuntu-community-wordpress-theme && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-fi ubuntu-fi && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntu-light ubuntu-light && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-ubuntustudio-wp ubuntustudio-wp && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-launchpad launchpad && \
    git clone https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-theme-xubuntu-website xubuntu-website && \
    rm -rf */.git

EXPOSE 80
