"""Module to handle Pandokia targeted reporting."""
from __future__ import absolute_import, division, print_function

import glob
import json
import os
import re
import stat
import sys
import time
from collections import Counter
from datetime import datetime
from difflib import context_diff

__all__ = ['CreatureReport', 'CaptainBarnacle', 'calling_all_octonauts',
           'get_all_reports', 'diff_last_two', 'rm_old_reps']

_warn_regex = re.compile(r"^\.\[?warning", re.IGNORECASE)


class CreatureReport(object):
    """Class to handle custom Pandokia parsing.

    Examples
    --------
    >>> from report import CreatureReport
    >>> c = CreatureReport()
    >>> c.parse_log('my_pdk_log.txt')
    >>> c.to_html('my_report.html')

    """
    def __init__(self):
        self.data = {}
        self.stats = {}
        self.empty_log = True

        # Exact warnings to catch. Set to empty list to catch it all.
        self.creatures = ['DeprecationWarning', 'FutureWarning']

    @property
    def has_data(self):
        """Indicate whether any interesting data is captured."""
        return len(self.data) > 0

    def parse_log(self, filename):
        """Parse raw log from ``pdk export``."""
        if not os.path.isfile(filename):
            print('{} does not exist'.format(filename))
            return

        in_data_block = False

        # Do something -- parse, stats
        with open(filename) as fin:
            for line in fin:
                row = line.strip()
                if self.empty_log:
                    self.empty_log = False

                # Start of individual test log
                if 'scalar_project=' in row:
                    in_data_block = True
                    scalar_project = row.split('=')[1]

                    if scalar_project not in self.stats:
                        self.stats[scalar_project] = Counter()

                # Individual test name
                elif 'scalar_test_name=' in row and in_data_block:
                    scalar_test_name = row.split('=')[1]

                # Individual test result
                # P = pass
                # F = fail
                # E = error
                # D = disable
                # M = missing?
                elif 'scalar_status=' in row and in_data_block:
                    scalar_status = row.split('=')[1]
                    self.stats[scalar_project][scalar_status] += 1

                # Warning to be captured. Each test can have multiple.
                # Note: Probably more elegant to use regex but that is also
                #       hard to understand...
                elif _warn_regex.match(row) and in_data_block:
                    has_creature = False

                    if len(self.creatures) == 0:
                        has_creature = True
                    else:
                        for creature in self.creatures:
                            if creature in row:
                                has_creature = True
                                break

                    if has_creature:
                        words = row.split()
                        module_loc = '/'.join(words[2].split('/')[-3:])[:-1]
                        warn_str = ' '.join(words[3:])
                        t_info = '{}: {}'.format(
                            scalar_project, scalar_test_name)
                        # Store in class data
                        if warn_str not in self.data:
                            self.data[warn_str] = {}
                        if module_loc not in self.data[warn_str]:
                            self.data[warn_str][module_loc] = Counter()
                        self.data[warn_str][module_loc][t_info] += 1

                # End of individual test log
                elif row == 'END' and in_data_block:
                    in_data_block = False
                    scalar_project = ''
                    scalar_test_name = ''

                # Just skip the line
                else:
                    continue

    def to_html(self, filename, title='Creature Report', overwrite=False):
        """Format compiled data into HTML."""
        if not overwrite and os.path.exists(filename):
            print('{} exists, use overwrite=True to write '
                  'anyway'.format(filename))
            return

        with open(filename, 'w') as fout:
            fout.write('<html>\n')
            fout.write('<title>{}</title>\n'.format(title))
            fout.write('<body>\n')

            if self.has_data:
                for warn_str in sorted(self.data):
                    warn_dict = self.data[warn_str]
                    fout.write('<p>{}</p>\n'.format(warn_str))

                    for module_loc in sorted(warn_dict):
                        t_counter = warn_dict[module_loc]
                        fout.write(
                            '<p>&emsp;&emsp;{}</p>\n'.format(module_loc))

                        for t_info in sorted(t_counter):
                            val = t_counter[t_info]
                            fout.write('<p>&emsp;&emsp;&emsp;&emsp;{}'.format(
                                t_info))
                            if val > 1:
                                fout.write(' (repeated {} times)'.format(val))
                            fout.write('</p>\n')

            elif self.empty_log:
                fout.write('<p>PDK log is empty!</p>\n')

            else:
                fout.write('<p>PDK log has no info of interest! '
                           'Yes, this is a good thing.</p>\n')

            fout.write('</body>\n</html>\n')

    def report_stats(self, filename, overwrite=False):
        """JSON file of test result stats."""
        if not overwrite and os.path.exists(filename):
            print('{} exists, use overwrite=True to write '
                  'anyway'.format(filename))
            return

        with open(filename, 'w') as fout:
            json.dump(self.stats, fout, sort_keys=True, indent=4)


