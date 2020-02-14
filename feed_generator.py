#!/usr/bin/env python3
import logging
import os
import sys
import argparse
import time
from cifsdk.client.http import HTTP as Client
from random import randint

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s[%(lineno)s][%(filename)s] - %(message)s'
VALID_FILTERS = ['indicator', 'itype', 'confidence', 'provider', 'limit', 'application', 'nolog', 'tags', 'days',
                 'hours', 'groups', 'reporttime', 'cc', 'asn', 'asn_desc', 'rdata', 'firsttime', 'lasttime', 'region',
                 'id']
FEED_LIMIT = 10

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


class MissingRequirement(Exception):
    pass

class CIFFeed(object):
    def __init__(self, remote, token, output_path='./', verify=False):
        self.remote = remote
        self.token = token
        self.output_path = output_path
        self.verify = verify
        self.filename = None
        self.filters = {}

    def __repr__(self):
        return str(self.__dict__)

    def add_filters(self, items):
        filter = {}
        for item, value in items:
            if item.lower() in VALID_FILTERS:
                filter[item.lower()] = value
        if not filter.get('tags'):
            logger.error('Feed does NOT specify a required filter for TAGS!')
            raise MissingRequirement

        self.filters = filter

    def get_feed(self):
        cli = Client(token=self.token,
                     remote=self.remote,
                     verify_ssl=self.verify)
        logger.debug('Getting feed with filters: {}'.format(self.filters))
        try:
            logger.debug('Getting feed with filter set: {}'.format(self.filters))
            f = cli.feed(filters=self.filters)
            return f
        except Exception as e:
            logger.warning('Exception during get_feed: {}'.format(e))
            logger.debug('CLI: {}, Filters: {}'.format(cli, self.filters))
            backoff = randint(30, 120)
            logger.warning('Backing off {} seconds after failure'.format(backoff))
            time.sleep(backoff)
            sys.exit(1)


def parse_feeds_from_environment():
    '''
    Get the environmental variables, and add any variables prefixed with "CHNFEED" to a dictionary

    :returns: a dictionary with a key of the variable, and a value of it's value
    '''
    env = {}
    for item in os.environ.items():
        if item[0][0:7].upper() == "CHNFEED":
            env[item[0].strip('"')] = item[1].strip('"')
    logger.debug('Retrived env from environment: {}'.format(env))

    config = get_feed_configs(env)
    return config


def feed_from_vars(fvars):
    logger.debug('Building feed from vars: {}'.format(fvars))
    try:
        remote = fvars.pop('REMOTE')
        token = fvars.pop('TOKEN')
        filename = fvars.pop('FILENAME')
    except KeyError as e:
        logger.warning('Feed config missing required values: {}'.format(e))
        return

    if fvars.get('TLS_VERIFY'):
        verify = fvars.pop('TLS_VERIFY')
        if verify.lower() == 'true':
            verify = True
        else:
            verify = False
    else:
        verify = False

    if fvars.get('OUTPUT_PATH'):
        output_path = fvars.pop('OUTPUT_PATH')
    else:
        output_path = './feeds'

    try:
        feed = CIFFeed(remote=remote, token=token, output_path=output_path, verify=verify)
        feed.filename = filename.strip('"')
        logger.debug('Processing filters with remaining fvars: {}'.format(fvars))
        feed.add_filters(fvars.items())

        logger.debug('Parsed Feed: {}'.format(repr(feed)))
        return feed
    except MissingRequirement as e:
        logger.warning('Ignoring feed config: {}'.format(fvars))
        return

def get_feed_configs(env):
    configs = {}
    for i in range(0, FEED_LIMIT):
        prefix = 'CHNFEED' + str(i) + '_'
        f = {}
        for key in env:
            if key[0:9] == prefix:
                f[key[9:]] = env[key]
        logger.debug('Collected set for f of: {}'.format(f))
        if f:
            feed = feed_from_vars(f)
            if feed:
                logger.debug('Adding feed: {}'.format(feed))
                configs[feed.filename] = feed
    return configs


def write_feed(filepath, data):
    with open(filepath, 'w') as f:
        for item in data:
            f.write('{}\n'.format(item['indicator']))

def process_feeds(config):
    for feed in config:
        logger.info('Processing feed {}'.format(feed))
        logger.debug('Feed: {}'.format(repr(config[feed])))

        cf = config[feed]
        data = cf.get_feed()
        logger.info('Retrieved {} items for feed {}'.format(len(data), feed))
        output_file = cf.output_path + '/' + feed
        write_feed(output_file, data)

def main():
    parser = argparse.ArgumentParser(
        description='Collect CIF feeds and write them out to a file, then refresh',
        epilog='http://xkcd.com/353/')
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

    config = parse_feeds_from_environment()
    feed_count = len(config)
    if not feed_count > 0:
        logger.error('Found NO valid feeds specified. Please check the env file for valid specifications. Exiting in '
                     '300 seconds')
        time.sleep(300)
        sys.exit(1)
    logger.debug('After parsing we have {} valid feeds'.format(feed_count))

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
