import psycopg2
import psycopg2.extras
from flask import Flask, jsonify
import numpy as np

DATABASE_URL = "dbname='initTest' user='postgres' host='192.168.1.67' password='44krn44' port='5432'"

try:
    # Attempt to establish a connection to the database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()

    print(conn)
    print(users)

    cur.close()
    conn.close()
    
    print("Successfully connected to the database!")
    
    # Optionally, you can add code here to execute SQL commands
    # For now, we'll just close the connection
    conn.close()
except Exception as e:
    print("An error occurred:", e)
