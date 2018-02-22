==========
What's New
==========

Summary of notable changes.

.. Take advice from http://keepachangelog.com/.


Unreleased (fork by JustAnotherArchivist)
=========================================

* Fixed: Plugins are now loaded early again, restoring behaviour in version 1.x and allowing plugins to override wpull components again.
* Fixed: `--concurrent` option had no effect since version 2.0.
* Added: URL priorisation through `--priority-*` options and a `get_priority` hook.
* Changed: `wpull.pipeline.pipeline.ItemSource` now deals in item generation coroutines rather than items directly.
* Changed: wpull no longer flattens consecutive slashes in the path component of URLs, in line with RFC 3986, related standards, and behaviour of other software (wget and browsers).
* Changed: Backslashes in URL paths are now treated like forward slashes in accordance with the URL Standard and behaviour of browsers.


Backwards incompatibility
+++++++++++++++++++++++++

Plugins are now loaded very early in the initialisation again (as in version 1.x). This means that the various components of wpull
are not yet initialised at the time `WpullPlugin.activate()` is executed. Plugins written for versions 2.0 through 2.0.3 which use
instances directly will need to be changed to instead replace the relevant class in WpullPlugin.app_session.factory.class_map`.

Any direct usage of the `ItemSource`, `Worker`, or `Producer` classes in `wpull.pipeline.pipeline` has to be adapted to handle item
generation coroutines instead of items. The `Pipeline` and `PipelineSeries` classes in the same module are not affected.


2.0.3 (2017-05-15, fork by falconkirtaran)
==========================================

* Removed: HTTP CONNECT support
* Fixed: `ValueError` crash from URL parsing


2.0.2 (2017-01-12, fork by falconkirtaran)
==========================================

* Fixed: Deadlock when wpull is finished.
* Fixed: `AttributeError` crash on some SSL connections.
* Fixed: `--warc-max-size` option had no effect since version 2.0.
* Fixed: `AttributeError` crash from asyncio reading from a closed connection.


2.0.1 (2016-06-21)
==================

* Fixed: `KeyError` crash when psutil was not installed.
* Fixed: `AttributeError` proxy error using PhantomJS due to response body not written to a file.


2.0 (2016-06-17)
================

* Removed: Lua scripting support and its Python counterpart (``--lua-script`` and ``--python-script``).
* Removed: Python 3.2 & 3.3 support.
* Removed: PyPy support.
* Changed: IP addresses are normalized to a standard notation to avoid fetching duplicates such as IPv4 addresses written in hexadecimal or long-hand IPv6 addresses.
* Changed: Scripting is now done using plugin interface via ``--plugin-script``.
* Fixed: Support for Python 3.5.
* Fixed: FTP unable to handle directory listing with date in MMM DD YYYY and filename containing YYYY-MM-DD text.
* Fixed: Downloads through the proxy (such as PhantomJS) now show up in the database and can be controlled through scripting.
* Fixed: `NotFound` error when converting links in CSS file that contain URLs that were not fetched.
* Fixed: When resuming a forcefully interrupted crawl (e.g., a crash) using a database, URLs in progress were not restarted because they were not reset in the database when the program started up.


Backwards incompatibility
+++++++++++++++++++++++++

This release contains backwards incompatible changes to the database
schema and scripting interface.

If you use ``--database``, the database created by older versions in
Wpull cannot be used in this version.

Scripting hook code will need to be rewritten to use the new API. See
the new documentation for scripting for the new style of interfacing
with Wpull.

Additionally for scripts, the internal event loop has switched from
Trollius to built-in Asyncio.


1.2.3 (2016-02-03)
==================

* Removed: cx_freeze build support.
* Deprecated: Lua Scripting support will be removed in next release.
* Deprecated: Python 3.2 & 3.3 support will be removed in the next release.
* Deprecated: PyPy support will be removed in the next release.
* Fixed: Error when logging in with FTP to servers that don't need a password.
* Fixed: ValueError when downloading URLs that contain unencoded unprintable characters like Zero Width Non-Joiner or Right to Left Mark.


1.2.2 (2015-10-21)
==================

* Fixed: ``--output-document`` file doesn't contain content.
* Fixed: OverflowError when URL contains invalid port number greater than 65535 or less than 0.
* Fixed: AssertionError when saving IPv4-mapped IPv6 addresses to WARC files.
* Fixed: AttributeError when running with installed Trollius 2.0.
* Changed: The setup file no longer requires optional psutil.


1.2.1 (2015-05-15)
==================

* Fixed: OverflowError with URLs with large port numbers.
* Fixed: TypeError when using standard input as input file (``--input-file -``).
* Changed: using ``--youtube-dl`` respects ``--inet4-only`` and ``--no-check-certificate`` now.


1.2 (2015-04-24)
================

* Fixed: Connecting to sites with IPv4 & IPv6 support resulted in errors when IPv6 was not supported by the local network. Connections now use Happy Eyeballs Algorithm for IPv4 & IPv6 dual-stack support.
* Fixed: SQLAlchemy error with PyPy and SQLAlchemy 1.0.
* Fixed: Input URLs are not fetched in order. Regression since 1.1.
* Fixed: UnicodeEncodeError when fetching FTP files with non-ASCII filenames.
* Fixed: Session cookies not loaded when using ``--load-cookies``.
* Fixed: ``--keep-session-cookies`` was always on.
* Changed: FTP communication uses UTF-8 instead of Latin-1.
* Changed: ``--prefer-family=none`` is now default.
* Added: ``none`` as a choice to ``--prefer-family``.
* Added: ``--no-glob`` and FTP filename glob support.


1.1.1 (2015-04-13)
==================

* Changed: when using ``--youtube-dl`` and ``--warc-file``, the JSON metedata file is now saved in the WARC file compatible with pywb.
* Changed: logging and progress meter to say "unspecified" instead of "none" when no content length is provided by server to match Wget.


1.1 (2015-04-03)
================

* Security: Updated certificate bundle.
* Fixed: ``--regex-type`` to accept ``pcre`` instead of ``posix``. Regular expressions always use Python's regex library. Posix regex is not supported.
* Fixed: when using ``--warc-max-size`` and ``--warc-append``, it wrote to existing sequential WARC files unnecessarily.
* Fixed: input URLs stored in memory instead of saved on disk. This issue was notable if there were many URLs provided by the ``--input-file`` option.
* Changed: when using ``--warc-max-size`` and ``--warc-append``, the next sequential WARC file is created to avoid appending to corrupt files.
* Changed: WARC file writing to use journal files and refuse to start program if any journals exist. This avoids corrupting files through naive use of ``--warc-append`` and allow for future automated recovery.
* Added: Open Graph and Twitter Card element links extraction.


1.0 (2015-03-14)
================

* Fixed: a ``--database`` path with a question mark (``?``) truncated the path, did not use a on-disk database, or causes ``TypeError``. The question mark is automatically replaced with an underscore.
* Fixed: HTTP proxy support broken since version 0.1001.
* Added: ``no_proxy`` environment variable support.
* Added: ``--proxy-domains``, ``--proxy-exclude-domains``, ``--proxy-hostnames``, ``--proxy-exclude-hostnames``
* Removed: ``--no-secure-proxy-tunnel``.


0.1009 (2015-03-08)
===================

* Added: ``--preserve-permissions``.
* Fixed: exit code returned as 2 instead of 1 on generic errors.
* Changed: exception tracebacks are printed only on generic errors.
* Changed: temporary WARC log file is now compressed to save space.

Scripting Hook API:

* Added: Version 3 API
* Added: ``wait_time`` to version 3 which provides useful context including response or error infos.


0.1008 (2015-02-26)
===================

* Security: updated certificate bundle.
* Fixed: TypeError crash on bad Meta Refresh HTML element.
* Fixed: unable to fetch FTP files with spaces and other special characters.
* Fixed: AssertionError fetching URLs with trailing dot not properly removed.
* Added: ``--no-cache``.
* Added: ``--report-speed``.
* Added: ``--monitor-disk`` and ``--monitor-memory``.


0.1007 (2015-02-19)
===================

* Fixed malformed URLs printed to logs without sanitation.
* Fixed AttributeError crash on FTP servers that support MLSD.
* Improved link recursion heuristics when extracting from JavaScript and HTML.
* Added ``--retr-symlinks``.
* Added ``--session-timeout``.


0.1006.1 (2015-02-09)
=====================

* Security: Fixed ``Referer`` HTTP header field leaking from HTTPS to HTTP.
* Fixed ``AttributeError`` in proxy when using PhantomJS and ``pre_response`` scripting hook.
* Fixed early program end when server returns error fetching robots.txt.
* Fixed uninteresting errors outputted if program is forcefully closed.
* Fixed ``--referer`` option not applied to subsequent requests.


0.1006 (2015-02-01)
===================

* Fixed inability to fetch URLs with hostnames starting/ending with hyphen.
* Fixed "Invalid file descriptor" error in proxy server.
* Fixed FTP listing dates mistakenly parsed as future date within the same month.
* Added ``--escaped-fragment`` option.
* Added ``--strip-session-id`` option.
* Added ``--no-skip-getaddrinfo`` option.
* Added ``--limit-rate`` option.
* Added ``--phantomjs-max-time`` option.
* Added ``--youtube-dl`` option.
* Added ``--plugin-script`` option.
* Improved PhantomJS stability.


0.1005 (2015-01-15)
===================

* Security: SSLv2/SSLv3 is disabled for ``--secure-protocol=auto``. Added ``--no-strong-crypto`` that re-enables them again if needed.
* Fixed NameError with PhantomJS proxy on Python 3.2.
* Fixed PhantomJS stop waiting for page load too early.
* Fixed "Line too long" error and remove uninteresting page errors during PhantomJS.
* Fixed ``--page-requisites`` exceeding ``--level``.
* Fixed ``--no-verbose`` not providing informative messages and behaving like ``--quiet``.
* Fixed infinite page requisite recursion when using ``--span-hosts-allow page-requisites``.
* Added ``--page-requisites-level``. The default max recursion depth on page requisites is now 5.
* Added ``--very-quiet``.
* ``--no-verbose`` is defaulted when ``--concurrent`` is 2 or greater.

Database Schema:

* URL ``inline`` column is now an integer.


0.1004.2 (2015-01-03)
=====================

Hotfix release.

* Fixed PhantomJS mode's MITM proxy AttributeError on certificates.


0.1004.1 (2015-01-03)
=====================

* Fixed TypeError crash on a bad cookie.
* Fixed PhantomJS mode's MITM proxy SSL certificates not installed.


0.1004 (2014-12-25)
===================

* Fixed FTP data connection reuse error.
* Fixed maximum recursion depth exceeded on FTP downloads.
* Fixed FTP file listing detecting dates too eagerly as ISO8601 format.
* Fixed crash on FTP if file listing could not find a date in a line.
* Fixed HTTP status code 204 "No Content" interpreted as an error.
* Fixed "cert already in hash table" error when using both OS and Wpull's certificates.
* Improved PhantomJS stability. Timeout errors should be less frequent.
* Added ``--adjust-extension``.
* Added ``--content-disposition``.
* Added ``--trust-server-names``.


0.1003 (2014-12-11)
===================

* Fixed FTP fetch where code 125 was not recognized as valid.
* Fixed FTP 12 o'clock AM/PM time logic.
* Fixed URLs fetched as lowercase URLs when scheme and authority separator is not provided.
* Added ``--database-uri`` option to specify a SQLAlchemy URI.
* Added ``none`` as a choice to ``--progress``.
* Added ``--user``/``--password`` support.

* Scripting:

  * Fixed missing response callback during redirects. Regression introduced in v0.1002.


0.1002 (2014-11-24)
===================

* Fixed control characters printed without escaping.
* Fixed cookie size not limited correctly per domain name.
* Fixed URL parsing incorrectly allowing spaces in hostnames.
* Fixed ``--sitemaps`` option not respecting ``--no-parent``.
* Fixed "Content overrun" error on broken web servers. A warning is logged instead.
* Fixed SSL verification error despite ``--no-check-certificate`` is specified.
* Fixed crash on IPv6 URLs containing consecutive dots.
* Fixed crash attempting to connect to IPv6 addresses.
* Consecutive slashes in URL paths are now flattened.
* Fixed crash when fetching IPv6 robots.txt file.
* Added experimental FTP support.
* Switched default HTML parser to html5lib.

* Scripting:

  * Added ``handle_pre_response`` callback hook.

* API:

  * Fixed ``ConnectionPool`` ``max_host_count`` argument not used.
  * Moved document scraping concerns from ``WebProcessorSession`` to ``ProcessingRule``.
  * Renamed ``SSLVerficationError`` to ``SSLVerificationError``.


0.1001.2 (2014-10-25)
=====================

* Fixed ValueError crash on HTTP redirects with bad IPv6 URLs.
* Fixed AssertionError on link extraction with non-absolute URLs in "codebase" attribute.
* Fixed premature exit during an error fetching robots.txt.
* Fixed executable filename problem in setup.py for cx_Freeze builds.


0.1001.1 (2014-10-09)
=====================

* Fixed URLs with IPv6 addresses not including brackets when using them in host strings.
* Fixed AssertionError crash where PhantomJS crashed.
* Fixed database slowness over time.
* Cookies are now synchronized and shared with PhantomJS.

* Scripting:

  * Fixed mismatched ``queued_url` and ``dequeued_url`` causing negative values in a counter. Issue was caused by requeued items in "error" status.


