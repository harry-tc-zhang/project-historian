import requests
import json
import os
import datetime
from time import sleep
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def cache_rss(cache_dir, rss_info_path):
    print('Caching RSS feeds...')

    url = 'https://cloud.feedly.com/v3/streams/contents'

    feed_info = json.load(open(rss_info_path, 'r'))

    save_dir = cache_dir
    if not os.path.isdir(save_dir):
        os.mkdir(save_dir)

    today_str = datetime.datetime.now().strftime('%Y-%m-%d')

    for key in feed_info.keys():
        cache_dir = os.path.join(save_dir, key)
        cache_cnt = 300
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir)
            cache_cnt = 1000
        req_params = {
            'streamId': 'feed/' + feed_info[key],
            'count': cache_cnt
        }
        results = requests.get(url, req_params).json()
        with open(os.path.join(cache_dir, today_str + '.js'), 'w') as outfile:
            json.dump(results, outfile, indent=4)
        print('- Done caching RSS for {}.'.format(key))
        sleep(1)

    return


def update_db(cache_dir, db_path, latest_only=True):
    print('Updating the RSS database...')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cache_dirs = os.listdir(cache_dir)
    feed_name_list = [dirname for dirname in cache_dirs if dirname[0].isalpha()]

    creation_command = (
        'CREATE TABLE IF NOT EXISTS rss_data('
        'id TEXT, '
        'title TEXT, '
        'feedname TEXT, '
        'content TEXT, '
        'summary TEXT, '
        'author TEXT, '
        'published INTEGER, '
        'origin TEXT, '
        'keywords TEXT, '
        'visual TEXT, '
        'engagement INTEGER, '
        'canonical TEXT, '
        'alternate TEXT, '
        'enclosure TEXT, '
        'cachedate TEXT, '
        'preprocessed TEXT, '
        'PRIMARY KEY(id)'
        ')'
    )
    cursor.execute(creation_command)
    conn.commit()

    info_creation_command = (
        'CREATE TABLE IF NOT EXISTS rss_info('
        'id TEXT, '
        'updated INT, '
        'title TEXT, '
        'feedname TEXT, '
        'url TEXT, '
        'lastcached TEXT, '
        'PRIMARY KEY(id))'
    )
    cursor.execute(info_creation_command)
    conn.commit()

    for feed_name in feed_name_list:
        print('- Updating DB for {}...'.format(feed_name))
        feed_cache_dir = os.path.join(cache_dir, feed_name)
        cache_list_raw = os.listdir(feed_cache_dir)
        cache_list = [fname for fname in cache_list_raw if '.js' in fname]
        cache_list.sort()
        update_list = [cache_list[-1]]
        if not latest_only:
            update_list = cache_list
        for cache_fname in update_list:
            data = None
            with open(os.path.join(feed_cache_dir, cache_fname), 'r',
                encoding='utf-8', newline='') as datafile:
                data = json.load(datafile)
            for item in data['items']:
                update_dict = {
                    'id': item['id'],
                    'keywords': ', '.join(item['keywords']) if 'keywords' in item.keys() else '',
                    'title': BeautifulSoup(item['title'], 'html5lib').getText() if 'title' in item.keys() else '',
                    'feedname': feed_name,
                    'author': item['author'] if 'author' in item.keys() else '',
                    'published': int(item['published']),
                    'origin': json.dumps(item['origin']) if 'origin' in item.keys() else '',
                    'visual': json.dumps(item['visual']) if 'visual' in item.keys() else '',
                    'engagement': int(item['engagement']) if 'engagement' in item.keys() else '',
                    'alternate': json.dumps(item['alternate']) if 'alternate' in item.keys() else '',
                    'enclosure': json.dumps(item['enclosure']) if 'enclosure' in item.keys() else '',
                    'cachedate': cache_fname.replace('.js', '')
                }
                # Extract content if available
                if 'content' in item.keys():
                    if 'content' in item['content'].keys():
                        content_soup = BeautifulSoup(item['content']['content'], 'html.parser')
                        update_dict['content'] = content_soup.getText()
                # Extract summary if available
                if 'summary' in item.keys():
                    if 'content' in item['summary'].keys():
                        summary_soup = BeautifulSoup(item['summary']['content'], 'html.parser')
                        update_dict['summary'] = summary_soup.getText()
                # Find canonical URL through 'canonical', 'canonicalUrl', 'originId' or 'alternate'
                if 'canonicalUrl' in item.keys():
                    update_dict['canonical'] = item['canonicalUrl']
                if 'canonical' not in update_dict.keys():
                    if 'canonical' in item.keys():
                        if 'href' in item['canonical']:
                            update_dict['canonical'] = item['canonical']['href']
                if 'canonical' not in update_dict.keys():
                    if 'originId' in item.keys():
                        id_parsed = urlparse(item['originId'])
                        if bool(id_parsed.scheme):
                            update_dict['canonical'] = item['originId']
                if 'canonical' not in update_dict.keys():
                    if 'alternate' in item.keys():
                        if len(item['alternate']) > 0:
                            for alt_item in item['alternate']:
                                if 'href' in alt_item.keys():
                                    update_dict['canonical'] = alt_item['href']
                                    break
                fields = list(update_dict.keys())
                update_template = (
                    'INSERT OR REPLACE INTO rss_data('
                    + ', '.join(fields) +
                    ') VALUES ('
                    + ', '.join(['?' for field in fields]) +
                    ')'
                )
                update_tuple = tuple([update_dict[field] for field in fields])
                cursor.execute(update_template, update_tuple)
            conn.commit()
            info_update_dict = {
                'id': data['id'],
                'feedname': feed_name,
                'lastcached': cache_fname.replace('.js', '')
            }
            if 'updated' in data.keys():
                info_update_dict['updated'] = int(data['updated'])
            if 'title' in data.keys():
                info_update_dict['title'] = data['title']
            if 'alternate' in data.keys():
                if len(data['alternate']) > 0:
                    for item in data['alternate']:
                        if 'href' in item.keys():
                            info_update_dict['url'] = item['href']
                            break
            info_fields = list(info_update_dict.keys())
            info_update_template = (
                'INSERT OR REPLACE INTO rss_info('
                + ', '.join(info_fields) +
                ') VALUES ('
                + ', '.join(['?' for field in info_fields]) +
                ')'
            )
            info_update_tuple = tuple([info_update_dict[field] for field in info_fields])
            cursor.execute(info_update_template, info_update_tuple)
            conn.commit()
            print('  > Done: {}'.format(cache_fname.replace('.js', '')))

    conn.close()

    return


if __name__ == '__main__':
    cache_dir = 'Cached'
    cache_rss(cache_dir, 'rss_info.txt')
    update_db(cache_dir, 'rss_database.db', True)
