# Copyright (C) 2001-2009 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <http://www.gnu.org/licenses/>.

"""Creation/deletion hooks for the Postfix MTA."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    'LMTP',
    ]


import os
import grp
import pwd
import time
import errno
import logging
import datetime

from locknix.lockfile import Lock
from zope.interface import implements

from mailman import Utils
from mailman.config import config
from mailman.interfaces.mta import IMailTransportAgent
from mailman.i18n import _

log = logging.getLogger('mailman.error')

LOCKFILE = os.path.join(config.LOCK_DIR, 'mta')
SUBDESTINATIONS = (
    'bounces',  'confirm',  'join',         'leave',
    'owner',    'request',  'subscribe',    'unsubscribe',
    )



class LMTP:
    """Connect Mailman to Postfix via LMTP."""

    implements(IMailTransportAgent)

    def create(self, mlist):
        """See `IMailTransportAgent`."""
        # Acquire a lock file to prevent other processes from racing us here.
        with Lock(LOCKFILE):
            # We can ignore the mlist argument because for LMTP delivery, we
            # just generate the entire file every time.
            self._do_write_file()

    delete = create

    def regenerate(self):
        """See `IMailTransportAgent`."""
        # Acquire a lock file to prevent other processes from racing us here.
        with Lock(LOCKFILE):
            self._do_write_file()

    def _do_write_file(self):
        """Do the actual file writes for list creation."""
        # Open up the new alias text file.
        path = os.path.join(config.DATA_DIR, 'postfix_lmtp')
        # Sort all existing mailing list names first by domain, then my local
        # part.  For postfix we need a dummy entry for the domain.
        by_domain = {}
        for mailing_list in config.db.list_manager.mailing_lists:
            by_domain.setdefault(mailing_list.host_name, []).append(
                mailing_list.list_name)
        with open(path + '.new', 'w') as fp:
            print >> fp, """\
# AUTOMATICALLY GENERATED BY MAILMAN ON {0}
#
# This file is generated by Mailman, and is kept in sync with the binary hash
# file.  YOU SHOULD NOT MANUALLY EDIT THIS FILE unless you know what you're
# doing, and can keep the two files properly in sync.  If you screw it up,
# you're on your own.
""".format(datetime.datetime.now().replace(microsecond=0))
            for domain in sorted(by_domain):
                print >> fp, """\
# Aliases which are visible only in the @{0} domain.
""".format(domain)
                for list_name in by_domain[domain]:
                    # Calculate the field width of the longest alias.  10 ==
                    # len('-subscribe') + '@'.
                    longest = len(list_name + domain) + 10
                    print >> fp, """\
{0}@{1:{3}}lmtp:inet:{2.mta.lmtp_host}:{2.mta.lmtp_port}""".format(
                        list_name, domain, config,
                        # Add 1 because the bare list name has no dash.
                        longest + 1)
                    for destination in SUBDESTINATIONS:
                        print >> fp, """\
{0}-{1}@{2:{4}}lmtp:inet:{3.mta.lmtp_host}:{3.mta.lmtp_port}""".format(
                        list_name, destination, domain, config,
                        longest - len(destination))
                print >> fp
        # Move the temporary file into place, then generate the new .db file.
        os.rename(path + '.new', path)
        # Now that the new aliases file has been written, we must tell Postfix
        # to generate a new .db file.
        command = config.mta.postfix_map_cmd + ' ' + path
        status = (os.system(command) >> 8) & 0xff
        if status:
            msg = 'command failure: %s, %s, %s'
            errstr = os.strerror(status)
            log.error(msg, command, status, errstr)
            raise RuntimeError(msg % (command, status, errstr))