0.1001 (2014-09-16)
===================

* Fixed ``--warc-move`` option which had no effect.
* Fixed JavaScript scraper to not accept URLs with backslashes.
* Fixed CSS scraper to not accept URLs longer than 500 characters.
* Fixed ValueError crash in Cache when two URLs are added sequentially at the same time due to bad LinkedList key comparison.
* Fixed crash formatting text when sizes reach terabytes.
* Fixed hang which may occur with lots of connection across many hostnames.
* Support for HTTP/HTTPS proxies but no HTTPS tunnelling support. Wpull will refuse to start without the insecure override option. Note that if authentication and WARC file is enabled, the username and password is recorded into the WARC file.
* Improved database performance.
* Added ``--ignore-fatal-errors`` option.
* Added ``--http-parser`` option. You can now use html5lib as the HTML parser.
* Support for PyPy 2.3.1 running with Python 3.2 implementation.
* Consistent URL parsing among various Python versions.
* Added ``--link-extractors`` option.
* Added ``--debug-manhole`` option.

* API:

  * ``document`` and ``scraper`` were put into their own packages.
  * HTML parsing was put into ``document.htmlparse`` package.
  * ``url.URLInfo`` no longer supports normalizing URLs by percent decoding unreserved/safe characters.

* Scripting:

  * Dropped support for Scripting API version 1.

