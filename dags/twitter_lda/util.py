import psycopg2

def postgres_query(sql_query):
    """Runs a sql query against the postgres public database.
    
    Arguments:
        sql_query {string} -- the sql query to be executed and commited on 
                              database
    """
    conn = psycopg2.connect("host=datapostgres user=data password=data dbname=data")
    cur = conn.cursor()
    cur.execute(sql_query)
    conn.commit()
    cur.close()
    conn.close()

def extract_tweet_data(tweepy_obj, query):
    """Extract the relevant fields from the JSON response from Twitter's API.
    
    Arguments:
        tweepy_obj {tweepy object} -- the tweepy object storing the result from 
                                      twitter
        query {string} -- the search string used to search twitter
    
    Returns:
        dictionary -- user_id, name, location, text, and query associate with 
                      the tweet
    """

    return {
        'user_id': tweepy_obj.user.screen_name,
        'created_at': tweepy_obj.created_at,
        'name': tweepy_obj.user.name,
        'location': tweepy_obj.user.location,
        'text': tweepy_obj.text,
        'query': query,
    }

