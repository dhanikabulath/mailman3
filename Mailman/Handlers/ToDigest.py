# Copyright (C) 1998,1999,2000,2001,2002 by the Free Software Foundation, Inc.
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

"""Add the message to the list's current digest and possibly send it.
"""

# Messages are accumulated to a Unix mailbox compatible file containing all
# the messages destined for the digest.  This file must be parsable by the
# mailbox.UnixMailbox class (i.e. it must be ^From_ quoted).
#
# When the file reaches the size threshold, it is moved to the qfiles/digest
# directory and the DigestRunner will craft the MIME, rfc1153, and
# (eventually) URL-subject linked digests from the mbox.

import os
import re
import time
from types import ListType
from cStringIO import StringIO

from email.Parser import Parser
from email.Generator import Generator
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import getaddresses

from Mailman import mm_cfg
from Mailman import Utils
from Mailman import Message
from Mailman import i18n
from Mailman.MemberAdaptor import ENABLED
from Mailman.Handlers.Decorate import decorate
from Mailman.Queue.sbcache import get_switchboard
from Mailman.Mailbox import Mailbox

_ = i18n._


# rfc1153 says we should keep only these headers, and present them in this
# exact order.
KEEP = ['Date', 'From', 'To', 'Cc', 'Subject', 'Message-ID', 'Keywords',
        # I believe we should also keep these headers though.
        'In-Reply-To', 'References', 'Content-Type', 'MIME-Version',
        'Content-Transfer-Encoding', 'Precedence',
        # Mailman 2.0 adds these headers, but they don't need to be kept from
        # the original message: Message
        ]



def process(mlist, msg, msgdata):
    # Short circuit non-digestable lists.
    if not mlist.digestable or msgdata.get('isdigest'):
        return
    mboxfile = os.path.join(mlist.fullpath(), 'digest.mbox')
    omask = os.umask(007)
    try:
        mboxfp = open(mboxfile, 'a+')
    finally:
        os.umask(omask)
    g = Generator(mboxfp)
    g(msg, unixfrom=1)
    # Calculate the current size of the accumulation file.  This will not tell
    # us exactly how big the MIME, rfc1153, or any other generated digest
    # message will be, but it's the most easily available metric to decide
    # whether the size threshold has been reached.
    mboxfp.flush()
    size = os.path.getsize(mboxfile)
    if size / 1024.0 >= mlist.digest_size_threshhold:
        # This is a bit of a kludge to get the mbox file moved to the digest
        # queue directory.
        mboxfp.seek(0)
        send_digests(mlist, mboxfp)
        os.unlink(mboxfile)
    mboxfp.close()



def send_digests(mlist, mboxfp):
    # Set the digest volume and time
    if mlist.digest_last_sent_at:
        bump = 0
        # See if we should bump the digest volume number
        timetup = time.localtime(mlist.digest_last_sent_at)
        now = time.localtime(time.time())
        freq = mlist.digest_volume_frequency
        if freq == 0 and timetup[0] < now[0]:
            bump = 1                              # Yearly
        elif freq == 1 and timetup[1] <> now[1]:
            # Monthly, but we take a cheap way to calculate this.  We assume
            # that the clock isn't going to be reset backwards.
            bump = 1
        elif freq == 2 and (timetup[1] % 4 <> now[1] % 4):
            # Quarterly, same caveat
            bump = 1
        elif freq == 3:
            # Once again, take a cheap way of calculating this
            weeknum_last = int(time.strftime('%W', timetup))
            weeknum_now = int(time.strftime('%W', now))
            if weeknum_now > weeknum_last or timetup[0] > now[0]:
                bump = 1
        elif timetup[7] <> now[7]:
            # assume daily
            bump = 1
        if bump:
            mlist.volume += 1
            mlist.next_digest_number = 1
    mlist.digest_last_sent_at = time.time()
    # Wrapper around actually digest crafter to set up the language context
    # properly.  All digests are translated to the list's preferred language.
    otranslation = i18n.get_translation()
    i18n.set_language(mlist.preferred_language)
    try:
        send_i18n_digests(mlist, mboxfp)
    finally:
        i18n.set_translation(otranslation)



