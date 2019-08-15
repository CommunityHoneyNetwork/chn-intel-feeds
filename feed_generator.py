#!/usr/bin/env python3
import logging
import os
import sys
import argparse
import time
import configparser
from cifsdk.client.http import HTTP as Client

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
VALID_FILTERS = ['indicator', 'itype', 'confidence', 'provider', 'limit', 'application', 'nolog', 'tags', 'days',
                 'hours', 'groups', 'reporttime', 'cc', 'asn', 'asn_desc', 'rdata', 'firsttime', 'lasttime', 'region',
                 'id']
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


class CIFFeed(object):
    def __init__(self, remote, token, ouput_path='./', verify=False):
        self.remote = remote
        self.token = token
        self.output_path = ouput_path
        self.verify = verify
        self.filters = {}

    def __repr__(self):
        return str(self.__dict__)

    def add_filters(self, items):
        filter = {}
        for item, value in items:
            if item in VALID_FILTERS:
                filter[item] = value
        self.filters = filter

    def get_feed(self):
        cli = Client(token=self.token,
                     remote=self.remote,
                     verify_ssl=self.verify)
        logger.debug('Getting feed with filters: {}'.format(self.filters))
        try:
            f = cli.feed(filters=self.filters)
            return f
        except Exception as e:
            logger.warning('Exception during get_feed: {}'.format(e))
            sys.exit(1)


def parse_section(s):
    cif_token = s.get('cif_token')
    cif_host = s.get('cif_host')
    cif_verify_ssl = s.getboolean('cif_verify_ssl', fallback=False)
    op = s.get('output_path', fallback='./feeds')
    output_path = os.path.expanduser(op)

    feed = CIFFeed(cif_host, cif_token, output_path, cif_verify_ssl)
    feed.add_filters(s.items())

    return feed


def parse_config(config_file):
    cf = os.path.expanduser(config_file)
    if not os.path.isfile(cf):
        sys.exit("Could not find configuration file: {0}".format(cf))

    parser = configparser.ConfigParser()
    parser.read(cf)

    config = {}

    for section in parser.sections():
        logger.info('Parsing section {}'.format(section))
        feed = parse_section(parser[section])
        config[section] = feed
    logger.debug('Parsed config: {0}'.format(repr(config)))
    return config


def write_feed(filepath, data):
    with open(filepath, 'w') as f:
        for item in data:
            f.write('{}\n'.format(item['indicator']))

def process_feeds(config):
    for feed in config:
        logger.info('Processing feed {}'.format(feed))
        logger.debug('Feed: {}'.format(config[feed].__dict__))

        cf = config[feed]
        data = cf.get_feed()
        logger.info('Retrieved {} items for feed {}'.format(len(data), feed))
        output_file = cf.output_path + '/' + feed
        write_feed(output_file, data)

def main():
    parser = argparse.ArgumentParser(
        description='Collect CIF feeds and write them out to a file, then refresh',
        epilog='http://xkcd.com/353/')
    parser.add_argument('-C', '--config', dest='configfile', default='~/feed_generator.cfg',
                        help='Feedparser Configuration file')
    parser.add_argument('-s', '--sleep', dest='sleep', type=int, default=60,
                        help='Number of minutes between feed refreshes; minimum 5, default 60')
    parser.add_argument('-r', '--refresh', action="store_true", dest='refresh',
                        default=False,
                        help='Refresh feeds every X minutes based on -s')
    parser.add_argument('-d', '--debug', action="store_true", dest='debug',
                        default=False,
                        help='Get debug messages about processing')
    opts = parser.parse_args()

    if opts.debug:
        logger.setLevel(logging.DEBUG)

    config = parse_config(opts.configfile)

    if opts.sleep < 5:
        logger.warning('Refresh delay set below minimum of 5 minutes; setting to 5 minutes')
        opts.sleep = 5

    seconds = opts.sleep * 60
    while True:
        process_feeds(config)
        if not opts.refresh:
            logger.info('Finished processing feeds, exiting.')
            sys.exit(0)
        logger.info('Finished processing feeds, sleeping for {} seconds'.format(seconds))
        time.sleep(seconds)


if __name__ == "__main__":
    sys.exit(main())