* Database schema:

  * Column ``url_encoding`` is removed from ``urls`` table.


0.1000 (2014-09-02)
===================

* Dropped support for Python 2. Please file an issue if this is a problem.
* Fixed possible crash on empty content with deflate compression.
* Fixed document encoding detection on documents larger than 4096 bytes where an encoded character may have been truncated.
* Always percent-encode IRIs with UTF-8 to match de facto web browser implementation.
* HTTP headers are consistently decoded as Latin-1.
* Scripting API:

  * New ``queued_url`` and ``dequeued_url`` hooks contributed by mback2k.

* API:

  * Switched to Trollius instead of Tornado. Please use Trollius 1.0.2 alpha or greater.
  * Most the of internals related to the HTTP protocol were rewritten and as a result, major components are not backwards compatible; lots of changes were made. If you happen to be using Wpull's API, please pin your requirements to ``<0.1000`` if you do not want to make a migration. Please file an issue if this is a problem.


0.36.4 (2014-08-07)
===================

* Fixes crash when ``--save-cookies`` is used with non-ASCII cookies. Cookies with non-ASCII values are discarded.
* Fixed HTTP gzip compressed content not decompressed during chunked transfer of single bytes.
* Tornado 4.0 support.
* API:

  * Renamed: ``cookie.CookieLimitsPolicy`` to ``DeFactoCookiePolicy``.


