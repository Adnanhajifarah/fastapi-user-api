import psycopg2

def get_connection():
    conn = psycopg2.connect(
        dbname="fast_apidb",
        user="adn",
        password="",
        host="localhost",
        port="5432"
    )
    return conn