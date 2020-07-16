#!/usr/bin/env python

"""Update Confluence with Swagger output.
"""

import difflib
import getpass
import os
import sys
import xmlrpclib
import xml.dom.minidom

from optparse import OptionParser
from xmlrpclib import Server

def fail(msg):
    print >> sys.stderr, msg
    sys.exit(1)

def read_fully(file):
    fd = open(file, 'r')
    try:
        return fd.read()
    finally:
        fd.close()

def main(argv):
    parser = OptionParser(usage = "usage: %prog [options] http://server/wiki/rpc/xmlrpc SPACE 'Asterisk 12'")
    parser.add_option("--username", dest="username", help="Confluence username")
    parser.add_option("--password", dest="password", help="Confluence password")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Verbose output")
    parser.add_option("--dry-run", action="store_true", dest="dry_run", default=False, help="Don't make changes")
    parser.add_option("--ast-version", default="Unknown version",
                      help="Asterisk version string, including SVN info")

    (options, args) = parser.parse_args(argv)

    if len(args) != 4:
        parser.error("Wrong number of arguments")

    url = args[1]
    space = args[2]
    prefix = args[3]
    wikidir = 'doc/rest-api'

    if not options.username:
        options.username = getpass.getuser()

    # If password isn't on the command line, check the environment
    if not options.password:
        options.password = os.environ.get('CONFLUENCE_PASSWORD')

    # If not there, prompt for it
    if not options.password:
        options.password = getpass.getpass()

    server = Server(url)
    try:
        token = server.confluence2.login(options.username, options.password)
        api = server.confluence2
        convert = True
    except:
        token = server.confluence1.login(options.username, options.password)
        api = server.confluence1
        convert = False

    if not token:
        fail("Could not log into Confluence!")

    try:
        parent = api.getPage(token, space, "%s ARI" % prefix)
        parentId = parent['id']
    except xmlrpclib.Fault, e:
        print("Page '%s ARI' doesn't exist" % prefix)
        if options.dry_run:
            print("Returning (dry run)")
            return
        else:
            print("Creating '%s ARI'" % prefix)
            parent = api.getPage(token, space, "%s Command Reference" % prefix)

            newpage = {
                'space': space,
                'parentId': parent['id'],
                'title': "%s ARI" % prefix,
                'content': "",
            }
            api.storePage(token, newpage)
            parent = api.getPage(token, space, "%s ARI" % prefix)
            parentId = parent['id']

    if options.verbose:
        print >> sys.stderr, "Parent page id %s" % parentId

    for wiki in os.listdir(wikidir):
        if not wiki.endswith('.wiki') or not wiki.startswith(prefix):
            print >> sys.stderr, "Unexpected file '%s' in wiki directory" % wiki
            continue
        page_title = wiki.replace('.wiki', '')
        wiki = os.path.join(wikidir, wiki)

        comment = {
            'minorEdit': True,
            'versionComment': 'Update to %s' % options.ast_version
        }
        content = read_fully(wiki)

        # convert wiki markup to storage format, if needed
        # Confluence is inconsistent how it renders <br/> tags. ugh.
        if convert:
            content = api.convertWikiToStorageFormat(token, content).replace("<br />", "<br/>")

        try:
            page = api.getPage(token, space, page_title)
            oldcontent = page['content']

            if convert:
                oldcontent = oldcontent.replace("<br />", "<br/>").replace("&quot;", "\"")

            if oldcontent != content:
                page['content'] = content
                page['parentId'] = parentId

                if options.dry_run:
                    print "Updating %s (dry run)" % page_title
		else:
                    print "Updating %s" % page_title
                    api.updatePage(token, page, comment)
                if options.verbose:
                    diff = difflib.unified_diff(oldcontent.splitlines(1), content.splitlines(1), fromfile=page_title, tofile=wiki)
                    for line in diff:
                        sys.stdout.write(line)
            else:
                if options.verbose:
                    print "Skipping %s (up to date)" % page_title
        except xmlrpclib.Fault, e:
            newpage = {
                'space': space,
                'parentId': parentId,
                'title': page_title,
                'content': content,
            }
            if options.dry_run:
                print "Creating %s (dry run)" % page_title
	    else:
                print "Creating %s" % page_title
                api.storePage(token, newpage)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
