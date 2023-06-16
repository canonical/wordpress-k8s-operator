# Plugins

By default, the following WordPress plugins are installed with the latest version during the OCI
image build time. If the plugins are installed during runtime with
`juju config wordpress-k8s plugins=<plugin-slug>`, the plugin will also be installed to it's latest
version by default and may cause version differences between pods.
The wordpress-k8s charm supports multi-unit deployments. Therefore, installing plugins through UI
has been disabled and can only be installed through the plugins configuration. Please see
[Configurations](https://charmhub.io/wordpress-k8s/configure) section for more
information.

_\*The descriptions of the following plugins are taken from the WordPress plugin pages._

- [404page](https://wordpress.org/plugins/404page/): Custom 404 error page creator using the
  WordPress Page Editor.
- [akismet](https://wordpress.org/plugins/akismet/): Comment and contact form submissions spam
  checker for malicious content prevention.
- [all-in-one-event-calendar](https://wordpress.org/plugins/all-in-one-event-calendar/): Most
  advanced website calendar Responsive calendar system available for WordPress.
- [coschedule-by-todaymade](https://wordpress.org/plugins/coschedule-by-todaymade/): Schedulable
  calendar with remote synchronization service.
- [elementor](https://wordpress.org/plugins/elementor/): Intuitive visual website builder platform
  for WordPress.
- [essential-addons-for-elementor-lite](https://wordpress.org/plugins/essential-addons-for-elementor-lite/):
  Addons for website builder Elementor.
- [favicon-by-realfavicongenerator](https://wordpress.org/plugins/favicon-by-realfavicongenerator/):
  Favicon generator for desktop browsers, iPhone/iPad, Android devices, Windows 8 tablets and more.
- [feedwordpress](https://wordpress.org/plugins/feedwordpress/): Atom/RSS aggregator for WordPress by
  syndicating content from selected feeds to WordPress weblog.
- [genesis-columns-advanced](https://wordpress.org/plugins/genesis-columns-advanced/): Shortcode
  generator for every column configurations available with the column classes provided by the
  Genesis Framework.
- [line-break-shortcode](https://wordpress.org/plugins/line-break-shortcode/): Shortcode [br] enabler
  for line breaks that will not be filtered out by TinyMCE.
- [no-category-base-wpml](https://wordpress.org/plugins/no-category-base-wpml/): Mandatory
  ‘Category Base’ from category permalinks remover.
- [openid](https://wordpress.org/plugins/openid/): Authenticator that allows users to authenticate to
  websites without having to create a new password using OpenID standard.
- [openstack-objectstorage-k8s](https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/openstack-objectstorage-k8s):
  Automatic image, video, document and other media storage provider using Openstack Swift.
- [powerpress](https://wordpress.org/plugins/powerpress/): Podcast manager, enabling podcast
  management directly from your WordPress website.
- [post-grid](https://wordpress.org/plugins/post-grid/): Fully customizable post grid layout
  builder.
- [redirection](https://wordpress.org/plugins/redirection/): 301 redirect, 404 error tracker and
  manager.
- [relative-image-urls](https://wordpress.org/plugins/relative-image-urls/): Relative URL enabler
  that overrides WordPress’s absolute URL to file.
- [safe-svg](https://wordpress.org/plugins/safe-svg/): SVG uploader with SVG/XML vulnerability
  sanitizer.
- [show-current-template](https://wordpress.org/plugins/show-current-template/): A tool bar indicator
  showing the current template file name, the current theme name and included template files’ name.
- [simple-301-redirects](https://wordpress.org/plugins/simple-301-redirects/): Requests 301
  redirection enabler.
- [simple-custom-css](https://wordpress.org/plugins/simple-custom-css/): Plugin and Theme default
  styles CSS overrider.
- [so-widgets-bundle](https://wordpress.org/plugins/so-widgets-bundle/): Widgets bundle containing
  responsive elements for building website pages.
- [svg-support](https://wordpress.org/plugins/svg-support/): Media library SVG uploader and
  enabler.
- [syntaxhighlighter](https://wordpress.org/plugins/syntaxhighlighter/): Code syntax highlighter
  without losing formatting.
- [wordpress-importer](https://wordpress.org/plugins/wordpress-importer/): A WordPress export file
  importer, importing the following content: posts, pages, comments, comment meta, custom fields,
  post meta, categories, tags and terms from custom taxonomies and term meta, authors.
- [wordpress-launchpad-integration](https://git.launchpad.net/~canonical-sysadmins/wordpress-launchpad-integration/+git/wordpress-launchpad-integration):
  WordPress authenticator using Launchpad's OpenID provider.
- [wordpress-teams-integration](https://git.launchpad.net/~canonical-sysadmins/wordpress-teams-integration/+git/wordpress-teams-integration):
  This plugin implements OpenID teams in Wordpress.
- [wp-mastodon-share](https://wordpress.org/plugins/wp-mastodon-share/): Post sharing plugin to share
  a post to a user’s Mastodon instance.
- [wp-markdown](https://wordpress.org/plugins/wp-markdown/): Plugin to enable writing posts (of any
  post type) using the Markdown syntax.
- [wp-polls](https://wordpress.org/plugins/wp-polls/): Poll creator with customization via templates
  and css styles.
- [wp-font-awesome](https://wordpress.org/plugins/wp-font-awesome/): Shortcode handlers to allow
  embedding Font Awesome icon a website.
- [wp-lightbox-2](https://wordpress.org/plugins/wp-lightbox-2/): Responsive lightbox effects for
  website images and also creating lightbox effects for album/gallery photos on a WordPress blog.
- [wp-statistics](https://wordpress.org/plugins/wp-statistics/): GDPR compliant website statistics
  tool.
- [xubuntu-team-members](https://git.launchpad.net/~canonical-sysadmins/wordpress/+git/wp-plugin-xubuntu-team-members):
  Adds the role "Xubuntu Team member"