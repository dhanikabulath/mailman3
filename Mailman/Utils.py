# Copyright (C) 1998,1999,2000,2001 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software 
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


"""Miscellaneous essential routines.

This includes actual message transmission routines, address checking and
message and address munging, a handy-dandy routine to map a function on all
the mailing lists, and whatever else doesn't belong elsewhere.

"""

import sys
import os
import re
import random
import urlparse
import sha
import errno
from string import whitespace as WHITESPACE

from mimelib.MsgReader import MsgReader

from Mailman import mm_cfg
from Mailman import Errors
from Mailman.SafeDict import SafeDict

EMPTYSTRING = ''
NL = '\n'
DOT = '.'



def list_exists(listname):
    """Return true iff list `listname' exists."""
    # It is possible that config.db got removed erroneously, in which case we
    # can fall back to config.db.last
    dbfile = os.path.join(mm_cfg.LIST_DATA_DIR, listname, 'config.db')
    lastfile = dbfile + '.last'
    return os.path.exists(dbfile) or os.path.exists(lastfile)


def list_names():
    """Return the names of all lists in default list directory."""
    got = []
    for fn in os.listdir(mm_cfg.LIST_DATA_DIR):
        if list_exists(fn):
            got.append(fn)
    return got



# a much more naive implementation than say, Emacs's fill-paragraph!
def wrap(text, column=70, honor_leading_ws=1):
    """Wrap and fill the text to the specified column.

    Wrapping is always in effect, although if it is not possible to wrap a
    line (because some word is longer than `column' characters) the line is
    broken at the next available whitespace boundary.  Paragraphs are also
    always filled, unless honor_leading_ws is true and the line begins with
    whitespace.  This is the algorithm that the Python FAQ wizard uses, and
    seems like a good compromise.

    """
    wrapped = ''
    # first split the text into paragraphs, defined as a blank line
    paras = re.split('\n\n', text)
    for para in paras:
        # fill
        lines = []
        fillprev = 0
        for line in para.split(NL):
            if not line:
                lines.append(line)
                continue
            if honor_leading_ws and line[0] in WHITESPACE:
                fillthis = 0
            else:
                fillthis = 1
            if fillprev and fillthis:
                # if the previous line should be filled, then just append a
                # single space, and the rest of the current line
                lines[-1] = lines[-1].rstrip() + ' ' + line
            else:
                # no fill, i.e. retain newline
                lines.append(line)
            fillprev = fillthis
        # wrap each line
        for text in lines:
            while text:
                if len(text) <= column:
                    line = text
                    text = ''
                else:
                    bol = column
                    # find the last whitespace character
                    while bol > 0 and text[bol] not in WHITESPACE:
                        bol = bol - 1
                    # now find the last non-whitespace character
                    eol = bol
                    while eol > 0 and text[eol] in WHITESPACE:
                        eol = eol - 1
                    # watch out for text that's longer than the column width
                    if eol == 0:
                        # break on whitespace after column
                        eol = column
                        while eol < len(text) and \
                              text[eol] not in WHITESPACE:
                            eol = eol + 1
                        bol = eol
                        while bol < len(text) and \
                              text[bol] in WHITESPACE:
                            bol = bol + 1
                        bol = bol - 1
                    line = text[:eol+1] + '\n'
                    # find the next non-whitespace character
                    bol = bol + 1
                    while bol < len(text) and text[bol] in WHITESPACE:
                        bol = bol + 1
                    text = text[bol:]
                wrapped = wrapped + line
            wrapped = wrapped + '\n'
            # end while text
        wrapped = wrapped + '\n'
        # end for text in lines
    # the last two newlines are bogus
    return wrapped[:-2]
    


def QuotePeriods(text):
    JOINER = '\n .\n'
    SEP = '\n.\n'
    return JOINER.join(text.split(SEP))


# TBD: what other characters should be disallowed?
_badchars = re.compile('[][()<>|;^,]')

def ValidateEmail(str):
    """Verify that the an email address isn't grossly invalid."""
    # Pretty minimal, cheesy check.  We could do better...
    if not str:
        raise Errors.MMBadEmailError
    if _badchars.search(str) or str[0] == '-':
        raise Errors.MMHostileAddress
    if str.find('/') <> -1 and \
       os.path.isdir(os.path.split(str)[0]):
        # then
        raise Errors.MMHostileAddress
    user, domain_parts = ParseEmail(str)
    # this means local, unqualified addresses, are no allowed
    if not domain_parts:
        raise Errors.MMBadEmailError
    if len(domain_parts) < 2:
	raise Errors.MMBadEmailError



