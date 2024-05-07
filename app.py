from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from datetime import datetime
import psycopg2
import psycopg2.extras
import os
#from dotenv import load_dotenv
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from functools import wraps


app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'ReeRa'  
csrf = CSRFProtect(app)
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
    lst = []
    number_of_rows = 40
    for _ in range(number_of_rows):
        lst.append(['', '', '', ''])
    if 'user_id' in session:
        try:
            user_id = session.get('user_id')
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
    return render_template("index.html", db_status=db_status, db_message=db_message, user_message=user_message, tables=tables, user_name=user_name, lst = lst)



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
            return redirect(url_for('home'))
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

        if not user or not bcrypt.check_password_hash(user['password_hash'], password):
            flash('Login failed. Please check your credentials.', 'error')
            return redirect(url_for('home'))  # Redirect back to login page to show the error message
        else:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('dashboard'))

    # If the method is not POST (i.e., the user is accessing the login page directly), 
    # or if the login failed and redirected here, just render the login template.
    # Remove or comment out `print(session['user_id'])` since it's not safe here.
    # print(session['user_id'])
    return render_template('index.html')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'is_admin' not in session or not session['is_admin']:
            flash('Admin access required', 'error')
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/users', defaults={'user_id': None})
@app.route('/admin/users/<int:user_id>')
@admin_required
def admin_users(user_id):  # Add user_id as a parameter here
    if not session.get('is_admin', False):
        flash('Admin access required', 'error')
        return redirect(url_for('login'))

    # Initialize variables to avoid ReferenceError
    users, user_records, target_details_list , weights = [], None, [], []

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT * FROM users')
        users = cur.fetchall()
        
        if user_id:  # Only fetch records if user_id is provided
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_records = cur.fetchone()
            print(user_records)
            # Get Target weight details
            cur.execute("""
            SELECT created_date, target_weight, date_of_target, status 
            FROM target_weights 
            WHERE user_id = %s
            """, (user_id,))
            target_details = cur.fetchall()

            for target in target_details:
                date_of_target = target[2]  # The target's end date
                cur.execute("""
                    SELECT weight, date_of_measurement 
                    FROM weights 
                    WHERE user_id = %s AND date_of_measurement <= %s
                    ORDER BY date_of_measurement DESC 
                    LIMIT 1
                    """, (user_id, date_of_target))
                latest_weight = cur.fetchone()
    
                # If a weight record exists that meets the condition
                if latest_weight:
                    # Convert each target detail to list and append the formatted weight string
                    formatted_target = list(target) + [f"{latest_weight[0]} (at {latest_weight[1].strftime('%Y-%m-%d')})"]
                else:
                    # If no weight was found before the target date, append a placeholder or None
                    formatted_target = list(target) + ["No weight recorded before target end date"]
    
                target_details_list.append(formatted_target)

            cur.execute("SELECT * FROM weights WHERE user_id = %s", (user_id,))
            weights = cur.fetchall()

        cur.close()
    except Exception as e:
        flash(f'Failed to fetch users: {e}', 'error')
    finally:
        if conn is not None:
            conn.close()

    return render_template('admin_users.html', users=users, user_records=user_records, target_weights=target_details_list, weights=weights, selected_user_id=user_id)



