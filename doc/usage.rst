=====
Usage
=====


Intro
=====

Wpull is a command line oriented program much like Wget. It is
non-interactive and requires all options to specified on start up. If
you are not familiar with Wget, please see the `Wikipedia article on
Wget <https://en.wikipedia.org/wiki/Wget>`_.



Example Commands
================

.. ⬇ Please keep these examples in sync with the README file. ⬇

To download the About page of Google.com::

    wpull google.com/about

To archive a website::

    wpull billy.blogsite.example \
        --warc-file blogsite-billy \
        --no-check-certificate \
        --no-robots --user-agent "InconspiuousWebBrowser/1.0" \
        --wait 0.5 --random-wait --waitretry 600 \
        --page-requisites --recursive --level inf \
        --span-hosts-allow linked-pages,page-requisites \
        --escaped-fragment --strip-session-id \
        --sitemaps \
        --reject-regex "/login\.php" \
        --tries 3 --retry-connrefused --retry-dns-error \
        --timeout 60 --session-timeout 21600 \
        --delete-after --database blogsite-billy.db \
        --quiet --output-file blogsite-billy.log

Wpull can also be invoked using::

    python3 -m wpull


Stopping & Resuming
===================

To gracefully stop Wpull, press CTRL+C (or send SIGINT). Wpull will quit
once the current download has finished. To stop immediately, press CTRL+C
again (or send SIGTERM).

If you have used the ``--database`` option, Wpull can reuse the
existing database for resuming crawls. This behavior is different than
``--continue``. Resuming with ``--continue`` is intended for resuming
partially downloaded files while ``--database`` is intended for resuming
partial crawls.

To resume a crawl provided you have used ``--database``, simply reuse
the same command options from the previous run. This will maintain the
same behavior as the previous run. You may also tweak the options, for
example, limit the recursion depth.

.. note:: When resuming downloads with ``--warc-file`` and
   ``--database``, Wpull will overwrite the WARC file by default. This
   occurs because Wpull simply maintains a list of URLs that are
   fetched and not fetched. You should either rename the existing
   file manually or use the additional option ``--warc-append`` or
   move the files ``--warc-move``.


Prioritisation
==============

With the ``--priority-regex`` and ``--priority-domain`` options, you can
control in which order the URLs in the queue are downloaded. These options
can be specified multiple times and are used in the given order. Each URL
is checked against the list of priority rules, and the first matching rule
sets the priority for the URL. The default priority (if no rule matches)
is zero. The higher a URL's priority value is, the sooner it is processed.


Proxied Services
================

Wpull is able to use an HTTP proxy server to capture traffic from third-party programs such as PhantomJS.
The requests will go through the proxy to Wpull's HTTP client (which can be recorded with ``--warc-file``).

.. warning:: Wpull uses the HTTP proxy insecurely on localhost.

    It is possible for another user, on the same machine as Wpull, to send bogus requests to the HTTP proxy. Wpull, however, does *not* expose the HTTP proxy outside to the net by default.

It is not possible to use the proxy standalone at this time.


PhantomJS Integration
+++++++++++++++++++++

**PhantomJS support is currently experimental.**

``--phantomjs`` will enable PhantomJS integration.

If a HTML document is encountered, Wpull will open the URL in PhantomJS. After the page is loaded, Wpull will try to scroll the page as specified by ``--phantomjs-scroll``. Then, the HTML DOM source is scraped for URLs as normal. HTML and PDF snapshots are taken by default.

Currently, Wpull will *not do anything else* to manipulate the page such as clicking on links. As a consequence, Wpull with PhantomJS is *not* a complete solution for dynamic web pages yet!

Storing console logs and alert messages inside the WARC file is not yet supported.


youtube-dl Integration
++++++++++++++++++++++

**youtube-dl support is currently experimental.**

``--youtube-dl`` will enable youtube-dl integration. 

If a HTML document is encountered, Wpull will run youtube-dl on the URL. Wpull uses the options for downloading subtitles and thumbnails. Other options are at the default which may not grab the best possible quality. For example, youtube-dl may not grab the highest quality stream because it is not a simple video file.

It is not recommended to use recursion because it may fetch redundant amounts of data.

Storing manifests, metadata, or converted files inside the WARC file is not yet supported.

