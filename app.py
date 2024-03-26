from flask import Flask, jsonify, render_template, request, redirect, url_for
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv


app = Flask(__name__)
if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    load_dotenv()
    DATABASE_URL = "dbname={databasename} user = {username} host = {hostname} password = {password} port = {portnumber}".format(
    username=os.environ.get("DB_USERNAME"),
    password=os.environ.get("DB_PASSWORD"),
    hostname=os.environ.get("DB_HOSTNAME"),
    databasename=os.environ.get("DB_NAME"),
    portnumber=os.environ.get("PORT_NUMBER"),
    )
else:
    from config import DATABASE_URL

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")

@app.route('/test', methods=['GET'])
def test_connection():
    try:
        # Attempt to establish a connection to the database
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        return render_template("test_connection.html")
    except Exception as e:
        return f"An error occurred: {e}"    

@app.route('/add_user', methods=['POST'])
def add_user():
    # Get form data
    username = request.form['username']
    email = request.form['email']
    
    # Insert form data into the database, without specifying the id
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO users (username, email) VALUES (%s, %s)', (username, email))
        conn.commit()  # Commit the transaction to save the insert
    except Exception as e:
        # If an error occurs, roll back the transaction
        conn.rollback()
        return f"An error occurred: {e}"
    finally:
        # Close the cursor and connection
        cur.close()
        conn.close()

@app.route('/add_user_form', methods=['GET'])
def add_user_form():
    return render_template("add_user.html")  # Ensure you create add_user.html


@app.route('/users', methods=['GET'])
def get_users():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("get_users.html", users=users)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
