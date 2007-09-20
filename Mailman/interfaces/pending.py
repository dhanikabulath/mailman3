# Copyright (C) 2007 by the Free Software Foundation, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301,
# USA.

"""Interfaces for the pending database.

The pending database contains events that must be confirmed by the user.  It
maps these events to a unique hash that can be used as a token for end user
confirmation.
"""

from zope.interface import Interface, Attribute



class IPendable(Interface):
    """A pendable object."""

    def keys():
        """The keys of the pending event data, all of which are strings."""

    def values():
        """The values of the pending event data, all of which are strings."""

    def items():
        """The key/value pairs of the pending event data.

        Both the keys and values must be strings.
        """
    


class IPending(Interface):
    """Interface to pending database."""

    def add(pendable, lifetime=None):
        """Create a new entry in the pending database, returning a token.

        :param pendable: The IPendable instance to add.
        :param lifetime: The amount of time, as a `datetime.timedelta` that
            the pended item should remain in the database.  When None is
            given, a system default maximum lifetime is used.
        :return: A token string for inclusion in urls and email confirmations.
        """

    def confirm(token, expunge=True):
        """Return the IPendable matching the token.

        :param token: The token string for the IPendable given by the `.add()`
            method.
        :param expunge: A flag indicating whether the pendable record should
            also be removed from the database or not.
        :return: The matching IPendable or None if no match was found.
        """

    def evict():
        """Remove all pended items whose lifetime has expired."""