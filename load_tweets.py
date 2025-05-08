#!/usr/bin/env python3
import sqlalchemy
import os
import datetime
import zipfile
import io
import json
import argparse

# Helper function to remove null characters
# PostgreSQL does not support the null character \x00 in strings
# This replaces nulls so they don't break COPY or INSERT

def remove_nulls(s):
    if s is None:
        return None
    return s.replace('\x00', '')

# Get or create a URL in the urls table and return its id

def get_id_urls(url, connection):
    sql = sqlalchemy.sql.text('''
        INSERT INTO urls (url)
        VALUES (:url)
        ON CONFLICT DO NOTHING
        RETURNING id_urls;
    ''')
    res = connection.execute(sql, {'url': url}).first()
    if res is None:
        sql = sqlalchemy.sql.text('''
            SELECT id_urls FROM urls WHERE url = :url;
        ''')
        res = connection.execute(sql, {'url': url}).first()
    return res[0]

# Insert a message (and its user + URLs) into the database

def insert_message(connection, message):
    # Skip if already loaded
    exists_sql = sqlalchemy.sql.text(
        'SELECT id_messages FROM messages WHERE id_messages = :id;'
    )
    if connection.execute(exists_sql, {'id': message['id']}).first():
        return

    # Wrap in a transaction to ensure atomicity
    with connection.begin():
        # 1. Insert or skip user
        user = message['user']
        user_sql = sqlalchemy.sql.text('''
            INSERT INTO users (id_users, created_at, username, password_hash, description)
            VALUES (:id, :created_at, :username, :password_hash, :description)
            ON CONFLICT (id_users) DO NOTHING;
        ''')
        connection.execute(user_sql, {
            'id': user['id'],
            'created_at': user.get('created_at'),
            'username': remove_nulls(user['username']),
            'password_hash': user.get('password_hash', ''),
            'description': remove_nulls(user.get('description'))
        })

        # 2. Insert the message
        content = remove_nulls(message.get('content') or message.get('text', ''))
        msg_sql = sqlalchemy.sql.text('''
            INSERT INTO messages (id_messages, id_users, created_at, content)
            VALUES (:id, :user_id, :created_at, :content)
            ON CONFLICT DO NOTHING;
        ''')
        connection.execute(msg_sql, {
            'id': message['id'],
            'user_id': user['id'],
            'created_at': message.get('created_at'),
            'content': content
        })

        # 3. Insert URLs and link them
        entities = message.get('entities', {})
        for url_obj in entities.get('urls', []):
            expanded = url_obj.get('expanded_url')
            if not expanded:
                continue
            url_id = get_id_urls(expanded, connection)
            link_sql = sqlalchemy.sql.text('''
                INSERT INTO message_urls (id_messages, id_urls)
                VALUES (:msg_id, :url_id)
                ON CONFLICT DO NOTHING;
            ''')
            connection.execute(link_sql, {
                'msg_id': message['id'],
                'url_id': url_id
            })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Load JSON message archives into Postgres'
    )
    parser.add_argument('--db', required=True, help='Postgres connection string')
    parser.add_argument('--inputs', nargs='+', required=True,
                        help='One or more ZIP files containing JSONL')
    parser.add_argument('--print_every', type=int, default=1000,
                        help='Log progress every N records')
    args = parser.parse_args()

    # Establish DB connection
    engine = sqlalchemy.create_engine(
        args.db,
        connect_args={'application_name': 'load_tweets.py'}
    )
    connection = engine.connect()

    # Process each archive in reverse sorted order
    for filename in sorted(args.inputs, reverse=True):
        with zipfile.ZipFile(filename, 'r') as archive:
            print(datetime.datetime.now(), 'Processing', filename)
            for subfilename in sorted(archive.namelist(), reverse=True):
                with io.TextIOWrapper(archive.open(subfilename), encoding='utf-8') as f:
                    for i, line in enumerate(f, start=1):
                        msg = json.loads(line)
                        insert_message(connection, msg)
                        if i % args.print_every == 0:
                            print(
                                datetime.datetime.now(), filename, subfilename,
                                f'i={i}', f'id={msg["id"]}'
                            )