@app.route('/admin/users/<int:user_id>/records')
@admin_required
def admin_user_records(user_id):
    if 'user_id' not in session or not session.get('is_admin', False):
        flash('Admin access required', 'error')
        return redirect(url_for('login'))

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Fetch user info
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user_info = cur.fetchone()

        # Fetch target_weights
        cur.execute('SELECT * FROM target_weights WHERE user_id = %s', (user_id,))
        target_weights = cur.fetchall()

        # Fetch weights
        cur.execute('SELECT * FROM weights WHERE user_id = %s', (user_id,))
        weights = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        flash(f'Failed to fetch records: {e}', 'error')
        user_info, target_weights, weights = None, [], []

    return render_template('admin_user_records.html', user_info=user_info, target_weights=target_weights, weights=weights)

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        try:
            user_id = session.get('user_id')
            print("user ID is: ", user_id)
            #update_target_weight_status(user_id)
            conn = psycopg2.connect(DATABASE_URL)
            # Get User details
            cur = conn.cursor()
            cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
            user_name_result = cur.fetchone()
            cur.execute("SELECT name, date_of_birth, sex, activity_level, height FROM users WHERE id = %s", (user_id,))
            user_details = cur.fetchall()
            print("user details are:", user_details)
            user_details_list = []
            user_details_list = [list(user_details[0])]
            cur.close()
            # Get Target weight details
            cur = conn.cursor()
            cur.execute("""
            SELECT created_date, target_weight, date_of_target, status 
            FROM target_weights 
            WHERE user_id = %s
            """, (user_id,))
            target_details = cur.fetchall()
            cur.close()

            target_details_list = []

            for target in target_details:
                date_of_target = target[2]  # The target's end date
                cur = conn.cursor()
                cur.execute("""
                    SELECT weight, date_of_measurement 
                    FROM weights 
                    WHERE user_id = %s AND date_of_measurement <= %s
                    ORDER BY date_of_measurement DESC 
                    LIMIT 1
                    """, (user_id, date_of_target))
                latest_weight = cur.fetchone()
                cur.close()
    
                # If a weight record exists that meets the condition
                if latest_weight:
                    # Convert each target detail to list and append the formatted weight string
                    formatted_target = list(target) + [f"{latest_weight[0]} (at {latest_weight[1].strftime('%Y-%m-%d')})"]
                else:
                    # If no weight was found before the target date, append a placeholder or None
                    formatted_target = list(target) + ["No weight recorded before target end date"]
    
                target_details_list.append(formatted_target)
            conn.close()
            number_of_rows = 5
            for _ in range(number_of_rows):
                user_details_list.append([' ', '', '', '', ''])
                if len(target_details_list) <= number_of_rows:
                    target_details_list.append([' ', '', '', ''])
            
            if user_name_result:
                user_name = user_name_result[0]
                user_message = f'Welcome, {user_name}!'
            else:
                user_name = None
                user_message = 'User not found.'
        except Exception as e:
            user_name = None
            user_message = f'Error fetching user information: {str(e)}'

        if session.get('is_admin', True):
            return render_template('admin_dashboard.html', user_name=user_name, user_message=user_message, user_details_list=user_details_list, target_details_list=target_details_list)
        else:
            # Non-admin users get the regular dashboard
            return render_template('dashboard.html', user_name=user_name, user_message=user_message, user_details_list=user_details_list, target_details_list=target_details_list)
    else:
        return redirect(url_for('login'))


       

@app.route('/logout')
def logout():
    # Remove 'user_id' from session
    session.pop('user_id', None)
    # Redirect to login page or home page after logout
    return redirect(url_for('home'))