# User J. Person <person@allusers.com>
_addrcre1 = re.compile('<(.*)>')
# person@allusers.com (User J. Person)
_addrcre2 = re.compile('([^(]*)\s(.*)')

def ParseAddrs(addresses):
    """Parse common types of email addresses:

    User J. Person <person@allusers.com>
    person@allusers.com (User J. Person)

    TBD: I wish we could use rfc822.parseaddr() but 1) the interface is not
    convenient, and 2) it doesn't work for the second type of address.

    Argument is a list of addresses, return value is a list of the parsed
    email addresses.  The argument can also be a single string, in which case
    the return value is a single string.  All addresses are string.strip()'d.

    """
    single = 0
    if type(addresses) == type(''):
        single = 1
        addrs = [addresses]
    else:
        addrs = addresses
    parsed = []
    for a in addrs:
        mo = _addrcre1.search(a)
        if mo:
            parsed.append(mo.group(1))
            continue
        mo = _addrcre2.search(a)
        if mo:
            parsed.append(mo.group(1))
            continue
        parsed.append(a)
    if single:
        return parsed[0].strip()
    return [s.strip() for s in parsed]



def GetPathPieces(envar='PATH_INFO'):
    path = os.environ.get(envar)
    if path:
        return [p for p in path.split('/') if p]
    return None



def ScriptURL(target, web_page_url=None, absolute=0):
    """target - scriptname only, nothing extra
    web_page_url - the list's configvar of the same name
    absolute - a flag which if set, generates an absolute url
    """
    if web_page_url is None:
        web_page_url = mm_cfg.DEFAULT_URL
        if web_page_url[-1] <> '/':
            web_page_url = web_page_url + '/'
    fullpath = os.environ.get('REQUEST_URI')
    if fullpath is None:
        fullpath = os.environ.get('SCRIPT_NAME', '') + \
                   os.environ.get('PATH_INFO', '')
    baseurl = urlparse.urlparse(web_page_url)[2]
    if not absolute and fullpath[:len(baseurl)] == baseurl:
        # Use relative addressing
        fullpath = fullpath[len(baseurl):]
        i = fullpath.find('?')
        if i > 0:
            count = fullpath.count('/', 0, i)
        else:
            count = fullpath.count('/')
        path = ('../' * count) + target
    else:
        path = web_page_url + target
    return path + mm_cfg.CGIEXT



# This takes an email address, and returns a tuple containing (user,host)
def ParseEmail(email):
    user = None
    domain = None
    email = email.lower()
    at_sign = email.find('@')
    if at_sign < 1:
	return (email, None)
    user = email[:at_sign]
    rest = email[at_sign+1:]
    domain = rest.split('.')
    return user, domain


def LCDomain(addr):
    "returns the address with the domain part lowercased"
    atind = addr.find('@')
    if atind == -1: # no domain part
        return addr
    return addr[:atind] + '@' + addr[atind+1:].lower()



# Return 1 if the 2 addresses match.  0 otherwise.
# Might also want to match if there's any common domain name...
# There's password protection anyway.
def AddressesMatch(addr1, addr2):
    "True when username matches and host addr of one addr contains other's."
    addr1, addr2 = map(LCDomain, [addr1, addr2])
    if not mm_cfg.SMART_ADDRESS_MATCH:
        return addr1 == addr2
    user1, domain1 = ParseEmail(addr1)
    user2, domain2 = ParseEmail(addr2)
    if user1 != user2:
	return 0
    if domain1 == domain2:
        return 1
    elif not domain1 or not domain2:
        return 0
    for i in range(-1 * min(len(domain1), len(domain2)), 0):
        # By going from most specific component of host part we're likely
        # to hit a difference sooner.
        if domain1[i] != domain2[i]:
            return 0
    return 1



def GetPossibleMatchingAddrs(name):
    """returns a sorted list of addresses that could possibly match
    a given name.

    For Example, given scott@pobox.com, return ['scott@pobox.com'],
    given scott@blackbox.pobox.com return ['scott@blackbox.pobox.com',
                                           'scott@pobox.com']"""
    
    name = name.lower()
    user, domain = ParseEmail(name)
    res = [name]
    if domain:
        domain = domain[1:]
        while len(domain) >= 2:
            res.append("%s@%s" % (user, DOT.join(domain)))
            domain = domain[1:]
    return res



def List2Dict(list):
    """List2Dict returns a dict keyed by the entries in the list
    passed to it."""
    res = {}
    for item in list:
        res[item] = 1
    return res


