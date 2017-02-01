"""Module to handle Pandokia targeted reporting."""
from __future__ import absolute_import, division, print_function

import os
from collections import Counter


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

                # Start of individual test log
                if 'scalar_project=' in row:
                    in_data_block = True
                    scalar_project = row.split('=')[1]

                # Individual test name
                elif 'scalar_test_name=' in row and in_data_block:
                    scalar_test_name = row.split('=')[1]

                # Warning to be captured. Each test can have multiple.
                elif (row.startswith('.[WARNING') and
                      ('DeprecationWarning' in row or
                       'FutureWarning' in row) and
                      in_data_block):
                    words = row.split()
                    module_loc = '/'.join(words[2].split('/')[-3:])[:-1]
                    warn_str = ' '.join(words[3:])
                    t_info = '{}: {}'.format(scalar_project, scalar_test_name)
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

            for warn_str in sorted(self.data):
                warn_dict = self.data[warn_str]
                fout.write('<p>{}</p>\n'.format(warn_str))

                for module_loc in sorted(warn_dict):
                    t_counter = warn_dict[module_loc]
                    fout.write('<p>&emsp;&emsp;{}</p>\n'.format(module_loc))

                    for t_info in sorted(t_counter):
                        val = t_counter[t_info]
                        fout.write('<p>&emsp;&emsp;&emsp;&emsp;{}'.format(
                            t_info))
                        if val > 1:
                            fout.write(' (repeated {} times)'.format(val))
                        fout.write('</p>\n')

            fout.write('</body>\n</html>\n')