0.36.3 (2014-07-25)
===================

* Improved performance on ``--database`` option. SQLite now uses synchronous=NORMAL instead of FULL.


0.36.2 (2014-07-16)
===================

* Fixed requirements.txt to use Tornado version less than 4.0.


0.36.1 (2014-07-16)
===================

* Fixes bug where "FINISHED" message was not logged in WARC file meta log. Regression was introduced in version 0.35.


0.36 (2014-06-23)
=================

* Works around ``PhantomJSRPCTimedOut`` errors.
* Adds ``--phantomjs-exe`` option.
* Supports extracting links from HTML ``img`` ``srcset`` attribute.
* API:

  * ``Builder.build()`` returns ``Application`` instead of ``Engine``.
  * Callback hooks ``exit_status`` and ``finishing_statistics`` now registered on ``Application`` instead of ``Engine``.
  * ``network`` module split into two modules ``bandwidth`` and ``dns``.
  * Adds ``observer`` module.
  * ``phantomjs.PhantomJSRemote.page_event`` renamed to ``page_observer``.


0.35 (2014-06-16)
=================

* Adds ``--warc-move`` option.
* Scripting:

  * Default scripting version is now 2.

* API:

  * `Builder` moved into new module `builder`
  * Adds `Application` class intended for different UI in the future.
  * ``Resolver`` ``families`` parameter renamed into ``family``. It accepts values from the module ``socket`` or ``PREFER_IPv4``/``PREFER_IPv6``.
  * Adds ``HookableMixin``. This removes the use of messy subclassing for scripting hooks.


0.34.1 (2014-05-26)
===================

* Fixes crash when a URL is incorrectly formatted by Wpull. (The incorrect formatting is not fixed yet however.)


0.34 (2014-05-06)
=================

* Fixes file descriptor leak with ``--phantomjs`` and ``--delete-after``.
* Fixes case where robots.txt file was stuck in download loop if server was offline.
* Fixes loading of cookies file from Wget. Cookie file header checks are disabled.
* Removes unneeded ``--no-strong-robots`` (superseded with ``--no-strong-redirects``.)
* Fixes ``--no-phantomjs-snapshot`` option not respected.
* More link extraction on HTML pages with elements with ``onclick``, ``onkeyX``, ``onmouseX``, and ``data-`` attributes.
* Adds web-based debugging console with ``--debug-console-port``.


0.33.2 (2014-04-29)
===================

* Fixes links not resolved correctly when document includes ``<base href="...">`` element.
* Different proxy URL rewriting for PhantomJS option.


0.33.1 (2014-04-26)
===================

* Fixes ``--bind_address`` option not working. The option was never functional since the first release.
* Fixes AttributeError crash when ``--phantomjs`` and ``--X-script`` options were used. Thanks to yipdw for reporting.
* Fixes ``--warc-tempdir`` to use the current directory by default.
* Fixes bad formatting and crash on links with malformed IPv6 addresses.
* Uses more rules for link extraction from JavaScript to reduce false positives.