def FindMatchingAddresses(name, dict, *dicts):
    """Given an email address, and any number of dictionaries keyed by
    email addresses, returns the subset of the list that matches the
    given address.  Should sort based on exactness of match,
    just in case."""
    dicts = list(dicts)
    dicts.insert(0, dict)
    if not mm_cfg.SMART_ADDRESS_MATCH:
        for d in dicts:
            if d.has_key(name.lower()):
                return [name]
        return []
    #
    # GetPossibleMatchingAddrs return string.lower'd values
    #
    p_matches = GetPossibleMatchingAddrs(name) 
    res = []
    for pm in p_matches:
        for d in dicts:
            if d.has_key(pm):
                res.append(pm)
    return res

  

_vowels = ('a', 'e', 'i', 'o', 'u')
_consonants = ('b', 'c', 'd', 'f', 'g', 'h', 'k', 'm', 'n',
               'p', 'r', 's', 't', 'v', 'w', 'x', 'z')
_syllables = []

for v in _vowels:
    for c in _consonants:
        _syllables.append(c+v)
        _syllables.append(v+c)

def MakeRandomPassword(length=6):
    syls = []
    while len(syls)*2 < length:
        syls.append(random.choice(_syllables))
    return EMPTYSTRING.join(syls)[:length]

def GetRandomSeed():
    chr1 = int(random.random() * 52)
    chr2 = int(random.random() * 52)
    def mkletter(c):
        if 0 <= c < 26:
            c = c + 65
        if 26 <= c < 52:
            c = c - 26 + 97
        return c
    return "%c%c" % tuple(map(mkletter, (chr1, chr2)))



def set_global_password(pw, siteadmin=1):
    if siteadmin:
        filename = mm_cfg.SITE_PW_FILE
    else:
        filename = mm_cfg.LISTCREATOR_PW_FILE
    omask = os.umask(026)                         # rw-r-----
    try:
        fp = open(filename, 'w')
        fp.write(sha.new(pw).hexdigest() + '\n')
        fp.close()
    finally:
        os.umask(omask)
    

def check_global_password(response, siteadmin=1):
    if siteadmin:
        filename = mm_cfg.SITE_PW_FILE
    else:
        filename = mm_cfg.LISTCREATOR_PW_FILE
    try:
        fp = open(filename)
        challenge = fp.read()[:-1]                # strip off trailing nl
        fp.close()
    except IOError, e:
        if e.errno <> errno.ENOENT: raise
        # It's okay not to have a site admin password, just return false
        return 0
    return challenge == sha.new(response).hexdigest()



def QuoteHyperChars(str):
    from cgi import escape
    return escape(str, quote=1)



# Just changing these two functions should be enough to control the way
# that email address obscuring is handled.
def ObscureEmail(addr, for_text=0):
    """Make email address unrecognizable to web spiders, but invertable.

    When for_text option is set (not default), make a sentence fragment
    instead of a token."""
    if for_text:
	return addr.replace('@', ' at ')
    else:
	return addr.replace('@', '--at--')

def UnobscureEmail(addr):
    """Invert ObscureEmail() conversion."""
    # Contrived to act as an identity operation on already-unobscured
    # emails, so routines expecting obscured ones will accept both.
    return addr.replace('--at--', '@')



def maketext(templatefile, dict=None, raw=0, lang=None):
    """Make some text from a template file.

    Reads the `templatefile', relative to mm_cfg.TEMPLATE_DIR, does string
    substitution by interpolating in the `dict', and if `raw' is false,
    wraps/fills the resulting text by calling wrap().
    """
    if lang is None:
        lang = mm_cfg.DEFAULT_SERVER_LANGUAGE
    if dict is None:
        dict = {}
    file = os.path.join(mm_cfg.TEMPLATE_DIR, lang, templatefile)
    try:
        fp = open(file)
    except IOError, e:
        if e.errno <> errno.ENOENT: raise
        # The language specific template directory may not yet exist
        file = os.path.join(mm_cfg.TEMPLATE_DIR, templatefile)
        fp = open(file)
    template = fp.read()
    fp.close()
    try:
        text = template % SafeDict(dict)
    except TypeError:
        # The template is really screwed up
        text = template
    if raw:
        return text
    return wrap(text)



