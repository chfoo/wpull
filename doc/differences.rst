==================================
Differences between Wpull and Wget
==================================

In most cases, Wpull can be substituted with Wget easily. However, some options may not be implemented yet. This section describes the reasons for option differences.


Missing in Wpull
================

* ``--background``
* ``--execute``
* ``--config``
* ``--spider``
* ``--ignore-case``
* ``--ask-password``
* ``--unlink``
* ``--method``
* ``--body-data``
* ``--body-file``
* ``--auth-no-challenge``: Temporarily on by default, but specifying the option is not yet available. Digest authentication is not yet supported.
* ``--no-passive-ftp``
* ``--mirror``
* ``--strict-comments``: No plans for support of this option.
* ``--regex-type=posix``: No plans to support posix regex.
* Features greater than Wget 1.15.


Missing in Wget
===============

* ``--plugin-plugin``: This provides scripting hooks.
* ``--plugin-args``
* ``--database``: Enables the use of the on-disk database.
* ``--database-uri``
* ``--concurrent``: Allows changing the number of downloads that happen at once.
* ``--debug-console-port``
* ``--debug-manhole``
* ``--ignore-fatal-errors``
* ``--monitor-disk``: Avoids filling the disk.
* ``--monitor-memory``
* ``--very-quiet``
* ``--ascii-print``: Force replaces Unicode text with escaped values for environments that are ASCII only.
* ``--http-proxy``:
* ``--https-proxy``
* ``--proxy-domains``
* ``--proxy-exclude-domains``
* ``--proxy-hostnames``
* ``--proxy-exclude-hostnames``
* ``--retry-dns-error``: Wget considers DNS errors as non-recoverable.
* ``--session-timeout``: Abort downloading infinite MP3 streams.
* ``--no-skip-getaddrinfo``
* ``--no-robots``: Wpull is designed for archiving.
* ``--http-compression`` (gzip, deflate, & raw deflate)
* ``--html-parser``: HTML parsing libraries have many trade-offs. Pick any two: small, fast, reliable.
* ``--link-extractors``
* ``--escaped-fragment``: Try to force HTML rendering instead of Javascript.
* ``--strip-session-id``
* ``--no-strong-crypto``
* ``--no-use-internal-ca-certs``
* ``--warc-append``
* ``--warc-move``: Move WARC files out of the way for resuming a crashed crawl.
* ``--page-requisites-level``: Prevent infinite downloading of misconfurged server resources such as HTML served under a image.
* ``--sitemaps``: Discover more URLs.
* ``--hostnames``: Wget simply matches the endings when using ``--domains`` instead of matching each part of the hostname.
* ``--exclude-hostnames``
* ``--span-hosts-allow``: Allow fetching things such as images hosted on another domain.
* ``--no-strong-redirects``
* ``--proxy-server``
* ``--proxy-server-address``
* ``--proxy-server-port``
* ``--youtube-dl``
* ``--youtube-dl-exe``
