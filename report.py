"""Module to handle Pandokia targeted reporting."""
from __future__ import absolute_import, division, print_function

import os


def parse_log(filename):
    """Parse raw log from ``pdk export``."""
    if not os.path.isfile(filename):
        print('{} does not exist'.format(filename))
        return
        
    # Do something -- parse, stats
    
    # Return Astropy table
    
    
def make_report(tab):
    """Generate human readable report from given table."""
    
