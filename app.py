import os
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    flash,
    render_template_string
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key-in-production"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )
else:
    database_url = "sqlite:///hure_management.db"


app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)


# ============================================================
# DATABASE MODELS
# ============================================================

class User(db.Model):

    __tablename__ = "hure_users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        nullable=False,
        default="worker"
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    assignments = db.relationship(
        "Assignment",
        backref="worker",
        lazy=True
    )


class Job(db.Model):

    __tablename__ = "hure_jobs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    location = db.Column(
        db.String(200)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    assignments = db.relationship(
        "Assignment",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Assignment(db.Model):

    __tablename__ = "hure_assignments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    job_id = db.Column(
        db.Integer,
        db.ForeignKey("hure_jobs.id"),
        nullable=False
    )

    worker_id = db.Column(
        db.Integer,
        db.ForeignKey("hure_users.id"),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="Pending"
    )

    assigned_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# ADMIN REQUIRED
# ============================================================

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        if session.get("role") != "admin":

            flash(
                "Admin access required.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# BASE HTML TEMPLATE
# ============================================================

BASE_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
name="viewport"
content="width=device-width, initial-scale=1"
>

<title>
{{ title }}
</title>


<style>

* {

box-sizing:border-box;

}

body {

margin:0;

font-family:Arial, sans-serif;

background:#f4f6f9;

color:#333;

}


.navbar {

background:#1f2937;

color:white;

padding:15px 30px;

display:flex;

justify-content:space-between;

align-items:center;

}


.navbar h2 {

margin:0;

font-size:20px;

}


.navbar a {

color:white;

text-decoration:none;

margin-left:15px;

padding:8px 12px;

border-radius:5px;

}


.navbar a:hover {

background:#374151;

}


.container {

max-width:1200px;

margin:auto;

padding:30px;

}


.card {

background:white;

padding:20px;

border-radius:10px;

margin-bottom:20px;

box-shadow:0 2px 8px rgba(0,0,0,.08);

}


.stats {

display:grid;

grid-template-columns:
repeat(auto-fit,minmax(180px,1fr));

gap:15px;

margin-bottom:25px;

}


.stat {

background:white;

padding:20px;

border-radius:10px;

box-shadow:0 2px 8px rgba(0,0,0,.08);

}


.stat h3 {

margin:0;

font-size:14px;

color:#666;

}


.stat p {

font-size:28px;

margin:10px 0 0;

font-weight:bold;

}


input,

textarea,

select {

width:100%;

padding:10px;

margin-top:6px;

margin-bottom:15px;

border:1px solid #ddd;

border-radius:6px;

}


button {

background:#2563eb;

color:white;

border:none;

padding:10px 18px;

border-radius:6px;

cursor:pointer;

}


button:hover {

background:#1d4ed8;

}


table {

width:100%;

border-collapse:collapse;

margin-top:15px;

}


th,

td {

padding:12px;

border-bottom:1px solid #ddd;

text-align:left;

}


th {

background:#f3f4f6;

}


.badge {

padding:5px 10px;

border-radius:20px;

font-size:12px;

color:white;

}


.pending {

background:#f59e0b;

}


.progress {

background:#3b82f6;

}


.done {

background:#10b981;

}


.notdone {

background:#ef4444;

}


.flash {

padding:12px;

margin-bottom:15px;

border-radius:6px;

}


.success {

background:#d1fae5;

color:#065f46;

}


.danger {

background:#fee2e2;

color:#991b1b;

}


.login-box {

max-width:400px;

margin:100px auto;

background:white;

padding:30px;

border-radius:10px;

box-shadow:0 4px 15px rgba(0,0,0,.1);

}


.row {

display:grid;

grid-template-columns:
repeat(auto-fit,minmax(250px,1fr));

gap:20px;

}


.small {

font-size:13px;

color:#666;

}


@media(max-width:600px) {

.container {

padding:15px;

}

table {

font-size:12px;

}

}

</style>

</head>


<body>


{% if session.get("user_id") %}

<div class="navbar">

<h2>
INTEGRATED HURE MANAGEMENT SYSTEM
</h2>

<div>

<a href="{{ url_for('dashboard') }}">
Dashboard
</a>

{% if session.get("role") == "admin" %}

<a href="{{ url_for('workers') }}">
Workers
</a>

<a href="{{ url_for('jobs') }}">
Jobs
</a>

{% endif %}

<a href="{{ url_for('logout') }}">
Logout
</a>

</div>

</div>

{% endif %}


<div class="container">

{% with messages = get_flashed_messages(with_categories=true) %}

{% for category,message in messages %}

<div class="flash {{ category }}">

{{ message }}

</div>

{% endfor %}

{% endwith %}


{{ content|safe }}

</div>


</body>

</html>

"""


# ============================================================
# RENDER PAGE
# ============================================================

def render_page(title, content):

    return render_template_string(
        BASE_HTML,
        title=title,
        content=content
    )


# ============================================================
# CREATE DEFAULT ADMIN
# ============================================================

def create_default_admin():

    admin = User.query.filter_by(
        username="admin"
    ).first()

    if not admin:

        admin_password = os.environ.get(
            "ADMIN_PASSWORD",
            "admin123"
        )

        admin = User(

            name="System Administrator",

            username="admin",

            password=generate_password_hash(
                admin_password
            ),

            role="admin",

            active=True

        )

        db.session.add(admin)

        db.session.commit()


# ============================================================
# HOME
# ============================================================

@app.route("/")

def home():

    if "user_id" in session:

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)

def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            username=username
        ).first()


        if not user:

            flash(
                "Invalid username or password.",
                "danger"
            )

            return redirect(
                url_for("login")
            )


        if not user.active:

            flash(
                "This account is inactive.",
                "danger"
            )

            return redirect(
                url_for("login")
            )


        if not check_password_hash(
            user.password,
            password
        ):

            flash(
                "Invalid username or password.",
                "danger"
            )

            return redirect(
                url_for("login")
            )


        session["user_id"] = user.id

        session["name"] = user.name

        session["role"] = user.role


        return redirect(
            url_for("dashboard")
        )


    content = """

    <div class="login-box">

    <h2>
    HURE MANAGEMENT SYSTEM
    </h2>

    <p class="small">
    Login to continue
    </p>


    <form method="POST">


    <label>
    Username
    </label>

    <input
    type="text"
    name="username"
    required
    >


    <label>
    Password
    </label>

    <input
    type="password"
    name="password"
    required
    >


    <button type="submit">

    Login

    </button>


    </form>


    </div>

    """

    return render_page(
        "Login",
        content
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")

def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")

@login_required

def dashboard():

    user_id = session["user_id"]

    user = db.session.get(
        User,
        user_id
    )


    # ========================================================
    # ADMIN DASHBOARD
    # ========================================================

    if user.role == "admin":

        jobs = Job.query.order_by(
            Job.id.desc()
        ).all()


        workers = User.query.filter_by(
            role="worker",
            active=True
        ).order_by(
            User.name
        ).all()


        assignments = Assignment.query.all()


        total_jobs = len(jobs)


        done = sum(
            1
            for assignment in assignments
            if assignment.status == "Done"
        )


        notdone = sum(
            1
            for assignment in assignments
            if assignment.status == "Not Done"
        )


        pending = sum(
            1
            for assignment in assignments
            if assignment.status == "Pending"
        )


        in_progress = sum(
            1
            for assignment in assignments
            if assignment.status == "In Progress"
        )


        today_total = sum(

            1

            for job in jobs

            if job.created_at
            and job.created_at.date() == date.today()

        )


        content = """

        <h1>
        Welcome, {{ name }}
        </h1>


        <div class="stats">


        <div class="stat">

        <h3>
        Total Jobs
        </h3>

        <p>
        {{ total_jobs }}
        </p>

        </div>


        <div class="stat">

        <h3>
        Today's Jobs
        </h3>

        <p>
        {{ today_total }}
        </p>

        </div>


        <div class="stat">

        <h3>
        Workers
        </h3>

        <p>
        {{ total_workers }}
        </p>

        </div>


        <div class="stat">

        <h3>
        Done
        </h3>

        <p>
        {{ done }}
        </p>

        </div>


        <div class="stat">

        <h3>
        Pending
        </h3>

        <p>
        {{ pending }}
        </p>

        </div>


        </div>


        <div class="card">

        <h2>
        Recent Jobs
        </h2>


        <table>

        <tr>

        <th>
        ID
        </th>

        <th>
        Job
        </th>

        <th>
        Location
        </th>

        <th>
        Created
        </th>

        </tr>


        {% for job in jobs[:10] %}

        <tr>

        <td>
        {{ job.id }}
        </td>

        <td>
        {{ job.title }}
        </td>

        <td>
        {{ job.location or "-" }}
        </td>

        <td>
        {{ job.created_at.strftime("%Y-%m-%d") }}
        </td>

        </tr>

        {% endfor %}


        </table>


        </div>

        """


        rendered_content = render_template_string(

            content,

            name=user.name,

            jobs=jobs,

            total_jobs=total_jobs,

            today_total=today_total,

            total_workers=len(workers),

            done=done,

            pending=pending,

            notdone=notdone,

            in_progress=in_progress

        )


        return render_page(
            "Admin Dashboard",
            rendered_content
        )


    # ========================================================
    # WORKER DASHBOARD
    # ========================================================

    assignments = Assignment.query.filter_by(
        worker_id=user.id
    ).order_by(
        Assignment.id.desc()
    ).all()


    content = """

    <h1>
    Welcome, {{ name }}
    </h1>


    <div class="card">

    <h2>
    My Assigned Jobs
    </h2>


    <table>


    <tr>

    <th>
    Job
    </th>

    <th>
    Description
    </th>

    <th>
    Location
    </th>

    <th>
    Status
    </th>

    <th>
    Update
    </th>

    </tr>


    {% for assignment in assignments %}


    <tr>


    <td>

    {{ assignment.job.title }}

    </td>


    <td>

    {{ assignment.job.description or "-" }}

    </td>


    <td>

    {{ assignment.job.location or "-" }}

    </td>


    <td>

    <span class="badge">

    {{ assignment.status }}

    </span>

    </td>


    <td>


    <form
    method="POST"
    action="{{ url_for('update_assignment', assignment_id=assignment.id) }}"
    >


    <select name="status">

    <option
    value="Pending"
    >

    Pending

    </option>


    <option
    value="In Progress"
    >

    In Progress

    </option>


    <option
    value="Done"
    >

    Done

    </option>


    <option
    value="Not Done"
    >

    Not Done

    </option>


    </select>


    <button type="submit">

    Update

    </button>


    </form>


    </td>


    </tr>


    {% endfor %}


    </table>


    </div>


    """


    rendered_content = render_template_string(

        content,

        name=user.name,

        assignments=assignments

    )


    return render_page(
        "Worker Dashboard",
        rendered_content
    )


# ============================================================
# WORKERS
# ============================================================

@app.route(
    "/workers",
    methods=["GET", "POST"]
)

@admin_required

def workers():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        username = request.form.get(
            "username",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        )


        existing_user = User.query.filter_by(
            username=username
        ).first()


        if existing_user:

            flash(
                "Username already exists.",
                "danger"
            )

            return redirect(
                url_for("workers")
            )


        worker = User(

            name=name,

            username=username,

            password=generate_password_hash(
                password
            ),

            role="worker",

            active=True

        )


        db.session.add(worker)

        db.session.commit()


        flash(
            "Worker created successfully.",
            "success"
        )


        return redirect(
            url_for("workers")
        )


    worker_list = User.query.filter_by(
        role="worker"
    ).order_by(
        User.name
    ).all()


    content = """

    <div class="row">


    <div class="card">


    <h2>
    Add Worker
    </h2>


    <form method="POST">


    <label>
    Full Name
    </label>

    <input
    name="name"
    required
    >


    <label>
    Username
    </label>

    <input
    name="username"
    required
    >


    <label>
    Password
    </label>

    <input
    type="password"
    name="password"
    required
    >


    <button type="submit">

    Create Worker

    </button>


    </form>


    </div>


    <div class="card">


    <h2>
    Workers
    </h2>


    <table>


    <tr>

    <th>
    Name
    </th>

    <th>
    Username
    </th>

    <th>
    Status
    </th>

    </tr>


    {% for worker in workers %}


    <tr>

    <td>
    {{ worker.name }}
    </td>

    <td>
    {{ worker.username }}
    </td>

    <td>

    {% if worker.active %}

    Active

    {% else %}

    Inactive

    {% endif %}

    </td>

    </tr>


    {% endfor %}


    </table>


    </div>


    </div>


    """


    rendered_content = render_template_string(

        content,

        workers=worker_list

    )


    return render_page(
        "Workers",
        rendered_content
    )

# ============================================================
# DELETE WORKER
# ============================================================

@app.route(
    "/workers/<int:worker_id>/delete",
    methods=["POST"]
)

@admin_required
def delete_worker(worker_id):

    worker = db.session.get(
        User,
        worker_id
    )

    if not worker:

        flash(
            "Worker not found.",
            "danger"
        )

        return redirect(
            url_for("workers")
        )


    if worker.role != "worker":

        flash(
            "Only worker accounts can be deleted.",
            "danger"
        )

        return redirect(
            url_for("workers")
        )


    # Delete worker assignments first

    Assignment.query.filter_by(
        worker_id=worker.id
    ).delete()


    # Delete worker

    db.session.delete(worker)

    db.session.commit()


    flash(
        "Worker deleted successfully.",
        "success"
    )


    return redirect(
        url_for("workers")
    )
# ============================================================
# JOBS
# ============================================================

@app.route(
    "/jobs",
    methods=["GET", "POST"]
)

@admin_required

def jobs():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()


        description = request.form.get(
            "description",
            ""
        ).strip()


        location = request.form.get(
            "location",
            ""
        ).strip()


        job = Job(

            title=title,

            description=description,

            location=location

        )


        db.session.add(job)

        db.session.commit()


        flash(
            "Job created successfully.",
            "success"
        )


        return redirect(
            url_for("jobs")
        )


    job_list = Job.query.order_by(
        Job.id.desc()
    ).all()


    workers = User.query.filter_by(
        role="worker",
        active=True
    ).all()


    content = """

    <div class="row">


    <div class="card">


    <h2>
    Create Job
    </h2>


    <form method="POST">


    <label>
    Job Title
    </label>

    <input
    name="title"
    required
    >


    <label>
    Description
    </label>

    <textarea
    name="description"
    >
    </textarea>


    <label>
    Location
    </label>

    <input
    name="location"
    >


    <button type="submit">

    Create Job

    </button>


    </form>


    </div>


    <div class="card">


    <h2>
    Jobs
    </h2>


    <table>


    <tr>

    <th>
    Job
    </th>

    <th>
    Location
    </th>

    <th>
    Assign Worker
    </th>

    </tr>


    {% for job in jobs %}


    <tr>


    <td>

    {{ job.title }}

    </td>


    <td>

    {{ job.location or "-" }}

    </td>


    <td>


    <form
    method="POST"
    action="{{ url_for('assign_worker', job_id=job.id) }}"
    >


    <select
    name="worker_id"
    required
    >


    <option value="">

    Select Worker

    </option>


    {% for worker in workers %}


    <option
    value="{{ worker.id }}"
    >

    {{ worker.name }}

    </option>


    {% endfor %}


    </select>


    <button type="submit">

    Assign

    </button>


    </form>


    </td>


    </tr>


    {% endfor %}


    </table>


    </div>


    </div>


    """


    rendered_content = render_template_string(

        content,

        jobs=job_list,

        workers=workers

    )


    return render_page(
        "Jobs",
        rendered_content
    )


# ============================================================
# ASSIGN WORKER
# ============================================================

@app.route(
    "/jobs/<int:job_id>/assign",
    methods=["POST"]
)

@admin_required

def assign_worker(job_id):

    worker_id = request.form.get(
        "worker_id"
    )


    existing = Assignment.query.filter_by(

        job_id=job_id,

        worker_id=worker_id

    ).first()


    if existing:

        flash(
            "Worker already assigned to this job.",
            "danger"
        )

        return redirect(
            url_for("jobs")
        )


    assignment = Assignment(

        job_id=job_id,

        worker_id=worker_id,

        status="Pending"

    )


    db.session.add(assignment)

    db.session.commit()


    flash(
        "Worker assigned successfully.",
        "success"
    )


    return redirect(
        url_for("jobs")
    )


# ============================================================
# UPDATE ASSIGNMENT
# ============================================================

@app.route(
    "/assignment/<int:assignment_id>/update",
    methods=["POST"]
)

@login_required

def update_assignment(assignment_id):

    assignment = db.session.get(
        Assignment,
        assignment_id
    )


    if not assignment:

        flash(
            "Assignment not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    # Worker can only update own assignment

    if session["role"] == "worker":

        if assignment.worker_id != session["user_id"]:

            flash(
                "Access denied.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )


    status = request.form.get(
        "status"
    )


    allowed_statuses = [

        "Pending",

        "In Progress",

        "Done",

        "Not Done"

    ]


    if status in allowed_statuses:

        assignment.status = status

        assignment.updated_at = datetime.utcnow()

        db.session.commit()


        flash(
            "Status updated successfully.",
            "success"
        )


    return redirect(
        url_for("dashboard")
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

with app.app_context():

    db.create_all()

    create_default_admin()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )


    app.run(

        host="0.0.0.0",

        port=port,

        debug=False

    )
