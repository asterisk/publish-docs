#!/bin/sh

#
# Publish Asterisk documentation to the wiki
#

PROGNAME=$(basename $0)
TOPDIR=$(dirname $0)
TOPDIR=$(cd ${TOPDIR} && pwd)

if test -f ~/.asterisk-wiki.conf; then
   . ~/.asterisk-wiki.conf
fi

: ${SVN:=svn}
: ${GREP:=grep}
: ${MAKE:=make}

function fail()
{
    echo "${PROGNAME}: " "$@" >&2
    exit 1
}

if test $# -eq 0; then
    echo "usage: ${PROGNAME} [branch-name]" >&2
    exit 1
fi
BRANCH_NAME="$1"

#
# Check settings from config file
#
if ! test ${CONFLUENCE_URL}; then
    fail "CONFLUENCE_URL not set in ~/.asterisk-wiki.conf"
fi

if ! test ${CONFLUENCE_USER}; then
    fail "CONFLUENCE_USER not set in ~/.asterisk-wiki.conf"
fi

if ! test ${CONFLUENCE_PASSWORD}; then
    fail "CONFLUENCE_PASSWORD not set in ~/.asterisk-wiki.conf"
fi

# default space to AST
: ${CONFLUENCE_SPACE:=AST}

#
# Check repository
#
if ! test -f main/asterisk.c; then
    fail "Must run from an Asterisk checkout"
fi

#
# Check current working copy
#
CHANGES=$(${SVN} st --ignore-externals | grep -v '^X' | wc -l)
if test ${CHANGES} -ne 0; then
    fail "Asterisk checkout must be clean"
fi

unset HAS_REST_API
if test -d doc/rest-api; then
    HAS_REST_API=true
fi

set -ex

#
# Create a virtualenv to install dependencies
#
mkdir -p ~/virtualenv
if ! test -d ~/virtualenv/ast-publish-docs; then
    virtualenv ~/virtualenv/ast-publish-docs
fi
. ~/virtualenv/ast-publish-docs/bin/activate
pip install -Ur ${TOPDIR}/requirements.txt

if test configure -nt makeopts; then
    # Build into a temporary directory
    AST_DIR=$(mktemp -d /tmp/ast-docs.XXXXXX)
    trap "rm -rf $AST_DIR" EXIT

    ./configure --prefix=${AST_DIR} --enable-dev-mode=noisy
else
    # Dev machine already configured for building
    AST_DIR=$(sed -n "s/^prefix='\([^']*\)'/\1/ p" config.log)
fi

#
# Check ARI documentation consistency
#
if test ${HAS_REST_API}; then
    # Generate latest ARI documentation
    make ari-stubs

    # Ensure docs are consistent with the implementation
    CHANGES=$(${SVN} st --ignore-externals | grep -v '^X' | wc -l)
    if test ${CHANGES} -ne 0; then
	fail "Asterisk code out of date compared to the model"
    fi

    # make ari-stubs may modify the $Revision$ tags in a file; revert the
    # changes
    svn revert . -R -q
fi

#
# Don't publish docs for trunk. We still want the above validation to ensure
# that REST API docs are kept up to date.
#
if test ${BRANCH_NAME} = 'trunk'; then
    exit 0;
fi

#
# Publish the REST API. Pass the password via environment so it doesn't show
# up in the output.
#
PASSWORD="${CONFLUENCE_PASSWORD}" \
echo ${TOPDIR}/publish-rest-api.py --username="${CONFLUENCE_USER}" \
    --verbose \
    ${CONFLUENCE_URL} \
    ${CONFLUENCE_SPACE} \
    "Asterisk ${BRANCH_NAME}"

#
# XML docs need a live Asterisk to interact with, so build one
#
case ${BRANCH_NAME} in
    1.8|10*)
        # make full introduced in 11
        make all
        ;;
    *)
        make full
        ;;
esac
make install samples

if test $(uname -s) = Darwin; then
    ${AST_DIR}/sbin/asterisk &
    sleep 3
else
    ${AST_DIR}/sbin/asterisk -F
fi
rm -f ${TOPDIR}/full-en_US.xml
${AST_DIR}/sbin/asterisk -x "xmldoc dump ${TOPDIR}/full-en_US.xml"
${AST_DIR}/sbin/asterisk -x "core stop now"

#
# Publish XML documentation.
#

# Script assumes that it's running from TOPDIR
cd ${TOPDIR}

# Pass the password via environment so it doesn't show up in the output.
PASSWORD="${CONFLUENCE_PASSWORD}" \
echo ${TOPDIR}/astxml2wiki.py --username="${CONFLUENCE_USER}" \
    --server=${CONFLUENCE_URL} \
    --prefix="Asterisk ${BRANCH_NAME}" \
    --space="${CONFLUENCE_SPACE}" \
    --file=${TOPDIR}/full-en_US.xml \
    --debug -v
