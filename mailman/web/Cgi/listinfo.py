# Copyright (C) 1998-2008 by the Free Software Foundation, Inc.
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

"""Produce listinfo page, primary web entry-point to mailing lists."""

# No lock needed in this script, because we don't change data.

import os
import cgi
import logging

from Mailman import Errors
from Mailman import MailList
from Mailman import Utils
from Mailman import i18n
from Mailman.configuration import config
from Mailman.htmlformat import *

# Set up i18n
_ = i18n._
i18n.set_language(config.DEFAULT_SERVER_LANGUAGE)

log = logging.getLogger('mailman.error')



def main():
    parts = Utils.GetPathPieces()
    if not parts:
        listinfo_overview()
        return

    listname = parts[0].lower()
    try:
        mlist = MailList.MailList(listname, lock=0)
    except Errors.MMListError, e:
        # Avoid cross-site scripting attacks
        safelistname = Utils.websafe(listname)
        listinfo_overview(_('No such list <em>%(safelistname)s</em>'))
        log.error('No such list "%s": %s', listname, e)
        return

    # See if the user want to see this page in other language
    cgidata = cgi.FieldStorage()
    language = cgidata.getvalue('language')
    if language not in config.languages.enabled_codes:
        language = mlist.preferred_language
    i18n.set_language(language)
    list_listinfo(mlist, language)



def listinfo_overview(msg=''):
    # Present the general listinfo overview
    hostname = Utils.get_request_domain()
    # Set up the document and assign it the correct language.  The only one we
    # know about at the moment is the server's default.
    doc = Document()
    doc.set_language(config.DEFAULT_SERVER_LANGUAGE)

    legend = _("%(hostname)s Mailing Lists")
    doc.SetTitle(legend)

    table = Table(border=0, width="100%")
    table.AddRow([Center(Header(2, legend))])
    table.AddCellInfo(table.GetCurrentRowIndex(), 0, colspan=2,
                      bgcolor=config.WEB_HEADER_COLOR)

    # Skip any mailing lists that isn't advertised.
    advertised = []
    for name in sorted(config.list_manager.names):
        mlist = MailList.MailList(name, lock=False)
        if mlist.advertised:
            if hostname not in mlist.web_page_url:
                # This list is situated in a different virtual domain
                continue
            else:
                advertised.append((mlist.GetScriptURL('listinfo'),
                                   mlist.real_name,
                                   mlist.description))
    if msg:
        greeting = FontAttr(msg, color="ff5060", size="+1")
    else:
        greeting = FontAttr(_('Welcome!'), size='+2')

    welcome = [greeting]
    mailmanlink = Link(config.MAILMAN_URL, _('Mailman')).Format()
    if not advertised:
        welcome.extend(
            _('''<p>There currently are no publicly-advertised
            %(mailmanlink)s mailing lists on %(hostname)s.'''))
    else:
        welcome.append(
            _('''<p>Below is a listing of all the public mailing lists on
            %(hostname)s.  Click on a list name to get more information about
            the list, or to subscribe, unsubscribe, and change the preferences
            on your subscription.'''))

    # set up some local variables
    adj = msg and _('right') or ''
    siteowner = Utils.get_site_noreply()
    welcome.extend(
        (_(''' To visit the general information page for an unadvertised list,
        open a URL similar to this one, but with a '/' and the %(adj)s
        list name appended.
        <p>List administrators, you can visit '''),
         Link(Utils.ScriptURL('admin'),
              _('the list admin overview page')),
         _(''' to find the management interface for your list.
         <p>If you are having trouble using the lists, please contact '''),
         Link('mailto:' + siteowner, siteowner),
         '.<p>'))

    table.AddRow([apply(Container, welcome)])
    table.AddCellInfo(max(table.GetCurrentRowIndex(), 0), 0, colspan=2)

    if advertised:
        table.AddRow(['&nbsp;', '&nbsp;'])
        table.AddRow([Bold(FontAttr(_('List'), size='+2')),
                      Bold(FontAttr(_('Description'), size='+2'))
                      ])
        highlight = 1
        for url, real_name, description in advertised:
            table.AddRow(
                [Link(url, Bold(real_name)),
                      description or Italic(_('[no description available]'))])
            if highlight and config.WEB_HIGHLIGHT_COLOR:
                table.AddRowInfo(table.GetCurrentRowIndex(),
                                 bgcolor=config.WEB_HIGHLIGHT_COLOR)
            highlight = not highlight

    doc.AddItem(table)
    doc.AddItem('<hr>')
    doc.AddItem(MailmanLogo())
    print doc.Format()



def list_listinfo(mlist, lang):
    # Generate list specific listinfo
    doc = HeadlessDocument()
    doc.set_language(lang)

    replacements = mlist.GetStandardReplacements(lang)

    if not mlist.digestable or not mlist.nondigestable:
        replacements['<mm-digest-radio-button>'] = ""
        replacements['<mm-undigest-radio-button>'] = ""
        replacements['<mm-digest-question-start>'] = '<!-- '
        replacements['<mm-digest-question-end>'] = ' -->'
    else:
        replacements['<mm-digest-radio-button>'] = mlist.FormatDigestButton()
        replacements['<mm-undigest-radio-button>'] = \
                                                   mlist.FormatUndigestButton()
        replacements['<mm-digest-question-start>'] = ''
        replacements['<mm-digest-question-end>'] = ''
    replacements['<mm-plain-digests-button>'] = \
                                              mlist.FormatPlainDigestsButton()
    replacements['<mm-mime-digests-button>'] = mlist.FormatMimeDigestsButton()
    replacements['<mm-subscribe-box>'] = mlist.FormatBox('email', size=30)
    replacements['<mm-subscribe-button>'] = mlist.FormatButton(
        'email-button', text=_('Subscribe'))
    replacements['<mm-new-password-box>'] = mlist.FormatSecureBox('pw')
    replacements['<mm-confirm-password>'] = mlist.FormatSecureBox('pw-conf')
    replacements['<mm-subscribe-form-start>'] = mlist.FormatFormStart(
        'subscribe')
    # Roster form substitutions
    replacements['<mm-roster-form-start>'] = mlist.FormatFormStart('roster')
    replacements['<mm-roster-option>'] = mlist.FormatRosterOptionForUser(lang)
    # Options form substitutions
    replacements['<mm-options-form-start>'] = mlist.FormatFormStart('options')
    replacements['<mm-editing-options>'] = mlist.FormatEditingOption(lang)
    replacements['<mm-info-button>'] = SubmitButton('UserOptions',
                                                    _('Edit Options')).Format()
    # If only one language is enabled for this mailing list, omit the choice
    # buttons.
    if len(mlist.language_codes) == 1:
        displang = ''
    else:
        displang = mlist.FormatButton('displang-button',
                                      text = _("View this page in"))
    replacements['<mm-displang-box>'] = displang
    replacements['<mm-lang-form-start>'] = mlist.FormatFormStart('listinfo')
    replacements['<mm-fullname-box>'] = mlist.FormatBox('fullname', size=30)

    # Do the expansion.
    doc.AddItem(mlist.ParseTags('listinfo.html', replacements, lang))
    print doc.Format()



if __name__ == "__main__":
    main()