class CaptainBarnacle(object):
    """Class to automate :class:`CreatureReport`."""
    def __init__(self, date_str=datetime.today().strftime('%Y%m%d'),
                 in_pfx='pdklog', out_pfx='rep'):
        self.path = os.environ['REMOTE_DIR']
        self.outpath = os.environ['HTML_DIR']
        self.pdklog = os.path.join(
            self.path, '{}{}.txt'.format(in_pfx, date_str))
        self.stat = os.path.join(
            self.path, 'stats_{}{}.json'.format(out_pfx, date_str))
        self.html = os.path.join(
            self.outpath, '{}{}.html'.format(out_pfx, date_str))

    def daily_report(self):
        """Generate daily report."""
        c = CreatureReport()
        c.parse_log(self.pdklog)
        c.to_html(self.html, overwrite=True)
        c.report_stats(self.stat, overwrite=True)

        # Add group write permission.
        os.chmod(self.html, os.stat(self.html).st_mode | stat.S_IWGRP)

    def symlink_results(self, linkfile='daily_report.html'):
        """Create symbolic link in ``REMOTE_DIR`` to the latest report."""
        dstfile = os.path.join(self.outpath, linkfile)
        if os.path.lexists(dstfile):
            os.unlink(dstfile)
        os.symlink(self.html, dstfile)
        print('{} is now pointed to {}'.format(dstfile, self.html))


def calling_all_octonauts(filename='index.html', title='Creature Report',
                          overwrite=False):
    """Generate main index."""
    if not overwrite and os.path.exists(filename):
        print('{} exists, use overwrite=True to write '
              'anyway'.format(filename))
        return

    root = os.environ['HTML_DIR']

    # nott dev + jwst
    all_but_last_dev = get_all_reports(root, pattern='rep*.html')[1:]
    daily_dev = 'daily_report.html'

    # nott public
    all_but_last_pub = get_all_reports(root, pattern='pub*.html')[1:]
    daily_pub = 'daily_report_pub.html'

    # pembry dev
    all_but_last_pemdev = get_all_reports(root, pattern='pemrep*.html')[1:]
    daily_pemdev = 'daily_report_pemdev.html'

    # pembry public
    all_but_last_pempub = get_all_reports(root, pattern='pempub*.html')[1:]
    daily_pempub = 'daily_report_pempub.html'

    with open(filename, 'w') as fout:
        fout.write('<html>\n')
        fout.write('<title>{}</title>\n'.format(title))
        fout.write('<body>\n')
        fout.write('<p>Lists of known deprecation warnings detected in '
                   'regression tests, refreshed daily from test results, '
                   'managed by STScI Data Analysis Tools Branch are '
                   'available below:<br/>\n<ul>\n')
        for s1, s2 in [(daily_dev, 'nott dev'),
                       (daily_pub, 'nott public'),
                       (daily_pemdev, 'pembry dev'),
                       (daily_pempub, 'pembry public')]:
            fout.write(
                '<li/><a href="{0}">{0}</a> ({1} build)\n'.format(s1, s2))
        fout.write('</ul>\n</p>\n')
        for s1, s2 in [('nott dev', all_but_last_dev),
                       ('nott public', all_but_last_pub),
                       ('pembry dev', all_but_last_pemdev),
                       ('pembry public', all_but_last_pempub)]:
            fout.write('<p>Older reports from {0} build for the past 7 days:'
                       '<br/>\n<ul>\n'.format(s1))
            for s in s2:
                fout.write('<li/><a href="{0}">{0}</a>\n'.format(
                    os.path.basename(s)))
            fout.write('</ul>\n</p>\n')
        fout.write('</body>\n</html>\n')

    # Add group write permission.
    os.chmod(filename, os.stat(filename).st_mode | stat.S_IWGRP)