0.33 (2014-04-21)
===================

* Fixes invalid XHTML documents not properly extracted for links.
* Fixes crash on empty page.
* Support for extracting links from JavaScript segments and files.
* Doesn't discard extracted links if document can only be parsed partially.

* API:

  * Moves ``OrderedDefaultDict`` from ``util`` to ``collections``.
  * Moves ``DeflateDecompressor``, ``gzip_decompress`` from ``util`` to ``decompression``.
  * Moves ``sleep``, ``TimedOut``, ``wait_future``, ``AdjustableSemaphore`` from ``util`` to ``async``.
  * Moves ``to_bytes``, ``to_str``, ``normalize_codec_name``, ``detect_encoding``, ``try_decoding``, ``format_size``, ``printable_bytes``, ``coerce_str_to_ascii`` from ``util`` to ``string``.
  * Removes ``extended`` module.

* Scripting:

  * Adds new `wait_time()` callback hook function.


0.32.1 (2014-04-20)
===================

* Fixes XHTML documents not properly extracted for links.
* If a server responds with content declared as Gzip, the content is checked to see if it starts with the Gzip magic number. This check avoids misreading text as Gzip streams.


0.32 (2014-04-17)
==================

* Fixes crash when HTML meta refresh URL is empty.
* Fixes crash when decoding a document that is malformed later in the document. These invalid documents are not searched for links.
* Reduces CPU usage when ``--debug`` logging is not enabled.
* Better support for detecting and differentiating XHTML and XML documents.
* Fixes converting XHTML documents where it did not write XHTML syntax.
* RSS/Atom feed ``link``, ``url``, ``icon`` elements are searched for links.

* API:

  * ``document.detect_response_encoding()`` default peek argument is lowered to reduce hanging.
  * ``document.BaseDocumentDetector`` is now a base class for document type detection.


0.31 (2014-04-14)
==================

* Fixes issue where an early ``</html>`` causes link discovery to be broken and converted documents missing elements.
* Fixes ``--no-parent`` which did not behave like Wget. This issue was noticeable with options such as ``--span-hosts-allow linked-pages``.
* Fixes ``--level`` where page requisites were mistakenly not fetched if it exceeds recursion level.
* Includes PhantomJS version string in WARC warcinfo record.
* User-agent string no longer includes Mozilla reference.
* Implements ``--force-html`` and ``--base``.
* Cookies now are limited to approximately 4 kilobytes and a maximum of 50 cookies per domain.
* Document parsing is now streamed for better handling of large documents.

* Scripting:

  * Ability to set a scripting API version.
  * Scripting API version 2: Adds ``record_info`` argument to ``handle_error`` and ``handle_response``.

* API:

  * WARCRecorder uses new parameter object WARCRecorderParams.
  * ``document``, ``scraper``, ``converter`` modules heavily modified to accommodate streaming readers. ``document.BaseDocumentReader.parse`` was removed and replaced with ``read_links``.
  * `version.version_info` available.


0.30 (2014-04-06)
==================

* Fixes crash on SSL handshake if connection is broken.
* DNS entries are periodically removed from cache instead of held for long times.
* Experimental cx_freeze support.

* PhantomJS:

  * Fixes proxy errors with requests containing a body.
  * Fixes proxy errors with occasional FileNotFoundError.
  * Adds timeouts to calls.
  * Viewport size is now 1200 × 1920.
  * Default ``--phantomjs-scroll`` is now 10.
  * Scrolls to top of page before taking snapshot.

* API:

  * URL filters moved into urlfilter module.
  * Engine uses and exposes interface to AdjustableSemaphore for issue #93.


0.29 (2014-03-31)
==================

* Fixes SSLVerficationError mistakenly raised during connection errors.
* ``--span-hosts`` no longer implicitly enabled on non-recursive downloads. This behavior is superseded by strong redirect logic. (Use ``--span-hosts-allow`` to guarantee fetching of page-requisites.)
* Fixes URL query strings normalized with unnecessary percent-encoding escapes. Some servers do not handle percent-encoded URLs well.
* Fixes crash handling directory paths that may contain a filename or a filename that is a directory. This crash occurs when a URL like `/blog` and `/blog/` exists. If a directory path contains a filename, the part of the directory path is suffixed with `.d`. If a filename is an existing directory, the filename is suffixed with `.f`.
* Fixes crash when URL's hostname contains characters that decompose to dots.
* Fixes crash when HTML document declares encoding name unknown to Python.
* Fixes stuck in loop if server returns errors on robots.txt.
* Implements ``--warc-dedup``.
* Implements ``--ignore-length``.
* Implements ``--output-document``.
* Implements ``--http-compression``.
* Supports reading HTTP compression "deflate" encoding (both zlib and raw deflate).

