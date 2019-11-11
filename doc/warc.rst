WARC Specification
==================

Additional de-facto and custom extensions to the WARC standard.

Wpull follows the specifications in the `ISO 28500 latest draft <http://bibnum.bnf.fr/WARC/WARC_ISO_28500_version1_latestdraft.pdf>`_. 


FTP
+++

FTP recording follows `Heritrix specifications <http://aaron.blog.archive.org/2013/05/17/handling-archived-ftp-resources/>`_.


Control Conversation
--------------------

The Control Conversation is recorded as

* WARC-Type: ``metadata``
* Content-Type: ``text/x-ftp-control-conversation``
* WARC-Target-URI: a URL. For example, ``ftp://anonymous@example.com/treasure.txt``
* WARC-IP-Address: an IPv4 address with port or an IPv6 address with brackets and port

The resource is formatted as followed:

* Events are indented with an ASCII asterisk and space.
* Requests are indented with an ASCII greater-than and space.
* Responses are indented with an ASCII less-than and space.

The document encoding is UTF-8.

.. versionchanged:: 1.2a1

    The document encoding previously used Latin-1.


Response data
-------------

The response data is recorded as

* WARC-Type: ``resource``
* WARC-Target-URI: a URL. For example, ``ftp://anonymous@example.com/treasure.txt``
* WARC-Concurrent-To: a WARC Record ID of the Control Conversation


Wpull Metadata
++++++++++++++

Log
---

Wpull's log is recorded as

* WARC-Type: ``resource``
* Content-Type: ``text/plain``
* WARC-Target-URI: ``urn:X-wpull:log``

The document encoding is UTF-8.

youtube-dl
++++++++++

JSON file is recorded as

* WARC-Type: ``metadata``
* Content-Type: ``application/vnd.youtube-dl_formats+json``
* WARC-Target-URI: ``metadata://AUTHORITY_AND_RESOURCE`` where ``AUTHORITY_AND_RESOURCE`` is the hierarchical part, query, and fragment of the URL passed to youtube-dl. In other words, the URI is the URL where the scheme is replaced with ``metadata``.