def get_all_reports(root, pattern='rep*.html'):
    """Return all HTML reports, sorted in descending alphabetical order."""
    return sorted(glob.iglob(os.path.join(root, pattern)), reverse=True)


def diff_last_two(root, pattern='rep*.html'):
    """Diff the latest two files matching given pattern in root.

    This is useful to decide whether some known warnings are fixed
    or new warnings popped up.

    """
    no_diff = True
    two_files = get_all_reports(root, pattern=pattern)[:2]

    if len(two_files) != 2:
        print('No diff')
        return

    f_next, f_prev = two_files

    with open(f_prev) as fin:
        s1 = fin.readlines()
    with open(f_next) as fin:
        s2 = fin.readlines()

    for line in context_diff(s1, s2, fromfile=f_prev, tofile=f_next):
        sys.stdout.write(line)
        if no_diff:
            no_diff = False

    if no_diff:
        print('No diff')


def rm_old_reps(root, pattern='rep*.html', max_life=7.0, verbose=True):
    """Delete all files matching ``pattern`` in ``root``
    older than ``max_life`` days.

    Parameters
    ----------
    root : string
        Root directory containing files to delete.

    pattern : string
        File ``glob`` pattern.

    max_life : float
        Maximum allowed life span in days. Naively
        assumes there are 86400 seconds in a day.

    verbose : bool
        Extra log info.

    """
    max_sec = 86400.0 * max_life
    t_now = time.time()  # sec

    for f in glob.iglob(os.path.join(root, pattern)):
        if not os.path.isfile(f):
            continue

        if (t_now - os.stat(f).st_mtime) < max_sec:
            if verbose:
                print('{} is newer than {} day(s) '
                      '-- skipped'.format(f, max_life))
            continue

        try:
            os.remove(f)
        except Exception as e:
            if verbose:
                print('{} cannot be deleted -- {}'.format(f, str(e)))
        else:
            if verbose:
                print('{} successfully deleted'.format(f))


if __name__ == '__main__':
    """Batch script for cron job."""
    html_dir = os.environ['HTML_DIR']

    # nott dev + jwst
    r = CaptainBarnacle(in_pfx='pdklog_nott_dev_')
    r.daily_report()
    r.symlink_results()
    diff_last_two(html_dir)
    print()

    # nott public
    r = CaptainBarnacle(in_pfx='pdklog_nott_public_', out_pfx='pub')
    r.daily_report()
    r.symlink_results(linkfile='daily_report_pub.html')
    diff_last_two(html_dir, pattern='pub*.html')
    print()

    # pembry dev
    r = CaptainBarnacle(in_pfx='pdklog_banana_dev_', out_pfx='pemrep')
    r.daily_report()
    r.symlink_results(linkfile='daily_report_pemdev.html')
    diff_last_two(html_dir, pattern='pemrep*.html')
    print()

    # pembry public
    r = CaptainBarnacle(in_pfx='pdklog_banana_public_', out_pfx='pempub')
    r.daily_report()
    r.symlink_results(linkfile='daily_report_pempub.html')
    diff_last_two(html_dir, pattern='pempub*.html')
    print()

    # index
    print('Generating index...')
    calling_all_octonauts(filename=os.path.join(html_dir, 'index.html'),
                          overwrite=True)

    print()
    print('Cleaning old files...')

    # nott dev + jwst
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='pdklog*.txt')
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='stats_rep*.json')
    rm_old_reps(html_dir)

    # nott public
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='pdkpub*.txt')
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='stats_pub*.json')
    rm_old_reps(html_dir, pattern='pub*.html')

    # pembry dev
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='pdkpemlog*.txt')
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='stats_pemrep*.json')
    rm_old_reps(html_dir, pattern='pemrep*.html')

    # pembry public
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='pdkpempub*.txt')
    rm_old_reps(os.environ['REMOTE_DIR'], pattern='stats_pempub*.json')
    rm_old_reps(html_dir, pattern='pempub*.html')