* Scripting:

  * Adds ``engine_run()`` callback.
  * Exposes the instance factory.

* API:

  * connection: ``Connection`` arguments changed. Uses ``ConnectionParams`` as a parameter object. ``HostConnectionPool`` arguments also changed.
  * database: ``URLDBRecord`` renamed to ``URL``. ``URLStrDBRecord`` renamed to ``URLString``.

* Schema change:

  * New ``visits`` table.


0.28 (2014-03-27)
==================

* Fixes crash when redirected to malformed URL.
* Fixes ``--directory-prefix`` not being honored.
* Fixes unnecessary high CPU usage when determining encoding of document.
* Fixes crash (GeneratorExit exception) when exiting on Python 3.4.
* Uses new internal socket connection stream system.
* Updates bundled certificates (Tue Jan 28 09:38:07 2014).
* PhantomJS:

  * Fixes things not appearing in WARC files. This regression was introduced in 0.26 where PhantomJS's disk cache was enabled. It is now disabled again.
  * Fixes HTTPS proxy URL rewriting where relative URLs were not properly rewritten.
  * Fixes proxy URL rewriting not working for localhost.
  * Fixes unwanted ``Accept-Language`` header picked up from environment. The value has been overridden to ``*``.
  * Fixes ``--header`` options left out in requests.

* API:

  * New ``iostream`` module.
  * ``extended`` module is deprecated.


0.27 (2014-03-23)
==================

* Fixes URLs ignored (if any) on command line when ``--input-file`` is specified.
* Fixes crash when redirected to a URL that is not HTTP.
* Fixes crash if lxml does not recognize the document encoding name. Falls back to Latin1 if lxml does not support the encoding after massaging the encoding name.
* Fixes crash on IPv6 addresses when using scripting or external API calls.
* Fixes speed shown as "0.0 B/s" instead of "-- B/s" when speed can not be calculated.
* Implements ``--local-encoding``, ``--remote-encoding``, ``--no-iri``.
* Implements ``--https-only``.
* Prints bandwidth speed statistics when exiting.
* PhantomJS:

  * Implements "smart scrolling" that avoids unnecessary scrolling.
  * Adds ``--no-phantomjs-smart-scroll``

* API:

  * ``WebProcessorSession._parse_url()`` renamed to ``WebProcessorSession.parse_url()``


0.26 (2014-03-16)
==================