@app.route('/add_weight', methods=['POST'])
def add_weight():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        date_of_measurement = request.json['date_of_measurement']
        weight = request.json['weight']

        # Convert date_of_measurement to a datetime object to ensure it's a valid date
        date_of_measurement = datetime.strptime(date_of_measurement, '%Y-%m-%d').date()

        # Ensure weight is a float
        weight = float(weight)

        # Check if a weight record for the given date already exists
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('SELECT * FROM weights WHERE user_id = %s AND date_of_measurement = %s',
                    (session['user_id'], date_of_measurement))
        if cur.fetchone():
            return jsonify({'error': 'Weight entry for this date already exists.'}), 400

        # Insert the new weight entry
        cur.execute('INSERT INTO weights (user_id, date_of_measurement, weight) VALUES (%s, %s, %s)', 
                    (session['user_id'], date_of_measurement, weight))
        conn.commit()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error occurred.'}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': 'Weight added successfully'}), 200



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
    print(weights)
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
        name = request.form.get('name')
        dob = request.form.get('dob')
        sex = request.form.get('sex')
        activity_level = request.form.get('activity_level')
        height = request.form.get('height')
        # Print form data for debugging
        print(f"Updating user {user_id} with: {name}, {dob}, {sex}, {activity_level}, {height}")
        
        # Update database
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                UPDATE users SET name = %s, date_of_birth = %s, sex = %s, activity_level = %s, height = %s
                WHERE id = %s
                """, (name, dob, sex, activity_level, height, user_id))
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
        cur.execute("SELECT name, date_of_birth, sex, activity_level, height FROM users WHERE id = %s", (user_id,))
        user_details = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        user_details = None
        flash(f'An error occurred while fetching user details: {e}', 'error')
    
    return render_template('personal_details.html', user_details=user_details)

@app.route('/api/user_details')
def api_user_details():
    if 'user_id' not in session:
        # Return an error message in JSON format if the user is not logged in
        return jsonify({'error': 'User not authenticated'}), 401

    user_id = session['user_id']

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Assuming 'height' is stored in meters or another consistent unit
        cur.execute("SELECT height FROM users WHERE id = %s", (user_id,))
        user_details = cur.fetchone()
        cur.close()
        conn.close()

        if user_details:
            return jsonify({'height': user_details['height']})
        else:
            return jsonify({'error': 'User details not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/weight_trend')
def api_weight_trend():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Please log in to view this content'}), 401

    # Fetch weight data from the database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT date_of_measurement, weight FROM weights WHERE user_id = %s ORDER BY date_of_measurement DESC', (user_id,))
    weights = cur.fetchall()
    cur.close()
    conn.close()

    # Prepare data for JSON response
    dates = [weight['date_of_measurement'].strftime('%Y-%m-%d') for weight in weights]  # Convert dates to strings
    weights = [weight['weight'] for weight in weights]

    return jsonify({'dates': dates, 'weights': weights})

@app.route('/plots')
def plots():
    # Add any data fetching or processing here if necessary
    return render_template('plots.html')

@app.route('/targets', methods=['GET'])
def get_targets():
    if 'user_id' not in session:
        # Redirect to login page if user is not logged in
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = psycopg2.connect(DATABASE_URL)
    # Get Target weight details
    cur = conn.cursor()
    cur.execute("""
    SELECT id, created_date, target_weight, date_of_target, status 
    FROM target_weights 
    WHERE user_id = %s
    ORDER BY created_date DESC
    """, (user_id,))
    target_details = cur.fetchall()
    cur.close()

    target_details_list = []

    for target in target_details:
        date_of_target = target[3]  # The target's end date
        cur = conn.cursor()
        cur.execute("""
            SELECT weight, date_of_measurement 
            FROM weights 
            WHERE user_id = %s AND date_of_measurement <= %s
            ORDER BY date_of_measurement DESC 
            LIMIT 1
            """, (user_id, date_of_target))
        latest_weight = cur.fetchone()
        cur.close()
    
        # If a weight record exists that meets the condition
        if latest_weight:
            # Convert each target detail to list and append the formatted weight string
            formatted_target = list(target) + [f"{latest_weight[0]} (at {latest_weight[1].strftime('%Y-%m-%d')})"]
        else:
            # If no weight was found before the target date, append a placeholder or None
            formatted_target = list(target) + ["No weight recorded before target end date"]
    
        target_details_list.append(formatted_target)
    conn.close()
    print(target_details_list)
    return render_template("target_registry.html", target_details_list=target_details_list)


@app.route('/add_target_weight', methods=['POST'])
def add_target_weight():
    if 'user_id' not in session:
        flash("Please log in to add target weight.", "info")
        return redirect(url_for('login'))

    user_id = session['user_id']
    date_of_target = request.form.get('date_of_target')
    target_weight = request.form.get('target_weight')

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Check if there's an existing target weight with 'In Progress' status
        cur.execute("""
            SELECT id FROM target_weights
            WHERE user_id = %s AND status = 'In Progress'
        """, (user_id,))
        existing_target = cur.fetchone()

        if existing_target:
            # Update status of existing target weight to 'Interrupted'
            cur.execute("""
                UPDATE target_weights SET status = 'Interrupted'
                WHERE id = %s
            """, (existing_target[0],))
            flash("Existing target weight has been marked as 'Interrupted'.", "warning")

        # Insert the new target weight entry
        cur.execute("""
            INSERT INTO target_weights (user_id, date_of_target, target_weight, status)
            VALUES (%s, %s, %s, 'In Progress')
        """, (user_id, date_of_target, target_weight))
        
        conn.commit()
        flash("New target weight added successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/delete_target/<int:target_id>')
def delete_target(target_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('DELETE FROM target_weights WHERE id = %s AND user_id = %s', (target_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('get_targets'))

def update_target_weight_status(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Get the latest weight of the user
    cur.execute("""
        SELECT weight FROM weights WHERE user_id = %s ORDER BY date_of_measurement DESC LIMIT 1
    """, (user_id,))
    latest_weight = cur.fetchone()[0] if cur.rowcount > 0 else None

    # Update the status based on conditions
    if latest_weight is not None:
        today = datetime.today().date()
        
        # Update to 'Failed' if target date is passed and target weight is not achieved
        cur.execute("""
            UPDATE target_weights
            SET status = 'Failed'
            WHERE user_id = %s AND date_of_target < %s AND target_weight < %s AND status = 'In Progress'
        """, (user_id, today, latest_weight))

        # Update to 'Success' if target weight is achieved before the target date
        cur.execute("""
            UPDATE target_weights
            SET status = 'Success'
            WHERE user_id = %s AND target_weight >= %s AND status = 'In Progress'
        """, (user_id, latest_weight))

    conn.commit()
    cur.close()

@app.route('/api/target_weights')
def api_target_weights():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Please log in to view this content'}), 401

    # Fetch weight data from the database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
            SELECT created_date, target_weight, date_of_target, status 
            FROM target_weights 
            WHERE user_id = %s
            """, (user_id,))
    targets = cur.fetchall()
    cur.close()
    conn.close()

    # Prepare data for JSON response
    dates = [target['created_date'].strftime('%Y-%m-%d') for target in targets]  # Convert dates to strings
    status = [target['status'] for target in targets]

    return jsonify({'dates': dates, 'status': status})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
