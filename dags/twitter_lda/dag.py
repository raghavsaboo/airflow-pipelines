"""simple Airflow data pipeline example using Twitter API
"""

from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.subdag_operator import SubDagOperator
from airflow.operators.python_operator import PythonOperator
from airflow.hooks import postgres_hook
from tweepy import API, Cursor, OAuthHandler
from configparser import ConfigParser
from csv import DictWriter, writer
from collections import Counter
from datetime import datetime, timedelta
import pandas as pd
from sklearn import datasets
import os.path
import psycopg2
from util import postgres_query, extract_tweet_data

CONFIG_FILE = os.path.abspath(os.path.join(__file__, '../twitter_api.cfg'))
RAW_TWITTER_DATA_DIRECTORY = os.path.abspath(os.path.join(__file__, '../../raw_data/'))
KEYWORDS_OF_INTEREST = ['tensorflow', 'reactjs', 'nodejs']
MAX_TWEEPY_PAGES = 1

dag_args = {
    'owner': 'kpmg',
    'depends_on_past': False,
    'start_date': datetime(2019, 1, 1),
    'email': 'trial@kpmg.com',
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'schedule_interval': '0 * * * *', # or @hourly
}

dag = DAG('twitter_lda', default_args=dag_args, schedule_interval='@daily')


def search_twitter(keyword, max_pages, twitter_config, csv_directory, **kwargs):
    """Searches Twitter for tweets with the passsed in keyword and stores the
    the result in the data folder locally as a csv file.
    
    Arguments:
        keyword {string} -- keyword to be used to search for relevant tweets
    """
    config = ConfigParser()
    config.read(twitter_config)
    auth = OAuthHandler(config.get('twitter', 'consumer_key'),
                        config.get('twitter', 'consumer_secret'))
    auth.set_access_token(config.get('twitter', 'access_token'),
                          config.get('twitter', 'access_token_secret'))
    api = API(auth)

    all_tweets = []
    
    page_num = 0

    # use the {{ ds }} = execution date variable passed in as part of context provided
    # by Airflow through Jinja macros
    since_date = datetime.strptime(kwargs.get('ds'), '%Y-%m-%d').date() - timedelta(hours=1)
    query += ' since:{} until:{}'.format(since_date.strftime('%Y-%m-%d'), kwargs.get('ds'))

    print('Searching Twitter with: %s' % keyword)

    for page in Cursor(api.search, q=keyword, monitor_rate_limit=True, wait_on_rate_limit=True).pages():
        all_tweets.extend([extract_tweet_data(t, keyword) for t in page])
        page_num += 1
        if page_num > max_pages:
            break
    
    # If it is an empty result, stop here
    if not len(all_tweets):
        return

    if not os.path.exists(csv_directory):
        os.makedirs(csv_directory)
    
    filename = '{}/{}_{}.csv'.format(csv_directory, keyword, datetime.now().strftime('%m%d%Y%H%M%S'))

    with open(filename, 'w') as raw_file:
        raw_writer = DictWriter(raw_file, fieldnames=all_tweets[0].keys())
        raw_writer.writeheader()
        raw_writer.writerows(all_tweets)

def csv_to_postgres(csv_directory, **kwargs):
    """ Very basic csv to postgres pipeline using Pandas.
    
    Keyword Arguments:
        csv_directory {string} -- directory where raw tweets csv is stored 
    """
    conn = psycopg2.connect("host=datapostgres user=data password=data dbname=data")
    cur = conn.cursor()
    for fname in glob.glob('{}/*.csv'.format(csv_directory)):
        if '_read' not in fname:
            try:
                df = pd.read_csv(fname)
            except pd.io.common.EmptyDataError:
                continue

with dag:
    create_twitter_schema = PythonOperator(
        task_id='create_twitter_schema',
        provide_context=False,
        python_callable=create_table,
        op_kwargs={'sql_query': 'CREATE SCHEMA IF NOT EXISTS twitter'}
    )

    create_raw_tweets_table = PythonOperator(
        task_id='create_raw_tweets_table',
        provide_context=False,
        python_callable=create_table,
        op_kwargs={'sql_query': 'CREATE TABLE raw_twitter_data' \ 
                                '(id serial PRIMARY KEY, created_at datetime, '
                                'user_id varchar, name varchar, ' \
                                'location varchar,' \ 
                                'text varchar, query varchar);'}
    )

    create_twitter_schema.set_downstream(create_raw_tweets_table)

    for term in KEYWORDS_OF_INTEREST:
        task_id = 'search_twitter_for_{}'.format(term)
        search = PythonOperator(task_id=task_id,
                                provide_context=True, 
                                python_callable=search_twitter,
                                params={'query': term})
        search.set_upstream(create_raw_data_table)
    
    insert_raw_tweets_into_db