* Fixes crash when URLs like ``http://example.com]`` were encountered.
* Implements ``--sitemaps``.
* Implements ``--max-filename-length``.
* Implements ``--span-hosts-allow`` (experimental, see issues #61, #66).
* Query strings items like ``?a&b`` are now preserved and no longer normalized to ``?a=&b=``.
* API:

  * url.URLInfo.normalize() was removed since it was mainly used internally.
  * Added url.normalize() convenience function.
  * writer: safe_filename(), url_to_filename(), url_to_dir_path() were modified.


0.25 (2014-03-13)
=================

* Fixes link converter not operating on the correct files when ``.N`` files were written.
* Fixes apparent hang when Wpull is almost finished on documents with many links.

  * Previously, Wpull adds all URLs to the database causing overhead processing to be done in the database. Now, only requisite URLs are added to the database.

* Implements ``--restrict-file-names``.
* Implements ``--quota``.
* Implements ``--warc-max-size``. Like Wget, "max size" is not the maximum size of each WARC file but it is the threshold size to trigger a new file. Unlike Wget, ``request`` and ``response`` records are not split across WARC files.
* Implements ``--content-on-error``.
* Supports recording scrolling actions in WARC file when PhantomJS is enabled.
* Adds the ``wpull`` command to ``bin/``.
* Database schema change: ``filename`` column was added.
* API:

  * converter.py: Converters no longer use PathNamer.
  * writer.py: ``sanitize_file_parts()`` was removed in favor of new ``safe_filename()``. ``save_document()`` returns a filename.
  * WebProcessor now requires a root path to be specified.
  * WebProcessor initializer now takes "parameter objects".

* Install requires new dependency: ``namedlist``.


0.24 (2014-03-09)
==================

* Fixes crash when document encoding could not be detected. Thanks to DopefishJustin for reporting.
* Fixes non-index files incorrectly saved where an extra directory was added as part of their path.
* URL path escaping is relaxed. This helps with servers that don't handle percent-encoding correctly.
* ``robots.txt`` now bypasses the filters. Use ``--no-strong-robots`` to disable this behavior.
* Redirects implicitly span hosts. Use ``--no-strong-redirects`` to disable this behavior.
* Scripting: ``should_fetch()`` info dict now contains ``reason`` as a key.


0.23.1 (2014-03-07)
===================

* Important: Fixes issue where URLs were downloaded repeatedly.


0.23 (2014-03-07)
=================

* Fixes incorrect logic in fetching robots.txt when it redirects to another URL.
* Fixes port number not included in the HTTP Host header.
* Fixes occasional ``RuntimeError`` when pressing CTRL+C.
* Fixes fetching URL paths containing dot segments. They are now resolved appropriately.
* Fixes ASCII progress bar not showing 100% when finished download occasionally.
* Fixes crash and improves handling of unusual document encodings and settings.
* Improves handling of links with newlines and whitespace intermixed.
* Requires beautifulsoup4 as a dependency.
* API:

  * ``util.detect_encoding()`` arguments modified to accept only a single fallback and to accept ``is_html``.
  * ``document.get_encoding()`` accepts ``is_html`` and ``peek`` arguments.


0.22.5 (2014-03-05)
===================

* The 'Refresh' HTTP header is now scraped for URLs.
* When an error occurs during writing WARC files, the WARC file is truncated back to the last good state before crashing.
* Works around error "Reached maximum read buffer size" downloading on fast connections. Side effect is intensive CPU usage.


0.22.4 (2014-03-05)
===================

* Fixes occasional error on chunked transfer encoding. Thanks to ivan for reporting.
* Fixes handling links with newlines found in HTML pages. Newlines are now stripped in links when scraping pages to better handle HTML soup.


0.22.3 (2014-03-02)
===================

* Fixes another case of ``AssertionError`` on ``url_item.is_processed`` when robots.txt was enabled.
* Fixes crash if a malformed gzip response was received.
* Fixes ``--span-hosts`` to be implicitly enabled (as with ``--no-robots``) if ``--recursive`` is not supplied. This behavior unconditionally allows downloading a single file without specifying any options. It is what a user intuitively expects.


0.22.2 (2014-03-01)
===================

* Improves performance on database operations. CPU usage should be less intensive.


0.22.1 (2014-02-28)
===================

* Fixes handling of "204 No Content" responses.
* Fixes ``AssertionError`` on ``url_item.is_processed`` when robots.txt was enabled.
* Fixes PhantomJS page scrolling to be consistent.
* Lengthens PhantomJS viewport to ensure lazy-load images are properly triggered.
* Lengthens PhantomJS paper size to reduce excessive fragmentation of blocks.


0.22 (2014-02-27)
=================

* Implements ``--phantomjs-scroll`` and ``--phantomjs-wait``.
* Implements saving HTML and PDF snapshots (including inside WARC file). Disable with ``--no-phantomjs-snapshot``.
* API: Adds PhantomJSController.


0.21.1 (2014-02-27)
===================

* Fixes missing dependencies and files in ``setup.py``.
* For PhantomJS:

  * Fixes capturing HTTPS connections .
  * Fixes statistics counter.
  * Supports very basic scraping of HTML. See Usage section.


0.21 (2014-02-26)
=================

* Fixes Request factory not used. This resolves issues where the User Agent was not set.
* Experimental PhantomJS support. It can be enabled with ``--phantomjs``. See the Usage section in the documentation for more details.
* API changes:

  * The ``http`` module was split up into smaller modules: ``http.client``, ``http.connection``, ``http.request``, ``http.util``.
  * ``ChunkedTransferStreamReader`` was added as a reusable abstraction.
  * The ``web`` module was moved to ``http.web``.
  * Added ``proxy`` module.
  * Added ``phantomjs`` module.


0.20 (2014-02-22)
=================

* Implements ``--no-dns-cache``, ``--accept``, ``--reject``.
* Scripting: Fixes ``AttributeError`` crash on ``handle_error``.
* Another possible fix for issue #27.


0.19.2 (2014-02-18)
===================

* Fixes crash if a non-HTTP URL was found during download.
* Lua scripting: Fixes booleans, coming from Wpull, mistakenly converted to integers on Python 2


0.19.1 (2014-02-14)
===================

* Fixes ``--timestamping`` functionality.
* Fixes ``--timestamping`` not checking ``.orig`` files.
* Fixes HTTP handling of responses which do not return content.


0.19 (2014-02-12)
=================

* Fixes files not actually being written.
* Implements ``--convert-links`` and ``--backup-converted``.
* API: ``HTMLScraper`` functions were refactored to be class methods. ``ScrapedLink`` was renamed to ``LinkInfo``.


0.18.1 (2014-02-11)
===================

* Fixes error when WARC but not CDX option is specified.
* Fixes closing of the SQLite database to avoid leaving temporary database files.


0.18 (2014-02-11)
==================

* Implements ``--no-warc-digests``, ``--warc-cdx``.
* Improvements on reducing CPU usage consumption.
* API: Engine and Processor interaction refactored to be asynchronous.

  * The Engine and Processor classes were modified significantly.
  * The Engine no longer is concerned with fetching requests.
  * Requests are handled within Processors. This will benefit future Processors to allow them to make arbitrary requests during processing.
  * The ``RedirectTracker`` was moved to a new ``web`` module.
  * A ``RichClient`` is implemented. It handles robots.txt, cookies, and redirect concerns.
  * ``WARCRecord`` was moved into a new ``warc`` module.


0.17.3 (2014-02-07)
===================

* Fixes ca-bundle file missing during install.
* Fixes AttributeError on ``retry_dns_error``.


0.17.2 (2014-02-06)
===================

* Another attempt to possibly fix #27.
* Implements cleaning inactive connections from the connection pool.


0.17.1 (2014-02-05)
===================

* Another attempt to possibly fix #27.
* API: Refactored ``ConnectionPool``. It now calls ``put`` on ``HostConnectionPool`` to avoid sharing a queue.


0.17 (2014-02-05)
=================

* Implements cookie support.
* Fixes non-recursive downloads where robots.txt was checked unnecessarily.
* Possibly fix issue #27 where HTTP workers get stuck.


0.16.1 (2014-02-05)
===================

* Adds some documentation about stopping Wpull and a list of all options.
* API: ``Builder`` now exposes ``Factory``.
* API: ``WebProcessorSession`` was refactored to not pass arguments through the initializer. It also now uses ``DemuxDocumentScraper`` and ``DemuxURLFilter``.


0.16 (2014-02-04)
=================

* Implements all the SSL options: ``--certificate``, ``--random-file``, ``--egd-file``, ``--secure-protocol``.
* Further improvement on database performance.


0.15.2 (2014-02-03)
===================

* Improves database performance on reducing CPU usage.


0.15.1 (2014-02-03)
===================

* Improves database performance on reducing disk reading.


0.15 (2014-02-02)
=================

* Fixes robots.txt being fetched for every request.
* Scripts: Supports ``replace`` as part of ``get_urls()``.
* Schema change: The database URL strings are normalized into a separate table. Using ``--database`` should now consume less disk space.


0.14.1 (2014-02-02)
===================

* NameValueRecord now supports a ``normalize_override`` argument to how specific keys are cased instead of the default title-case.
* Fixes WARC file's field names to match the same cases as hanzo's warc-tools. warc-tools does not support case-insensitivity as required by the WARC specification in section 4. The WARC files generated by Wpull are conformant however.


0.14 (2014-02-01)
=================

* Database change: SQLAlchemy is now used for the URL Table.

  * Scripts: ``url_info['inline']`` now returns a boolean, not an integer.

* Implements ``--post-data`` and ``--post-file``.
* Scripts can now return ``post_data`` and ``link_type`` as part of ``get_urls()``.


0.13 (2014-01-31)
=================

* Supports reading HTTP responses with gzip content type.


0.12 (2014-01-31)
=================

* No changes to program usage itself.
* More documentation.
* Major API changes due to refactoring:

  * ``http.Body`` moved to ``conversation.Body``
  * ``document.HTTPScraper``, ``document.CSSScraper`` moved to ``scraper`` module.
  * ``conversation`` module now contains base classes for protocol elements.
  * ``processor.WebProcessorSession`` now uses keyword arguments
  * ``engine.Engine`` requires ``Statistics`` argument.


0.11 (2014-01-29)
=================

* Implements ``--progress`` which includes a progress bar indicator.
* Bumps up the HTTP connection buffer size to support fast connections.


0.10.9 (2014-01-28)
===================

* Adds documentation. No program changes.


0.10.8 (2014-01-26)
===================

* Improves robustness against bad HTTP protocol messages.
* Fixes various URL and IRI handling issues.
* Fixes ``--input-file`` to work as expected.
* Fixes command line arguments not working under Python 2.


0.10 (2014-01-23)
=================

* Improves handling on URLs and document encodings.
* Implements ``--ascii-print``.
* Fixes Lua scripting conversion of Python to Lua object types.


0.9 (2014-01-21)
================

* Adds basic SSL options.


0.8 (2014-01-21)
================

* Supports Python and Lua scripting via ``--python-script`` and
  ``--lua-script``.


0.7 (2014-01-18)
================

* Fixes robots.txt support.


0.6 (2014-01-17)
================

* Implements ``--warc-append``, ``--concurrent``.
* ``--read-timeout`` default is 900 seconds.


0.5 (2014-01-17)
================

* Implements ``--no-http-keepalive``, ``--rotate-dns``.
* Adds basic support for HTTPS.


0.4 (2014-01-15)
================

* Implements ``--continue``, ``--no-clobber``, ``--timestamping``.


0.3.2 (2014-01-07)
==================

* Fixes database rows not saved correctly.


0.3 (2014-01-07)
================

* Implements ``--hostnames`` and ``--exclude-hostnames``.


0.2 (2014-01-06)
================

* Implements ``--header`` option.
* Various 3to2 bug fixes.


0.1 (2014-01-05)
================

* The first usable release.



