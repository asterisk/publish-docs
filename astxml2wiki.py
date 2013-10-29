#!/usr/bin/env python

import sys, os, re, difflib
import lxml.etree as etree
import version
import string
from optparse import OptionParser
import subprocess
from xmlrpclib import Server

def escape(string):
    return re.sub(r'([\{\}\[\]^_])', r'\\\1', string)

def call(*args, **kwargs):
    '''Invokes subprocess.call, calling sys.exit if it fails'''
    res = subprocess.call(*args, **kwargs)
    if res != 0:
        print >> sys.stderr, "Failed to call: %s %s\n" % (args, kwargs)
        sys.exit(1)

class AstXML2Wiki:
    def __init__(self, argv):
        usage = "Usage: ./astxml2wiki.py " \
            "--username=USERNAME --password=PASSWORD " \
            "--server=http://example.com/rpc/xmlrpc " \
            "--prefix=\"Asterisk 10\" " \
            "--svn=http://domain.com/branch|" \
            "--file=/path/to/core-en_US.xml [--force] " \
            "--debug " \
            "--force-convert " \
            "--diff"
            # the debug flag obviates any need for user, password, or server
            # and will make no attempt to contact the server even if provided

        self._markup_tags = {
            'filename': ('{{','}}'),
            'directory': ('{{','}}'),
            'emphasis': ('*','*'),
            'variable': ('{{','}}'),
            'literal': ('{{','}}'),
            'replaceable': ('_','_'),
            'astcli': ('{{','}}')}

        self.s = ''
        self.path = ''
        self.ast_v = 'Unknown'
        self.token = ''
        self.thingschanged = True
        self.elements = []
        self.args = {
            'server': '',
            'space': 'AST',
            'prefix': '',
            'username': '',
            'password': '',
            'svn': '',
            'file': '',
            'force': False,
            'v': False,
            'debug': False,
            'force-convert': False,
            'diff': False
        }
        self.processed = {
            'unchanged': 0,
            'updated': 0,
            'created': 0
        }

        argv.pop(0)
        for a in argv:
            pieces = a.split("=", 1)
            try:
                self.args[pieces[0].strip('-')] = pieces[1]
            except:
                self.args[pieces[0].strip('-')] = True

        if self.args['prefix'] == 'AST':
            self.args['prefix'] = ''
        else:
            if self.args['prefix'] != '':
                self.args['prefix'] = self.args['prefix'] + ' '

        self.parent = {
            'manager': self.args['prefix'] + 'AMI Actions',
            'function': self.args['prefix'] + 'Dialplan Functions',
            'application': self.args['prefix'] + 'Dialplan Applications',
            'agi': self.args['prefix'] + 'AGI Commands',
            'managerEvent': self.args['prefix'] + 'AMI Events',
            'configInfo': self.args['prefix'] + 'Module Configuration'
        }

        if self.args['file'] == '' and self.args['svn'] == '':
            print >> sys.stderr, "Please specify a path to core-en_US.xml or an SVN URL."
            print >> sys.stderr, usage
            sys.exit(2)

        self.convert = False

        # If password isn't on the command line, check the environment
        if not self.args['password']:
            self.args['password'] = os.environ.get('PASSWORD', '')

        if not self.args['debug'] or self.args['force-convert']:
            if self.args['username'] == '' or self.args['password'] == '':
                print >> sys.stderr, "Please specify a username and a password."
                sys.exit(1)

            if self.args['space'] == '':
                print >> sys.stderr, "Please specify which Confluence space to use."
                sys.exit(5)

            if self.args['server'] == '' or \
                re.search(r'xmlrpc', self.args['server']) is None:
                print >> sys.stderr, "Please specify a Confluence XMLRPC URL."
                sys.exit(3)

            self.s = Server(self.args['server'])
            try:
                self.token = self.s.confluence2.login(
                    self.args['username'], self.args['password']
                )
                self.api = self.s.confluence2
                self.convert = True
            except:
                self.token = self.s.confluence1.login(
                    self.args['username'], self.args['password']
                )
                self.api = self.s.confluence1

            if self.token is None or self.token == '':
                print >> sys.stderr, "Could not log into Confluence!"
                sys.exit(4)

    def build(self):
        ''' checkout Asterisk from source and build the documentation to use.
        This only gets run if a subversion repository URL is passed to the
        script.'''

        self.path = os.getcwd()
        self.svndir = self.args['svn']
        pieces = self.svndir.rsplit('/', 1)
        self.svndir = 'workdirs/' + pieces[1]
        if self.args['v'] is True:
            print "svndir is", self.svndir

        # Checkout branch from subversion
        if not os.path.exists(self.svndir):
            call("svn checkout -q " + self.args['svn'] + " " + self.svndir, shell=True)
            os.chdir(self.path + "/" + self.svndir)
        else:
            # Update the existing repository
            os.chdir(self.path + "/" + self.svndir)
            call("svn up -q", shell=True)

        # run configure script; make docs and version; extract version
        # Even --quiet isn't as quiet as it should be
        with open(os.devnull, "w") as devnull:
            out = devnull
            err = devnull
            if self.args['v'] is True:
                out = sys.stdout
                err = sys.stderr
            call("./configure", stdout=out, stderr=err, shell=True)
            if self.svndir == 'workdirs/1.8' or self.svndir == 'workdirs/10':
                call("make -s doc/core-en_US.xml", stdout=out, stderr=err, shell=True)
            else:
                call("make -s doc/full-en_US.xml", stdout=out, stderr=err, shell=True)

        res_verproc = subprocess.Popen("export GREP=grep; export AWK=awk; " + \
            self.path + "/" + self.svndir + "/build_tools/make_version " + \
            self.path + "/" + self.svndir, shell=True, \
            stdout=subprocess.PIPE)
        res_ver = subprocess.Popen.communicate(res_verproc)
        self.ast_v = res_ver[0].rstrip('\n')
        self.ast_v = str(version.AsteriskVersion(self.ast_v))
        if self.args['v'] is True:
            print "version: ", self.ast_v

        self.args['file'] = self.path + "/" + self.svndir + "/doc/core-en_US.xml"
        os.chdir(self.path)

    def build_paragraph_contents(self, node):
        ''' First pass on the XML node.  For each para node, we need to replace
        out the formatting markup - using an XSLT to do this job is tricky, as
        it won't necessarily preserve the order of text/markup '''
        for paragraph in node.getiterator('para'):
            current_text = ''
            if paragraph.text:
                children = paragraph.getchildren()
		# Emulate the itertext function
		paragraph_text = []
		for p in paragraph.getiterator():
		    if p.text:
                        paragraph_text.append(p.text)
                    if p.tail:
                        paragraph_text.append(p.tail)

                for t in paragraph_text:
                    match = [markup for markup in children if markup.text == t]
                    if len(match):
                        # Just use the first.
                        markup = match[0]
                        if markup.tag in self._markup_tags.keys():
                            current_text += '%s%s%s' % (self._markup_tags[markup.tag][0], \
                            escape(t), self._markup_tags[markup.tag][1])
                    else:
                        current_text += escape(t)
                for c in children:
                    paragraph.remove(c)
                paragraph.text = current_text.replace('\n', ' ').replace('\t','')

        # values may also need to be escaped
        for value in node.getiterator('value'):
            if value.text:
                value.text = escape(value.text)
            # escape [] in names
            if 'name' in value.attrib:
                value.set('name', escape(value.get('name')))

        return node

    def build_seealso_references(self, node):
        refnodes = node.getiterator('ref')
        for refnode in refnodes:
            type = refnode.attrib.get('type')
            module = refnode.attrib.get('module')
            if not module:
                module = ''
            else:
                module = '_%s' % module
            link = refnode.text
            if type == 'manager':
                link = '[' + self.args['prefix'] + 'ManagerAction_%s%s]\n' % (link, module)
            elif type == 'application':
                link = '[' + self.args['prefix'] + 'Application_%s%s]\n' % (link, module)
            elif type == 'function':
                link = '[' + self.args['prefix'] + 'Function_%s%s]\n' % (link, module)
            elif type == 'agi':
                link = '[' + self.args['prefix'] + 'AGICommand_%s%s]\n' % (link, module)
            elif type == 'managerEvent':
                link = '[' + self.args['prefix'] + 'ManagerEvent_%s%s]\n' % (link, module)
            elif type == 'configInfo':
                link = '[' + self.args['prefix'] + 'Configuration_%s%s]\n' % (link, module)
            else:
                # This is either "filename" or "manpage"
                link = '{{%s}}\n' % link
            refnode.text = link

        return node

    def parse(self):
        ''' Collect and do the first pass of formatting on the XML nodes for each
        major type '''

	print self.args['file']
        self.xmltree = etree.parse(self.args['file'])
        self.xmltree.xinclude()
        for child in self.xmltree.getiterator():
            if child.tag == 'application' or \
                child.tag == 'manager' or \
                child.tag == 'agi' or \
                child.tag == 'function' or \
                child.tag == 'configInfo' or \
                child.tag == 'managerEvent':

                # Two things have to be constructed here.  The paragraph contents,
                # as we have XML embedded with text - and that's just not easy to
                # do in XSLT (without doing multiple XSLT passes).  The ref links
                # have to be built here, as we have the information to build the
                # page links based on what was passed in to this script.
                child = self.build_paragraph_contents(child)
                child = self.build_seealso_references(child)
                self.elements.append(child)


    def update(self):
        ''' format the wiki pages and update Confluence '''

        newpage = {'space': self.args['space']}
        xslt = etree.XSLT(etree.parse('astxml2wiki.xslt'))
        topics = ['manager','application','function','agi',]
        if not hasattr(self, 'svndir') or not self.svndir == 'workdirs/1.8' and not self.svndir == 'workdirs/10':
            topics.append('managerEvent')
        if not hasattr(self, 'svndir') or not self.svndir == 'workdirs/1.8' and not self.svndir == 'workdirs/10' and not self.svndir == 'workdirs/11':
            topics.append('configInfo')

        for f in topics:
            # Get the ids of the parent pages
            if not self.args['debug']:
                if self.args['v'] is True:
                    print "getPage(%s, %s, %s)" % (self.token, self.args['space'], self.parent[f])

                elpage = self.api.getPage(
                    self.token, self.args['space'], self.parent[f]
                )
                self.parent[f] = elpage['id']

        if self.args['v'] is True:
            print "Updating Confluence"

        for node in self.elements:
            name = node.attrib.get('name')
            module = node.attrib.get('module')
            if not name:
                raise ValueError('name undefined for node')
            if node.tag == 'manager':
                pagetitle = 'ManagerAction_%s' % name
            elif node.tag == 'application':
                pagetitle = 'Application_%s' % name
            elif node.tag == 'function':
                pagetitle = 'Function_%s' % name
            elif node.tag == 'agi':
                pagetitle = 'AGICommand_%s' % name
            elif node.tag == 'managerEvent':
                pagetitle = 'ManagerEvent_%s' % name
            elif node.tag == 'configInfo':
                pagetitle = 'Configuration_%s' % name
            if module:
                pagetitle = '%s_%s' % (pagetitle, module)

            pagetitle = self.args['prefix'] + pagetitle

            wiki = str(xslt(node))
            wiki += "\nh3. Import Version\n\n"
            wiki += ("This documentation was imported from Asterisk Version %s" %
                (self.ast_v))

            # convert wiki markup to storage format, if needed
            # Confluence is inconsistent how it renders <br/> tags. ugh.
            if self.convert:
                wiki = self.api.convertWikiToStorageFormat(self.token, wiki)

            if self.args['debug']:
                print pagetitle
                print wiki
                continue

            try:
                oldpage = self.api.getPage(
                    self.token, self.args['space'], pagetitle
                )
                elpage = oldpage.copy()

                elpage['content'] = wiki
                elpage['title'] = pagetitle
                elpage['parentId'] = str(self.parent[node.tag])
                oldcontent = oldpage['content'].split("This documentation was imported from")[0]
                newcontent = elpage['content'].split("This documentation was imported from")[0]

                # The resulting XML has meaningless inconsistencies.
                # Hack it into submission.
                oldcontent = oldcontent.replace("&quot;", '"').replace("<br />", "<br/>").replace('<ul class="alternate">', '<ul class="alternate" type="square">').replace(' class="external-link"', "")
                newcontent = newcontent.replace("&#94;", "^").replace("&#8211;", "&ndash;").replace("&#41;", ")").replace("&#95;", "_").replace(' class="external-link"', "")

                if oldcontent != newcontent or self.args['force'] is True:
                    if self.args['v']:
                        print elpage['title'], " updated"
                        self.processed['updated'] += 1
                    if self.args['diff']:
                        diff = difflib.unified_diff(oldcontent.splitlines(1),
                                                    newcontent.splitlines(1),
                                                    fromfile=pagetitle,
                                                    tofile=pagetitle)
                        for line in diff:
                            sys.stdout.write(line)
                    else:
                        self.api.updatePage(self.token, elpage, {
                            'minorEdit': True,
                            'versionComment': 'Updated to' + self.ast_v
                        })

            except:
                newpage['title'] = pagetitle
                newpage['content'] = wiki
                newpage['parentId'] = str(self.parent[node.tag])
                if self.args['diff']:
                    print "%s created" % pagetitle
                else:
                    try:
                        page = self.api.storePage(self.token, newpage)
                        if self.args['v']:
                            print newpage['title'], " created"
                            self.processed['created'] += 1
                    except:
                        pass


def main(argv):
    '''
    Usage: ./astxml2wiki.py [--svn=yes|no] [--file=/path/to/core-en_US.xml]
[--username=USERNAME --password=PASSWORD]
[--server=http://example.com/rpc/xmlrpc]
[--prefix="Asterisk 10"]
[-v]
    '''

    a = AstXML2Wiki(argv)
    if a.args['svn'] != '':
        a.build()

    a.parse()

    a.update()
    if a.args['debug']:
        return 0
    if a.args['v'] is True:
        for k in a.processed:
            print k, " ", a.processed[k]

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
