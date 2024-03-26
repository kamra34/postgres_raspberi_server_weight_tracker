from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv


app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = 'ReeRa'
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

@app.route('/')
def home():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Fetch the table names from the database
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'public'""")
        tables = [table[0] for table in cur.fetchall()]
        cur.close()
        conn.close()
        db_status = 'up'
        message = 'Connected to the database. Tables: ' + ', '.join(tables)
    except Exception as e:
        db_status = 'down'
        message = 'Failed to connect to the database.'
        tables = []

    return render_template("index.html", db_status=db_status, message=message, tables=tables)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        # Insert the new user into the database
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('INSERT INTO users (name, password_hash) VALUES (%s, %s)', (name, password_hash))
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT * FROM users WHERE name = %s', (name,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        else:
            return 'Login failed'
    return render_template('index.html')

@app.route('/logout')
def logout():
    # Remove 'user_id' from session
    session.pop('user_id', None)
    # Redirect to login page or home page after logout
    return redirect(url_for('home'))


@app.route('/add_weight', methods=['GET', 'POST'])
def add_weight():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        date_of_measurement = request.form['date_of_measurement']
        weight = request.form['weight']
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('INSERT INTO weights (user_id, date_of_measurement, weight) VALUES (%s, %s, %s)', 
                    (session['user_id'], date_of_measurement, weight))
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('home'))
    return render_template('add_weight.html')


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

@app.route('/weights', methods=['GET'])
def get_weights():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('SELECT * FROM weights')
    weights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("get_weights.html", weights=weights)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