def send_i18n_digests(mlist, mboxfp):
    mbox = Mailbox(mboxfp)
    # Prepare common information
    lang = mlist.preferred_language
    realname = mlist.real_name
    volume = mlist.volume
    issue = mlist.next_digest_number
    digestid = _('%(realname)s Digest, Vol %(volume)d, Issue %(issue)d')
    # Set things up for the MIME digest.  Only headers not added by
    # CookHeaders need be added here.
    mimemsg = Message.Message()
    mimemsg['Content-Type'] = 'multipart/mixed'
    mimemsg['MIME-Version'] = '1.0'
    mimemsg['From'] = mlist.GetRequestEmail()
    mimemsg['Subject'] = digestid
    mimemsg['To'] = mlist.GetListEmail()
    # Set things up for the rfc1153 digest
    plainmsg = StringIO()
    rfc1153msg = Message.Message()
    rfc1153msg['From'] = mlist.GetRequestEmail()
    rfc1153msg['Subject'] = digestid
    rfc1153msg['To'] = mlist.GetListEmail()
    separator70 = '-' * 70
    separator30 = '-' * 30
    # In the rfc1153 digest, the masthead contains the digest boilerplate plus
    # any digest header.  In the MIME digests, the masthead and digest header
    # are separate MIME subobjects.  In either case, it's the first thing in
    # the digest, and we can calculate it now, so go ahead and add it now.
    mastheadtxt = Utils.maketext(
        'masthead.txt',
        {'real_name' :        mlist.real_name,
         'got_list_email':    mlist.GetListEmail(),
         'got_listinfo_url':  mlist.GetScriptURL('listinfo', absolute=1),
         'got_request_email': mlist.GetRequestEmail(),
         'got_owner_email':   mlist.GetOwnerEmail(),
         }, mlist=mlist)
    # MIME
    masthead = MIMEText(mastheadtxt, _charset=Utils.GetCharSet(lang))
    masthead['Content-Description'] = digestid
    mimemsg.add_payload(masthead)
    # rfc1153
    print >> plainmsg, mastheadtxt
    print >> plainmsg
    # Now add the optional digest header
    if mlist.digest_header:
        headertxt = decorate(mlist, mlist.digest_header, _('digest header'))
        # MIME
        header = MIMEText(headertxt)
        header['Content-Description'] = _('Digest Header')
        mimemsg.add_payload(header)
        # rfc1153
        print >> plainmsg, headertxt
        print >> plainmsg
    # Now we have to cruise through all the messages accumulated in the
    # mailbox file.  We can't add these messages to the plainmsg and mimemsg
    # yet, because we first have to calculate the table of contents
    # (i.e. grok out all the Subjects).  Store the messages in a list until
    # we're ready for them.
    #
    # Meanwhile prepare things for the table of contents
    toc = StringIO()
    print >> toc, _("Today's Topics:\n")
    # Now cruise through all the messages in the mailbox of digest messages,
    # building the MIME payload and core of the rfc1153 digest.  We'll also
    # accumulate Subject: headers and authors for the table-of-contents.
    messages = []
    msgcount = 0
    msg = mbox.next()
    while msg:
        msgcount += 1
        messages.append(msg)
        # Get the Subject header
        subject = msg.get('subject', _('(no subject)'))
        # Don't include the redundant subject prefix in the toc
        mo = re.match('(re:? *)?(%s)' % re.escape(mlist.subject_prefix),
                      subject, re.IGNORECASE)
        if mo:
            subject = subject[:mo.start(2)] + subject[mo.end(2):]
        addresses = getaddresses([msg.get('From', '')])
        username = ''
        # Take only the first author we find
        if type(addresses) is ListType and len(addresses) > 0:
            username = addresses[0][0]
        if username:
            username = ' (%s)' % username
        # Wrap the toc subject line
        wrapped = Utils.wrap('%2d. %s' % (msgcount, subject))
        # Split by lines and see if the username can fit on the last line
        slines = wrapped.split('\n')
        if len(slines[-1]) + len(username) > 70:
            slines.append(username)
        else:
            slines[-1] += username
        # Add this subject to the accumulating topics
        first = 1
        for line in slines:
            if first:
                print >> toc, ' ', line
                first = 0
            else:
                print >> toc, '     ', line
        # We do not want all the headers of the original message to leak
        # through in the digest messages.  For simplicity, we'll leave the
        # same set of headers in both digests, i.e. those required in rfc1153
        # plus a couple of other useful ones.  We also need to reorder the
        # headers according to rfc1153.
        keeper = {}
        for keep in KEEP:
            keeper[keep] = msg.get_all(keep, [])
        # Now remove all unkempt headers :)
        for header in msg.keys():
            del msg[header]
        # And add back the kept header in the rfc1153 designated order
        for keep in KEEP:
            for field in keeper[keep]:
                msg[keep] = field
        # And a bit of extra stuff
        msg['Message'] = `msgcount`
        # Get the next message in the digest mailbox
        msg = mbox.next()
    # Now we're finished with all the messages in the digest.  First do some
    # sanity checking and then on to adding the toc.
    if msgcount == 0:
        # Why did we even get here?
        return
    toctext = toc.getvalue()
    # MIME
    tocpart = MIMEText(toctext)
    tocpart['Content-Description']= _("Today's Topics (%(msgcount)d messages)")
    mimemsg.add_payload(tocpart)
    # rfc1153
    print >> plainmsg, toctext
    print >> plainmsg
    # For rfc1153 digests, we now need the standard separator
    print >> plainmsg, separator70
    print >> plainmsg
    # Now go through and add each message
    mimedigest = MIMEBase('multipart', 'digest')
    mimedigest.set_payload([])
    mimemsg.add_payload(mimedigest)
    first = 1
    for msg in messages:
        # MIME
        mimedigest.add_payload(msg)
        # rfc1153
        if first:
            first = 0
        else:
            print >> plainmsg, separator30
            print >> plainmsg
        g = Generator(plainmsg)
        g(msg, unixfrom=0)
    # Now add the footer
    if mlist.digest_footer:
        footertxt = decorate(mlist, mlist.digest_footer, _('digest footer'))
        # MIME
        footer = MIMEText(footertxt)
        footer['Content-Description'] = _('Digest Footer')
        mimemsg.add_payload(footer)
        # rfc1153
        # BAW: This is not strictly conformant rfc1153.  The trailer is only
        # supposed to contain two lines, i.e. the "End of ... Digest" line and
        # the row of asterisks.  If this screws up MUAs, the solution is to
        # add the footer as the last message in the rfc1153 digest.  I just
        # hate the way that VM does that and I think it's confusing to users,
        # so don't do it unless there's a clamor.
        print >> plainmsg, separator30
        print >> plainmsg
        print >> plainmsg, footertxt
        print >> plainmsg
    # Do the last bit of stuff for each digest type
    signoff = _('End of ') + digestid
    # MIME
    # BAW: This stuff is outside the normal MIME goo, and it's what the old
    # MIME digester did.  No one seemed to complain, probably because you
    # won't see it in an MUA that can't display the raw message.  We've never
    # got complaints before, but if we do, just wax this.  It's primarily
    # included for (marginally useful) backwards compatibility.
    mimemsg.postamble = signoff
    # rfc1153
    print >> plainmsg, signoff
    print >> plainmsg, '*' * len(signoff)
    # Do our final bit of housekeeping, and then send each message to the
    # outgoing queue for delivery.
    mlist.next_digest_number += 1
    virginq = get_switchboard(mm_cfg.VIRGINQUEUE_DIR)
    # Calculate the recipients lists
    plainrecips = []
    mimerecips = []
    drecips = mlist.getDigestMemberKeys() + mlist.one_last_digest.keys()
    for user in mlist.getMemberCPAddresses(drecips):
        # user might be None if someone who toggled off digest delivery
        # subsequently unsubscribed from the mailing list.  Also, filter out
        # folks who have disabled delivery.
        if user is None or mlist.getDeliveryStatus(user) <> ENABLED:
            continue
        # Otherwise, decide whether they get MIME or RFC 1153 digests
        if mlist.getMemberOption(user, mm_cfg.DisableMime):
            plainrecips.append(user)
        else:
            mimerecips.append(user)
    # Zap this since we're now delivering the last digest to these folks.
    mlist.one_last_digest.clear()
    # MIME
    virginq.enqueue(mimemsg, recips=mimerecips, listname=mlist.internal_name())
    # rfc1153
    rfc1153msg.add_payload(plainmsg.getvalue())
    virginq.enqueue(rfc1153msg,
                    recips = plainrecips,
                    listname = mlist.internal_name())
