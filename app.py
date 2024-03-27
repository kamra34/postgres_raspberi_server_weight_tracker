from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
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

def db_check(DATABASE_URL):
    # Attempt to connect to the database and fetch table names
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [table[0] for table in cur.fetchall()]
        db_message = 'Database is up and running. Available Tables: ' + ', '.join(tables)
        db_status = 'up'
        cur.close()
        conn.close() 
    except Exception as e:
        db_message = 'Failed to connect to the database. Error: ' + str(e)
        db_status = 'down'
        tables = []
    return(db_message, db_status, tables)

@app.route('/')
def home():
    # Check if user is logged in and get their name
    user_name = None
    db_message, db_status, tables = db_check(DATABASE_URL)
    if 'user_id' in session:
        try:
            user_id = session.get('user_id')
            print()
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
            user_name = cur.fetchone()[0] if cur.rowcount > 0 else None
            cur.close()
            conn.close()
            user_message = f'Welcome, {user_name}!' if user_name else 'User not found.'
        except Exception as e:
            user_message = 'Error fetching user information: ' + str(e)
    else:
        user_message = 'Not logged in.'
    # Pass separate messages for database status and user login status to the template
    return render_template("index.html", db_status=db_status, db_message=db_message, user_message=user_message, tables=tables, user_name=user_name)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
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
        except Exception as e:
            flash('Registration failed: Username may already exist.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

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

        if not user or not bcrypt.check_password_hash(user['password_hash'], password):
            flash('Login failed. Please check your credentials.', 'error')
            return redirect(url_for('home'))  # Redirect back to login page to show the error message
        else:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))

    # If the method is not POST (i.e., the user is accessing the login page directly), 
    # or if the login failed and redirected here, just render the login template.
    # Remove or comment out `print(session['user_id'])` since it's not safe here.
    # print(session['user_id'])
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        try:
            user_id = session.get('user_id')
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
            user_name_result = cur.fetchone()
            cur.close()
            conn.close()
            if user_name_result:
                user_name = user_name_result[0]
                user_message = f'Welcome, {user_name}!'
            else:
                user_name = None
                user_message = 'User not found.'
        except Exception as e:
            user_name = None
            user_message = f'Error fetching user information: {str(e)}'
    else:
        return redirect(url_for('login'))

    # Ensure that user_name is always defined, even if it's None, to prevent rendering issues.
    return render_template('dashboard.html', user_name=user_name, user_message=user_message)


       

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

        return redirect(url_for('get_weights'))
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

@app.route('/weights', methods=['GET'])
def get_weights():
    if 'user_id' not in session:
        # Redirect to login page if user is not logged in
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Modify the query to filter weights by the logged-in user's ID
    cur.execute('SELECT * FROM weights WHERE user_id = %s ORDER BY date_of_measurement DESC', (user_id,))
    weights = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("get_weights.html", weights=weights)

@app.route('/delete_weight/<int:weight_id>')
def delete_weight(weight_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('DELETE FROM weights WHERE id = %s AND user_id = %s', (weight_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('get_weights'))

@app.route('/update_weight/<int:weight_id>', methods=['POST'])
def update_weight(weight_id):
    if 'user_id' not in session:
        return {'error': 'Unauthorized'}, 401
    
    data = request.json
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('UPDATE weights SET date_of_measurement = %s, weight = %s WHERE id = %s AND user_id = %s',
                (data['date_of_measurement'], data['weight'], weight_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()

    return {'success': 'Weight updated successfully'}, 200

@app.route('/personal_details', methods=['GET', 'POST'])
def personal_details():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        # Extract form data
        dob = request.form.get('dob')
        sex = request.form.get('sex')
        activity_level = request.form.get('activity_level')
        height = request.form.get('height')
        
        # Update database
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET date_of_birth = %s, sex = %s, activity_level = %s, height = %s
                WHERE id = %s
                """, (dob, sex, activity_level, height, user_id))
            conn.commit()
            cur.close()
            conn.close()
            flash('Details updated successfully', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
    
    # Fetch current user details to prefill the form
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT date_of_birth, sex, activity_level, height FROM users WHERE id = %s", (user_id,))
        user_details = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        user_details = None
        flash(f'An error occurred while fetching user details: {e}', 'error')
    
    return render_template('personal_details.html', user_details=user_details)



if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
