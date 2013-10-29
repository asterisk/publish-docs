# publish-docs

This project contains the scripts used to publish Asterisk's generated
documentation to http://wiki.asterisk.org.

The top level `publish.sh` should be run from the source directory of
the Asterisk version you wish to document. The file
`~/.asterisk-wiki.conf` should contain the settings for accessing the
[Confluence wiki server][confluence]. The script has a required
parameter naming the documentation branch (1.8, 11, 12, etc.).

```bash
# Example publish-docs configuration file
CONFLUENCE_URL=https://wiki.asterisk.org/wiki/rpc/xmlrpc
CONFLUENCE_USER=wikibot
CONFLUENCE_PASSWORD=peekaboo
#CONFLUENCE_SPACE=AST
```

Because some of the Asterisk documentation can only be generated at
runtime, the `publish.sh` script will build and install Asterisk to
the `/tmp` directory for generating the final documentation.

 [confluence]: https://www.atlassian.com/software/confluence
