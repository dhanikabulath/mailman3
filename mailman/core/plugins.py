# Copyright (C) 2007-2009 by the Free Software Foundation, Inc.
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

"""Get a requested plugin."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    ]


import pkg_resources



def get_plugin(group):
    """Get the named plugin.

    In general, this returns exactly one plugin.  If no plugins have been
    added to the named group, the 'stock' plugin will be used.  If more than
    one plugin -- other than the stock one -- exists, an exception will be
    raised.

    :param group: The plugin group name.
    :return: The loaded plugin.
    :raises RuntimeError: If more than one plugin overrides the stock plugin
        for the named group.
    """
    entry_points = list(pkg_resources.iter_entry_points(group))
    if len(entry_points) == 0:
        raise RuntimeError(
            'No entry points found for group: {0}'.format(group))
    elif len(entry_points) == 1:
        # Okay, this is the one to use.
        return entry_points[0].load()
    elif len(entry_points) == 2:
        # Find the one /not/ named 'stock'.
        entry_points = [ep for ep in entry_points if ep.name <> 'stock']
        if len(entry_points) == 0:
            raise RuntimeError(
                'No stock plugin found for group: {0}'.format(group))
        elif len(entry_points) == 2:
            raise RuntimeError('Too many stock plugins defined')
        else:
            raise AssertionError('Insanity')
        return entry_points[0].load()
    else:
        raise RuntimeError('Too many plugins for group: {0}'.format(group))



def get_plugins(group):
    """Get and return all plugins in the named group.

    :param group: Plugin group name.
    :return: The loaded plugin.
    """
    for entry_point in pkg_resources.iter_entry_points(group):
        yield entry_point.load()
