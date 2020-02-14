#!/usr/bin/env python3
import logging
import os
import sys
import argparse
import time
from cifsdk.client.http import HTTP as Client
from random import randint
from pathlib import Path
import validators
import json

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s[%(lineno)s][%(filename)s] - %(message)s'

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

FEED_LIMIT = 5


class MissingRequirement(Exception):
    pass


class CIFFeed(object):

    def __init__(self, remote, token, input_path, verify, provider, itype, filename):
        self.remote = remote
        self.token = token
        self.input_path = input_path
        self.verify = verify
        self.group = provider
        self.itype = itype
        self.filename = filename

    def _chunks(self, l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def _list_to_filters(self, l):
        for item in l:
            f = {"indicator": item,
                 "tags": "whitelist",
                 "itype": self.itype,
                 "confidence": 5,
                 "group": self.group,
                 "provider": self.group
                 }
            yield f

    def submit_safelist(self, l):
        cli = Client(token=self.token,
                     remote=self.remote,
                     verify_ssl=self.verify)

        filters = [f for f in self._list_to_filters(l)]
        try:
            i = 1
            for data in self._chunks(filters, 500):
                ret = cli.indicators_create(json.dumps(data))
                logger.debug('Submitted chunk {} with return status {}'.format(i, ret))
                i += 1
        except Exception as e:
            logger.warning('Exception during get_feed: {}'.format(e))
            logger.debug('CLI: {}, Filters: {}'.format(cli, data))
            backoff = randint(30, 120)
            logger.warning('Backing off {} seconds after failure'.format(backoff))
            time.sleep(backoff)
            sys.exit(1)
        logger.info('Complete submission of safelist with size {}'.format(str(len(l))))

    def process_safelist(self):
        items = []

        try:
            validate = getattr(CIFFeed, self.itype)
        except Exception as e:
            logger.warning('Unable to process safelists with an itype of: {}'.format(self.itype))
            return

        p = self.input_path + self.filename
        f = Path(p)
        if f.is_file():
            with open(p, 'r') as h:
                for line in h.readlines():
                    l = line.strip('\n')
                    if validate(self, l):
                        items.append(l)
                    else:
                        logger.warning('Rejected safelist candidate: {}'.format(l))
        logger.debug('Extracted the following safelist: {}'.format(items))

        return items

    def ipv4(self, candidate):
        logger.debug('Testing candidate for IPv4-ness: {}'.format(candidate))
        if validators.ip_address.ipv4(candidate):
            return True
        else:
            return False


def parse_safelists_from_environment():
    '''
    Get the environmental variables, and add any variables prefixed with "CHNSAFELIST" to a dictionary

    :returns: a dictionary with a key of the variable, and a value of it's value
    '''
    env = {}
    for item in os.environ.items():
        if item[0][0:11].upper() == "CHNSAFELIST":
            env[item[0].strip('"')] = item[1].strip('"')
    logger.debug('Retrived env from environment: {}'.format(env))

    config = get_feed_configs(env)
    return config


def get_feed_configs(env):
    configs = {}
    for i in range(0, FEED_LIMIT):
        prefix = 'CHNSAFELIST' + str(i) + '_'
        f = {}
        for key in env:
            if key[0:13] == prefix:
                f[key[13:]] = env[key]
        logger.debug('Collected set for f of: {}'.format(f))
        if f:
            feed = safelist_from_vars(f)
            if feed:
                logger.debug('Addin safelist: {}'.format(feed))
                configs[feed.filename] = feed
    return configs


def safelist_from_vars(fvars):
    logger.debug('Building safelist from vars: {}'.format(fvars))
    try:
        remote = fvars.pop('REMOTE')
        token = fvars.pop('TOKEN')
        filename = fvars.pop('FILENAME').strip('"')
        provider = fvars.pop('PROVIDER')
        itype = fvars.pop('ITYPE')

    except KeyError as e:
        logger.warning('Safelist config missing required values: {}'.format(e))
        return
    if provider.upper() == 'EVERYONE':
        logger.warning('Users may not submit safelist entries to the everyone group!')
        logger.warning('Ignoring safelist config')
        return

    if fvars.get('TLS_VERIFY'):
        verify = fvars.pop('TLS_VERIFY')
        if verify.lower() == 'true':
            verify = True
        else:
            verify = False
    else:
        verify = False

    input_path = './'

    try:
        feed = CIFFeed(remote=remote, token=token, input_path=input_path, verify=verify, provider=provider,
                       itype=itype, filename=filename)

        logger.debug('Parsed Feed: {}'.format(repr(feed)))
        return feed
    except MissingRequirement as e:
        logger.warning('Ignoring feed config: {}'.format(fvars))
        return


def process_safelists(config):
    for feed in config:
        logger.info('Processing safelist {}'.format(feed))
        logger.debug('Safelist: {}'.format(repr(config[feed])))

        cf = config[feed]
        sl = cf.process_safelist()
        cf.submit_safelist(sl)
        logger.info('Upload items for safelist {} with item count of {}'.format(feed, str(len(sl))))


def main():
    parser = argparse.ArgumentParser(
        description='Collect CIF feeds and write them out to a file, then refresh',
        epilog='http://xkcd.com/353/')
    parser.add_argument('-s', '--sleep', dest='sleep', type=int, default=24,
                        help='Number of hours between feed refreshes; minimum 1, default 24')
    parser.add_argument('-r', '--refresh', action="store_true", dest='refresh',
                        default=False,
                        help='Refresh safelist every X hours based on -s')
    parser.add_argument('-d', '--debug', action="store_true", dest='debug',
                        default=False,
                        help='Get debug messages about processing')
    opts = parser.parse_args()

    if opts.debug:
        logger.setLevel(logging.DEBUG)

    config = parse_safelists_from_environment()
    feed_count = len(config)
    if not feed_count > 0:
        logger.error('Found NO valid safelists specified. Please check the env file for valid specifications. Restart'
                     ' in 300 seconds')
        time.sleep(300)
        sys.exit(0)
    logger.debug('After parsing we have {} valid safelists'.format(feed_count))

    if opts.sleep < 1:
        logger.warning('Refresh delay set below minimum of 1 hour; setting to 1 hour')
        opts.sleep = 1

    seconds = opts.sleep * 60 * 60
    while True:
        process_safelists(config)
        if not opts.refresh:
            logger.info('Finished processing feeds, exiting.')
            sys.exit(0)
        logger.info('Finished processing feeds, sleeping for {} seconds'.format(seconds))
        time.sleep(seconds)


if __name__ == "__main__":
    sys.exit(main())
