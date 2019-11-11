============
Introduction
============

.. ⬇ Please keep this intro in sync with the README file. ⬇

Wpull is a Wget-compatible (or remake/clone/replacement/alternative) web
downloader and crawler.

.. image:: https://raw.githubusercontent.com/chfoo/wpull/master/icon/wpull_logo_full.png
   :target: https://github.com/chfoo/wpull
   :alt: A dog pulling a box via a harness.

Notable Features:

* Written in Python: lightweight, modifiable, robust, & scriptable
* Graceful stopping; on-disk database resume
* youtube-dl integration (experimental)

.. ⬆ Please keep this intro above in sync with the README file. ⬆
   Additional intro stuff not in the README should go below.


Wpull is designed to be (almost) a drop-in replacement for Wget with
minimal changes to options. It is designed to run on much larger crawls
rather than speedily downloading a single file.

Wpull's behavior is not an exact duplicate of Wget's behavior. As such,
you should not expect exact output and operation out of Wpull. However,
it aims to be a very useful alternative as its source code can be
easily modified to fix, change, or extend its behaviors.

For instructions, read on to the next sections. Confused? Check out the
:doc:`Frequently Asked Questions <help>`.