ADMINDATA = {
    # admin keyword: (minimum #args, maximum #args)
    'subscribe':   (0, 3),
    'unsubscribe': (0, 1),
    'who':         (0, 0),
    'info':        (0, 0),
    'lists':       (0, 0),
    'set':         (3, 3),
    'help':        (0, 0),
    'password':    (2, 2),
    'options':     (0, 0),
    'remove':      (0, 0),
    }

# Given a Message.Message object, test for administrivia (eg subscribe,
# unsubscribe, etc).  The test must be a good guess -- messages that return
# true get sent to the list admin instead of the entire list.
def is_administrivia(msg):
    reader = MsgReader(msg)
    linecnt = 0
    lines = []
    while 1:
        line = reader.readline()
        if not line:
            break
        # Strip out any signatures
        if line == '-- ':
            break
        if line.strip():
            linecnt += 1
        if linecnt > mm_cfg.DEFAULT_MAIL_COMMANDS_MAX_LINES:
            return 0
        lines.append(line)
    bodytext = NL.join(lines)
    # See if the body text has only one word, and that word is administrivia
    if ADMINDATA.has_key(bodytext.strip().lower()):
        return 1
    # See if the subect has only one word, and that word is administrivia
    if ADMINDATA.has_key(msg.get('subject', '').strip().lower()):
        return 1
    # Look at the first N lines and see if there is any administrivia on the
    # line.  BAW: N is currently hardcoded to 5.
    for line in lines[:5]:
        if not line.strip():
            continue
        words = [word.lower() for word in line.split()]
        minargs, maxargs = ADMINDATA.get(words[0], (None, None))
        if minargs is None and maxargs is None:
            continue
        if minargs <= len(words[1:]) <= maxargs:
            # Special case the `set' keyword.  BAW: I don't know why this is
            # here.
            if words[0] == 'set' and words[2] not in ('on', 'off'):
                continue
            return 1
    return 0

        

def mkdir(dir, mode=02775):
    """Wraps os.mkdir() in a umask saving try/finally.

    Two differences from os.mkdir():
        - umask is forced to 0 during mkdir()
        - default mode is 02775
    """
    ou = os.umask(0)
    try:
        os.mkdir(dir, mode)
    finally:
        os.umask(ou)


def rmdirhier(dir):
    """Like `rm -r'

    Completely and recursively removes a directory and all its contents,
    unlike os.removedirs().
    """
    files = []
    def ls(arg, dirname, names):
        for name in names:
            arg.append(os.path.join(dirname, name))
    os.path.walk(dir, ls, files)
    files.reverse()
    for file in files:
        if os.path.isdir(file):
            os.rmdir(file)
        else:
            os.unlink(file)
    os.rmdir(dir)



def GetRequestURI(fallback=None):
    """Return the full virtual path this CGI script was invoked with.

    Newer web servers seems to supply this info in the REQUEST_URI
    environment variable -- which isn't part of the CGI/1.1 spec.
    Thus, if REQUEST_URI isn't available, we concatenate SCRIPT_NAME
    and PATH_INFO, both of which are part of CGI/1.1.

    Optional argument `fallback' (default `None') is returned if both of
    the above methods fail.

    """
    if os.environ.has_key('REQUEST_URI'):
        return os.environ['REQUEST_URI']
    elif os.environ.has_key('SCRIPT_NAME') and os.environ.has_key('PATH_INFO'):
        return os.environ['SCRIPT_NAME'] + os.environ['PATH_INFO']
    else:
        return fallback



# Wait on a dictionary of child pids
def reap(kids, func=None, once=0):
    while kids:
        if func:
            func()
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except OSError, e:
            # If the child procs had a bug we might have no children
            if e.errno <> errno.ECHILD:
                raise
            kids.clear()
            break
        if pid <> 0:
            try:
                del kids[pid]
            except KeyError:
                # Huh?  How can this happen?
                pass
        if once:
            break


def GetDirectories(path):
    from os import listdir
    from os.path import isdir, join
    return [f for f in listdir(path) if isdir(join(path, f))]


def GetLanguageDescr(lang):
    return mm_cfg.LC_DESCRIPTIONS[lang][0]


def GetCharSet(lang):
    return mm_cfg.LC_DESCRIPTIONS[lang][1]



def get_domain():
    host = os.environ.get('HTTP_HOST', os.environ.get('SERVER_NAME'))
    port = os.environ.get('SERVER_PORT')
    # Strip off the port if there is one
    if port and host.endswith(':' + port):
        host = host[:-len(port)-1]
    if mm_cfg.VIRTUAL_HOST_OVERVIEW and host:
        return host
    else:
        return mm_cfg.DEFAULT_HOST_NAME
