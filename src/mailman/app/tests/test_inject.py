# Copyright (C) 2011-2012 by the Free Software Foundation, Inc.
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

"""Testing app.inject functions."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    ]


import unittest

from mailman.app.inject import inject_message, inject_text
from mailman.app.lifecycle import create_list
from mailman.email.message import Message
from mailman.testing.helpers import (
    get_queue_messages,
    specialized_message_from_string as message_from_string)
from mailman.testing.layers import ConfigLayer


NL = '\n'



class TestInjectMessage(unittest.TestCase):
    """Test message injection."""

    layer = ConfigLayer

    def setUp(self):
        # Python 2.7 has a better equality tester for message texts.
        self.eq = getattr(self, 'assertMultiLineEqual', self.assertEqual)
        self.mlist = create_list('test@example.com')
        self.msg = message_from_string("""\
From: anne@example.com
To: test@example.com
Subject: A test message
Message-ID: <first>
Date: Tue, 14 Jun 2011 21:12:00 -0400

Nothing.
""")
        # For Python 2.7.
        self.maxDiff = None

    def test_inject_message(self):
        # Test basic inject_message() call.
        inject_message(self.mlist, self.msg)
        items = get_queue_messages('in')
        self.assertEqual(len(items), 1)
        self.eq(items[0].msg.as_string(), self.msg.as_string())
        self.assertEqual(items[0].msgdata['listname'], 'test@example.com')
        self.assertEqual(items[0].msgdata['original_size'],
                         len(self.msg.as_string()))

    def test_inject_message_with_recipients(self):
        # Explicit recipients end up in the metadata.
        recipients = ['bart@example.com', 'cris@example.com']
        inject_message(self.mlist, self.msg, recipients)
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['recipients'], recipients)

    def test_inject_message_to_queue(self):
        # Explicitly use a different queue.
        inject_message(self.mlist, self.msg, switchboard='virgin')
        items = get_queue_messages('in')
        self.assertEqual(len(items), 0)
        items = get_queue_messages('virgin')
        self.assertEqual(len(items), 1)
        self.eq(items[0].msg.as_string(), self.msg.as_string())
        self.assertEqual(items[0].msgdata['listname'], 'test@example.com')
        self.assertEqual(items[0].msgdata['original_size'],
                         len(self.msg.as_string()))

    def test_inject_message_without_message_id(self):
        # inject_message() adds a Message-ID header if it's missing.
        del self.msg['message-id']
        self.assertFalse('message-id' in self.msg)
        inject_message(self.mlist, self.msg)
        self.assertTrue('message-id' in self.msg)
        items = get_queue_messages('in')
        self.assertTrue('message-id' in items[0].msg)
        self.assertEqual(items[0].msg['message-id'], self.msg['message-id'])

    def test_inject_message_without_date(self):
        # inject_message() adds a Date header if it's missing.
        del self.msg['date']
        self.assertFalse('date' in self.msg)
        inject_message(self.mlist, self.msg)
        self.assertTrue('date' in self.msg)
        items = get_queue_messages('in')
        self.assertTrue('date' in items[0].msg)
        self.assertEqual(items[0].msg['date'], self.msg['date'])

    def test_inject_message_trusts_original_size_attribute(self):
        # If the message object has an `original_size` attribute, this is
        # copied into the metadata. 
        self.msg.original_size = 3
        inject_message(self.mlist, self.msg)
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['original_size'], 3)

    def test_inject_message_with_keywords(self):
        # Keyword arguments are copied into the metadata.
        inject_message(self.mlist, self.msg, foo='yes', bar='no')
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['foo'], 'yes')
        self.assertEqual(items[0].msgdata['bar'], 'no')



class TestInjectText(unittest.TestCase):
    """Test text injection."""

    layer = ConfigLayer

    def setUp(self):
        # Python 2.7 has a better equality tester for message texts.
        self.eq = getattr(self, 'assertMultiLineEqual', self.assertEqual)
        self.mlist = create_list('test@example.com')
        self.text = b"""\
From: bart@example.com
To: test@example.com
Subject: A test message
Message-ID: <second>
Date: Tue, 14 Jun 2011 21:12:00 -0400

Nothing.
"""
        # For Python 2.7.
        self.maxDiff = None

    def _remove_line(self, header):
        return NL.join(line for line in self.text.splitlines()
                       if not line.lower().startswith(header))

    def test_inject_text(self):
        # Test basic inject_text() call.
        inject_text(self.mlist, self.text)
        items = get_queue_messages('in')
        self.assertEqual(len(items), 1)
        self.assertTrue(isinstance(items[0].msg, Message))
        self.eq(items[0].msg.as_string(), self.text)
        self.assertEqual(items[0].msgdata['listname'], 'test@example.com')
        self.assertEqual(items[0].msgdata['original_size'], len(self.text))

    def test_inject_text_with_recipients(self):
        # Explicit recipients end up in the metadata.
        recipients = ['bart@example.com', 'cris@example.com']
        inject_text(self.mlist, self.text, recipients)
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['recipients'], recipients)

    def test_inject_text_to_queue(self):
        # Explicitly use a different queue.
        inject_text(self.mlist, self.text, switchboard='virgin')
        items = get_queue_messages('in')
        self.assertEqual(len(items), 0)
        items = get_queue_messages('virgin')
        self.assertEqual(len(items), 1)
        self.eq(items[0].msg.as_string(), self.text)
        self.assertEqual(items[0].msgdata['listname'], 'test@example.com')
        self.assertEqual(items[0].msgdata['original_size'], len(self.text))

    def test_inject_text_without_message_id(self):
        # inject_text() adds a Message-ID header if it's missing.
        filtered = self._remove_line('message-id')
        self.assertFalse('Message-ID' in filtered)
        inject_text(self.mlist, filtered)
        items = get_queue_messages('in')
        self.assertTrue('message-id' in items[0].msg)

    def test_inject_text_without_date(self):
        # inject_text() adds a Date header if it's missing.
        filtered = self._remove_line('date')
        self.assertFalse('date' in filtered)
        inject_text(self.mlist, self.text)
        items = get_queue_messages('in')
        self.assertTrue('date' in items[0].msg)

    def test_inject_text_adds_original_size(self):
        # The metadata gets an original_size attribute that is the length of
        # the injected text.
        inject_text(self.mlist, self.text)
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['original_size'], len(self.text))

    def test_inject_text_with_keywords(self):
        # Keyword arguments are copied into the metadata.
        inject_text(self.mlist, self.text, foo='yes', bar='no')
        items = get_queue_messages('in')
        self.assertEqual(items[0].msgdata['foo'], 'yes')
        self.assertEqual(items[0].msgdata['bar'], 'no')
