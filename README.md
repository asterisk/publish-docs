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
 
 
## Getting up and running

Checkout Asterisk branch

Run `contrib/scripts/install_prereq` in asterisk checkout directory

You'll need some dependencies

sudo apt-get install python-dev python-virtualenv python-lxml

pip install pystache

You'll need to run all of this as the root user, its easier to just sudo su!

## Gotchas - until we sort them out in a nice generic way

Running `publish.sh --dry-run BRANCH_NUMBER` will fail eventually, take the command it outputs and run that directly with `--debug` added to it

Something like:

```
/path/to/publish-docs/astxml2wiki.py --username=wikibot --server=https://wiki.asterisk.org/wiki/rpc/xmlrpc '--prefix=Asterisk 12' --space=AST --file=/path/to/publish-docs/asterisk-docs.xml --ast-version=SVN-branch-12-r406327 --diff -v --debug
```

You do want to run publish.sh though, as it compiles Asterisk with all the things you need and generates the docs xml file from Asterisk itself

If you're not changing anything to do with ARI documentation, comment ARI docs generation out of publish.sh - `line 152` in `publish.sh` - it doesn't listen to `--debug` or `--dry-run` properly yet - so it tries to talk to Confluence

The ARI docs generation DOES NOT handle dry-run or debug, it will try and talk to Confluence and it'll fail if you don't have credentials

If you are changing `publish-rest-api.py` then you'll likely need to change the interpretter at the top from python2.6

publish.sh looks for a pid file for Asterisk but it fails on my OS, I had to change the path so it worked - `line 202`

```
-        AST_PID=$(cat ${AST_DIR}/var/run/asterisk/asterisk.pid)
+        AST_PID=$(cat /var/run/asterisk/asterisk.pid)
```

I had to increase the sleep commands and add one in publish.sh

```
         killall -9 asterisk || true # || true so set -e doesn't kill us
+        sleep 10
         ${AST_DIR}/sbin/asterisk &
-        sleep 1
+        sleep 10
```

As sleeping 1 didn't wait long enough to quit Asterisk

Hopefully we'll sort these issues out fairly quickly but at least these are documented now
