#!/usr/bin/env python3
import logging
import os
import sys
import argparse
import time
import requests

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s[%(lineno)s][%(filename)s] - %(message)s'

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def process_feeds_from_environment():
    '''
    Get the environmental variables, and add any variables prefixed with "CHNFEED" to a dictionary

    :returns: a dictionary with a key of the variable, and a value of it's value
    '''
    env = {}
    for item in os.environ.items():
        if item[0][0:10].upper() == "CHNAPIFEED":
            key = item[0][11:].strip('"')
            value = item[1].strip('"')
            env[key] = value
    logger.debug('Retrived env from environment: {}'.format(env))

    try:
        remote = env.pop('REMOTE')
        token = env.pop('TOKEN')
        filename = env.pop('FILENAME')
    except KeyError as e:
        logger.warning('Feed config missing required values: {}'.format(e))
        return

    if env.get('TLS_VERIFY'):
        verify = env.pop('TLS_VERIFY')
        if verify.lower() == 'true':
            verify = True
        else:
            verify = False
    else:
        verify = False

    if env.get('OUTPUT_PATH'):
        output_path = env.pop('OUTPUT_PATH')
    else:
        output_path = './feeds'

    if env.get('HOURS'):
        hours = env.pop('HOURS')
    else:
        hours = '24'

    if env.get('LIMIT'):
        limit = env.pop('LIMIT')
    else:
        limit = '1000'

    headers = {
        'apikey': token
    }

    payload = {
        'hours_ago': hours,
        'limit': limit
    }

    url = remote + '/api/intel_feed/'

    r = requests.get(url=url, headers=headers, params=payload, verify=verify)
    if r:
        logger.debug('Got from server: {}'.format(r))
        data = r.json()
        feed = set()
        for entry in data['data']:
            feed.add(entry['source_ip'])
        logger.info('Received {} unique entries from server.'.format(len(feed)))

    else:
        logger.error('No data returned from server!')
        time.sleep(300)
        exit(1)

    filepath = output_path + '/' + filename
    with open(filepath, 'w') as f:
        for item in feed:
            f.write('{}\n'.format(item))


def main():
    parser = argparse.ArgumentParser(
        description='Collect CHN feeds and write them out to a file, then refresh',
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

    if opts.sleep < 5:
        logger.warning('Refresh delay set below minimum of 5 minutes; setting to 5 minutes')
        opts.sleep = 5

    seconds = opts.sleep * 60
    while True:
        process_feeds_from_environment()
        if not opts.refresh:
            logger.info('Finished processing feeds, exiting.')
            sys.exit(0)
        logger.info('Finished processing feeds, sleeping for {} seconds'.format(seconds))
        time.sleep(seconds)


if __name__ == "__main__":
    sys.exit(main())
