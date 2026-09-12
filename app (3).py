import os
from datetime import datetime, date
from functools import wraps

from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

database_url = os.getenv("DATABASE_URL", "sqlite:///hure.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================================================
# DATABASE MODELS
# ============================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="worker")
    active = db.Column(db.Boolean, default=True)
    daily_rate = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    work_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(30), default="Present")
    hours = db.Column(db.Numeric(6, 2), default=8)
    overtime_hours = db.Column(db.Numeric(6, 2), default=0)
    worker = db.relationship("User", backref="attendance")

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    remarks = db.Column(db.Text, default="")
    job = db.relationship("Job", backref="assignments")
    worker = db.relationship("User", backref="assignments")

class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    days_worked = db.Column(db.Numeric(8, 2), default=0)
    basic_pay = db.Column(db.Numeric(12, 2), default=0)
    overtime_pay = db.Column(db.Numeric(12, 2), default=0)
    allowances = db.Column(db.Numeric(12, 2), default=0)
    deductions = db.Column(db.Numeric(12, 2), default=0)
    net_pay = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    worker = db.relationship("User", backref="payrolls")

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(100), default="")
    address = db.Column(db.String(255), default="")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    barcode = db.Column(db.String(80), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    cost_price = db.Column(db.Numeric(12, 2), default=0)
    selling_price = db.Column(db.Numeric(12, 2), default=0)
    stock = db.Column(db.Numeric(12, 2), default=0)
    reorder_level = db.Column(db.Numeric(12, 2), default=5)
    active = db.Column(db.Boolean, default=True)
    category = db.relationship("Category", backref="products")
    supplier = db.relationship("Supplier", backref="products")

class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    movement_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    reference = db.Column(db.String(120), default="")
    notes = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship("Product", backref="stock_movements")

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(100), default="")
    address = db.Column(db.String(255), default="")

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    discount = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
    payment = db.Column(db.Numeric(12, 2), default=0)
    change = db.Column(db.Numeric(12, 2), default=0)
    payment_method = db.Column(db.String(30), default="Cash")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship("Customer", backref="sales")

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    sale = db.relationship("Sale", backref="items")
    product = db.relationship("Product")

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    status = db.Column(db.String(30), default="Pending")
    delivery_address = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    total = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship("Customer", backref="orders")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    order = db.relationship("Order", backref="items")
    product = db.relationship("Product")

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_no = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    driver = db.Column(db.String(150), default="")
    vehicle = db.Column(db.String(150), default="")
    status = db.Column(db.String(30), default="For Delivery")
    delivered_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship("Order", backref="deliveries")
    customer = db.relationship("Customer", backref="deliveries")


# ============================================================
# HELPERS
# ============================================================

def money(v):
    return f"{float(v or 0):,.2f}"

def next_number(prefix, model):
    count = model.query.count() + 1
    return f"{prefix}-{datetime.now():%Y%m%d}-{count:05d}"

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Administrator access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapped

BASE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title or 'Integrated HURE Management System' }}</title>
<style>
*{box-sizing:border-box} body{margin:0;font-family:Arial,sans-serif;background:#f1f3f6;color:#263444}
nav{background:#243142;color:#fff;padding:15px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
nav b{font-size:19px;margin-right:auto} nav a{color:#fff;text-decoration:none;font-size:14px}
.container{max-width:1400px;margin:auto;padding:28px 20px}.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 10px #0001}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}.stat{background:#fff;padding:18px;border-radius:10px;box-shadow:0 2px 8px #0001}.stat small{color:#657}.stat strong{display:block;font-size:26px;margin-top:8px}
input,select,textarea{width:100%;padding:10px;border:1px solid #ccd3dd;border-radius:7px;margin:5px 0 12px}button,.btn{background:#2563b8;color:#fff;border:0;border-radius:7px;padding:10px 15px;text-decoration:none;cursor:pointer;display:inline-block}
.btn.red{background:#c0392b}.btn.green{background:#198754}.btn.gray{background:#65727f}.btn.orange{background:#d97706}
table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid #e5e7eb;text-align:left}th{background:#f3f4f6}.flash{padding:12px;margin:12px 0;border-radius:7px}.success{background:#d1fae5}.danger{background:#fee2e2}.warning{background:#fef3c7}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}.right{text-align:right}.muted{color:#667085}.badge{padding:4px 8px;border-radius:99px;background:#e8eef7;font-size:12px}
@media print{nav,.no-print,.flash{display:none!important}.container{padding:0}.card{box-shadow:none;border:0}}
</style>
</head>
<body>
{% if session.get('user_id') %}
<nav>
<b>INTEGRATED HURE MANAGEMENT SYSTEM</b>
<a href="{{ url_for('dashboard') }}">Dashboard</a>
<a href="{{ url_for('pos') }}">POS</a>
<a href="{{ url_for('products') }}">Inventory</a>
<a href="{{ url_for('workers') }}">Workforce</a>
<a href="{{ url_for('payroll') }}">Payroll</a>
<a href="{{ url_for('orders') }}">Orders</a>
<a href="{{ url_for('deliveries') }}">Delivery</a>
<a href="{{ url_for('reports') }}">Reports</a>
<a href="{{ url_for('logout') }}">Logout</a>
</nav>
{% endif %}
<div class="container">
{% for category,message in get_flashed_messages(with_categories=true) %}<div class="flash {{ category }}">{{ message }}</div>{% endfor %}
{{ body|safe }}
</div>
</body></html>
"""

def page(body, **ctx):
    return render_template_string(BASE, body=render_template_string(body, **ctx), money=money, **ctx)


# ============================================================
# AUTH
# ============================================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, active=True).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["role"] = user.role
            session["full_name"] = user.full_name
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return page("""
    <div style="max-width:420px;margin:90px auto" class="card">
      <h1>HURE MANAGEMENT SYSTEM</h1><p class="muted">Login to continue</p>
      <form method="post">
      <label>Username</label><input name="username" required>
      <label>Password</label><input type="password" name="password" required>
      <button>Login</button></form>
    </div>""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():
    today_sales = db.session.query(db.func.coalesce(db.func.sum(Sale.total),0)).filter(db.func.date(Sale.created_at)==date.today()).scalar()
    low_stock = Product.query.filter(Product.stock <= Product.reorder_level).count()
    body = """
    <h1>Welcome, {{ session.get('full_name','User') }}</h1>
    <div class="grid">
      <div class="stat"><small>Today's Sales</small><strong>₱{{ money(today_sales) }}</strong></div>
      <div class="stat"><small>Products</small><strong>{{ products }}</strong></div>
      <div class="stat"><small>Active Workers</small><strong>{{ workers }}</strong></div>
      <div class="stat"><small>Pending Jobs</small><strong>{{ pending_jobs }}</strong></div>
      <div class="stat"><small>Low Stock</small><strong>{{ low_stock }}</strong></div>
      <div class="stat"><small>Payroll Records</small><strong>{{ payroll_count }}</strong></div>
    </div>
    <div class="row" style="margin-top:20px">
      <div class="card"><h2>Quick Actions</h2>
      <a class="btn" href="{{ url_for('pos') }}">New POS Sale</a>
      <a class="btn green" href="{{ url_for('products') }}">Add Product</a>
      <a class="btn orange" href="{{ url_for('workers') }}">Manage Workforce</a>
      <a class="btn gray" href="{{ url_for('orders') }}">New Order</a></div>
      <div class="card"><h2>Recent Sales</h2>
      <table><tr><th>Receipt</th><th>Total</th><th>Print</th></tr>
      {% for s in recent_sales %}<tr><td>{{ s.receipt_no }}</td><td>₱{{ money(s.total) }}</td><td><a href="{{ url_for('receipt',sale_id=s.id) }}">Receipt</a></td></tr>{% endfor %}
      </table></div>
    </div>
    """
    return page(body, today_sales=today_sales, products=Product.query.count(),
                workers=User.query.filter_by(role="worker",active=True).count(),
                pending_jobs=Job.query.filter_by(status="Pending").count(),
                low_stock=low_stock, payroll_count=Payroll.query.count(),
                recent_sales=Sale.query.order_by(Sale.id.desc()).limit(5).all())


# ============================================================
# WORKFORCE
# ============================================================

@app.route("/workers", methods=["GET", "POST"])
@login_required
@admin_required
def workers():
    if request.method == "POST":
        full_name=request.form["full_name"].strip()
        username=request.form["username"].strip()
        password=request.form["password"]
        daily_rate=float(request.form.get("daily_rate") or 0)
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
        elif not full_name:
            flash("Full name is required.", "danger")
        else:
            db.session.add(User(full_name=full_name,username=username,password_hash=generate_password_hash(password),role="worker",daily_rate=daily_rate))
            db.session.commit(); flash("Worker created successfully.","success")
            return redirect(url_for("workers"))
    return page("""
    <h1>Workforce Management</h1><div class="row">
    <div class="card"><h2>Add Worker</h2><form method="post">
    <label>Full Name</label><input name="full_name" required>
    <label>Username</label><input name="username" required>
    <label>Password</label><input name="password" type="password" required>
    <label>Daily Rate</label><input name="daily_rate" type="number" step="0.01" value="0">
    <button>Create Worker</button></form></div>
    <div class="card"><h2>Workers</h2><table><tr><th>Name</th><th>Username</th><th>Daily Rate</th><th>Status</th><th>Action</th></tr>
    {% for w in workers %}<tr><td>{{w.full_name}}</td><td>{{w.username}}</td><td>₱{{money(w.daily_rate)}}</td><td>{{'Active' if w.active else 'Inactive'}}</td>
    <td><a class="btn gray" href="{{url_for('edit_worker',worker_id=w.id)}}">Edit</a>
    <form method="post" action="{{url_for('delete_worker',worker_id=w.id)}}" style="display:inline" onsubmit="return confirm('Delete this worker?')"><button class="btn red">Delete</button></form></td></tr>{% endfor %}
    </table></div></div>""", workers=User.query.filter_by(role="worker").order_by(User.full_name).all())

@app.route("/workers/<int:worker_id>/edit", methods=["GET","POST"])
@login_required
@admin_required
def edit_worker(worker_id):
    w=db.session.get(User,worker_id) or abort(404)
    if request.method=="POST":
        w.full_name=request.form["full_name"]; w.username=request.form["username"]; w.daily_rate=float(request.form.get("daily_rate") or 0)
        if request.form.get("password"): w.password_hash=generate_password_hash(request.form["password"])
        db.session.commit(); flash("Worker updated.","success"); return redirect(url_for("workers"))
    return page("""<div class="card" style="max-width:600px"><h1>Edit Worker</h1><form method="post">
    <label>Full Name</label><input name="full_name" value="{{w.full_name}}">
    <label>Username</label><input name="username" value="{{w.username}}">
    <label>New Password (optional)</label><input type="password" name="password">
    <label>Daily Rate</label><input type="number" step="0.01" name="daily_rate" value="{{w.daily_rate}}">
    <button>Save Changes</button></form></div>""",w=w)

@app.route("/workers/<int:worker_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_worker(worker_id):
    w=db.session.get(User,worker_id) or abort(404)
    if w.role!="worker": abort(403)
    Attendance.query.filter_by(worker_id=w.id).delete()
    Assignment.query.filter_by(worker_id=w.id).delete()
    Payroll.query.filter_by(worker_id=w.id).delete()
    db.session.delete(w); db.session.commit()
    flash("Worker deleted successfully.","success")
    return redirect(url_for("workers"))

@app.route("/attendance", methods=["GET","POST"])
@login_required
@admin_required
def attendance():
    if request.method=="POST":
        db.session.add(Attendance(worker_id=int(request.form["worker_id"]),work_date=datetime.strptime(request.form["work_date"],"%Y-%m-%d").date(),
                                  status=request.form["status"],hours=float(request.form.get("hours") or 0),overtime_hours=float(request.form.get("overtime_hours") or 0)))
        db.session.commit(); flash("Attendance saved.","success"); return redirect(url_for("attendance"))
    return page("""<h1>Attendance</h1><div class="row"><div class="card"><form method="post">
    <label>Worker</label><select name="worker_id">{% for w in workers %}<option value="{{w.id}}">{{w.full_name}}</option>{% endfor %}</select>
    <label>Date</label><input type="date" name="work_date" value="{{today}}">
    <label>Status</label><select name="status"><option>Present</option><option>Absent</option><option>Half Day</option></select>
    <label>Hours</label><input name="hours" type="number" step="0.5" value="8">
    <label>Overtime Hours</label><input name="overtime_hours" type="number" step="0.5" value="0"><button>Save</button></form></div>
    <div class="card"><table><tr><th>Date</th><th>Worker</th><th>Status</th><th>Hours</th><th>OT</th></tr>{% for a in records %}<tr><td>{{a.work_date}}</td><td>{{a.worker.full_name}}</td><td>{{a.status}}</td><td>{{a.hours}}</td><td>{{a.overtime_hours}}</td></tr>{% endfor %}</table></div></div>""",
    workers=User.query.filter_by(role="worker",active=True).all(),records=Attendance.query.order_by(Attendance.work_date.desc()).limit(100).all(),today=date.today().isoformat())

@app.route("/jobs", methods=["GET","POST"])
@login_required
@admin_required
def jobs():
    workers=User.query.filter_by(role="worker",active=True).all()
    if request.method=="POST":
        j=Job(title=request.form["title"],location=request.form.get("location",""),description=request.form.get("description",""))
        db.session.add(j); db.session.flush()
        for wid in request.form.getlist("worker_ids"):
            db.session.add(Assignment(job_id=j.id,worker_id=int(wid)))
        db.session.commit(); flash("Job created and assigned.","success"); return redirect(url_for("jobs"))
    return page("""<h1>Jobs</h1><div class="row"><div class="card"><h2>Create Job</h2><form method="post">
    <label>Job Title</label><input name="title" required><label>Location</label><input name="location">
    <label>Description</label><textarea name="description"></textarea><label>Assign Workers</label>
    {% for w in workers %}<label><input style="width:auto" type="checkbox" name="worker_ids" value="{{w.id}}"> {{w.full_name}}</label><br>{% endfor %}
    <br><button>Create Job</button></form></div>
    <div class="card"><table><tr><th>Job</th><th>Location</th><th>Status</th><th>Workers</th></tr>{% for j in jobs %}<tr><td>{{j.title}}</td><td>{{j.location}}</td><td>{{j.status}}</td><td>{% for a in j.assignments %}{{a.worker.full_name}} ({{a.status}})<br>{% endfor %}</td></tr>{% endfor %}</table></div></div>""",workers=workers,jobs=Job.query.order_by(Job.id.desc()).all())


# ============================================================
# PAYROLL
# ============================================================

@app.route("/payroll", methods=["GET","POST"])
@login_required
@admin_required
def payroll():
    workers=User.query.filter_by(role="worker",active=True).all()
    if request.method=="POST":
        wid=int(request.form["worker_id"]); start=datetime.strptime(request.form["period_start"],"%Y-%m-%d").date(); end=datetime.strptime(request.form["period_end"],"%Y-%m-%d").date()
        w=db.session.get(User,wid)
        present=Attendance.query.filter(Attendance.worker_id==wid,Attendance.work_date>=start,Attendance.work_date<=end,Attendance.status.in_(["Present","Half Day"])).all()
        days=sum(0.5 if a.status=="Half Day" else 1 for a in present)
        ot=sum(float(a.overtime_hours or 0) for a in present)
        basic=days*float(w.daily_rate or 0); otpay=ot*(float(w.daily_rate or 0)/8*1.25)
        allow=float(request.form.get("allowances") or 0); deduct=float(request.form.get("deductions") or 0)
        net=basic+otpay+allow-deduct
        p=Payroll(worker_id=wid,period_start=start,period_end=end,days_worked=days,basic_pay=basic,overtime_pay=otpay,allowances=allow,deductions=deduct,net_pay=net)
        db.session.add(p);db.session.commit();flash("Payroll generated.","success");return redirect(url_for("payslip",payroll_id=p.id))
    return page("""<h1>Payroll</h1><div class="row"><div class="card"><h2>Generate Payroll</h2><form method="post">
    <label>Worker</label><select name="worker_id">{% for w in workers %}<option value="{{w.id}}">{{w.full_name}} - ₱{{money(w.daily_rate)}}/day</option>{% endfor %}</select>
    <label>Period Start</label><input type="date" name="period_start" required><label>Period End</label><input type="date" name="period_end" required>
    <label>Allowances</label><input type="number" step="0.01" name="allowances" value="0"><label>Deductions / Cash Advance / Loan</label><input type="number" step="0.01" name="deductions" value="0"><button>Generate</button></form></div>
    <div class="card"><table><tr><th>Worker</th><th>Period</th><th>Net Pay</th><th>Print</th></tr>{% for p in records %}<tr><td>{{p.worker.full_name}}</td><td>{{p.period_start}} to {{p.period_end}}</td><td>₱{{money(p.net_pay)}}</td><td><a href="{{url_for('payslip',payroll_id=p.id)}}">Payslip</a></td></tr>{% endfor %}</table></div></div>""",workers=workers,records=Payroll.query.order_by(Payroll.id.desc()).all())

@app.route("/payslip/<int:payroll_id>")
@login_required
def payslip(payroll_id):
    p=db.session.get(Payroll,payroll_id) or abort(404)
    return page("""<div class="card" style="max-width:700px;margin:auto"><div class="right no-print"><button onclick="window.print()">Print Payslip</button></div><h1>PAYSLIP</h1><h2>{{p.worker.full_name}}</h2>
    <p>Period: {{p.period_start}} to {{p.period_end}}</p><table>
    <tr><td>Days Worked</td><td>{{p.days_worked}}</td></tr><tr><td>Basic Pay</td><td>₱{{money(p.basic_pay)}}</td></tr><tr><td>Overtime Pay</td><td>₱{{money(p.overtime_pay)}}</td></tr><tr><td>Allowances</td><td>₱{{money(p.allowances)}}</td></tr><tr><td>Deductions</td><td>₱{{money(p.deductions)}}</td></tr><tr><th>NET PAY</th><th>₱{{money(p.net_pay)}}</th></tr></table><br><p>Received by: __________________________</p></div>""",p=p)


# ============================================================
# INVENTORY
# ============================================================

@app.route("/products", methods=["GET","POST"])
@login_required
def products():
    if request.method=="POST":
        action=request.form.get("action")
        if action=="category":
            name=request.form["name"].strip()
            if name and not Category.query.filter_by(name=name).first(): db.session.add(Category(name=name));db.session.commit()
            flash("Category saved.","success")
        elif action=="supplier":
            db.session.add(Supplier(name=request.form["name"],contact=request.form.get("contact",""),address=request.form.get("address","")));db.session.commit();flash("Supplier saved.","success")
        elif action=="product":
            sku=request.form["sku"].strip()
            if Product.query.filter_by(sku=sku).first(): flash("SKU already exists.","danger")
            else:
                p=Product(name=request.form["name"],sku=sku,barcode=request.form.get("barcode",""),category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
                supplier_id=int(request.form["supplier_id"]) if request.form.get("supplier_id") else None,cost_price=float(request.form.get("cost_price") or 0),selling_price=float(request.form.get("selling_price") or 0),stock=float(request.form.get("stock") or 0),reorder_level=float(request.form.get("reorder_level") or 5))
                db.session.add(p);db.session.flush()
                if float(p.stock)>0: db.session.add(StockMovement(product_id=p.id,movement_type="Opening Stock",quantity=p.stock,reference="INITIAL"))
                db.session.commit();flash("Product added.","success")
        elif action=="stockin":
            p=db.session.get(Product,int(request.form["product_id"]));qty=float(request.form["quantity"]);p.stock=float(p.stock)+qty
            db.session.add(StockMovement(product_id=p.id,movement_type="Stock In",quantity=qty,reference=request.form.get("reference",""),notes=request.form.get("notes","")));db.session.commit();flash("Stock updated.","success")
        return redirect(url_for("products"))
    return page("""<h1>Inventory</h1><div class="row">
    <div class="card"><h2>Add Product</h2><form method="post"><input type="hidden" name="action" value="product">
    <label>Product Name</label><input name="name" required><label>SKU</label><input name="sku" required><label>Barcode</label><input name="barcode">
    <label>Category</label><select name="category_id"><option value="">-- Select --</option>{% for c in categories %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select>
    <label>Supplier</label><select name="supplier_id"><option value="">-- Select --</option>{% for s in suppliers %}<option value="{{s.id}}">{{s.name}}</option>{% endfor %}</select>
    <label>Cost Price</label><input type="number" step="0.01" name="cost_price"><label>Selling Price</label><input type="number" step="0.01" name="selling_price" required>
    <label>Opening Stock</label><input type="number" step="0.01" name="stock" value="0"><label>Reorder Level</label><input type="number" step="0.01" name="reorder_level" value="5"><button>Add Product</button></form></div>
    <div class="card"><h2>Categories / Suppliers</h2><form method="post"><input type="hidden" name="action" value="category"><input name="name" placeholder="New Category"><button>Save Category</button></form>
    <hr><form method="post"><input type="hidden" name="action" value="supplier"><input name="name" placeholder="Supplier Name" required><input name="contact" placeholder="Contact"><input name="address" placeholder="Address"><button>Save Supplier</button></form></div></div>
    <div class="card"><h2>Stock In</h2><form method="post" class="row"><input type="hidden" name="action" value="stockin"><div><select name="product_id">{% for p in products %}<option value="{{p.id}}">{{p.name}} ({{p.stock}})</option>{% endfor %}</select></div><div><input type="number" step="0.01" name="quantity" placeholder="Quantity" required></div><div><input name="reference" placeholder="Reference / DR"></div><div><button>Stock In</button></div></form></div>
    <div class="card"><h2>Products</h2><table><tr><th>SKU</th><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th></tr>{% for p in products %}<tr><td>{{p.sku}}</td><td>{{p.name}}</td><td>{{p.category.name if p.category else ''}}</td><td>₱{{money(p.selling_price)}}</td><td>{{p.stock}}</td><td>{% if p.stock<=p.reorder_level %}<span class="badge">LOW STOCK</span>{% else %}OK{% endif %}</td></tr>{% endfor %}</table></div>""",
    products=Product.query.order_by(Product.name).all(),categories=Category.query.order_by(Category.name).all(),suppliers=Supplier.query.order_by(Supplier.name).all())


# ============================================================
# POS + PRINTABLE RECEIPT
# ============================================================

@app.route("/pos", methods=["GET","POST"])
@login_required
def pos():
    products=Product.query.filter_by(active=True).order_by(Product.name).all()
    customers=Customer.query.order_by(Customer.name).all()
    if request.method=="POST":
        customer_id=request.form.get("customer_id") or None
        discount=float(request.form.get("discount") or 0); payment=float(request.form.get("payment") or 0)
        product_ids=request.form.getlist("product_id"); quantities=request.form.getlist("quantity")
        items=[];subtotal=0
        for pid,qty in zip(product_ids,quantities):
            if not pid or float(qty or 0)<=0: continue
            p=db.session.get(Product,int(pid)); q=float(qty)
            if not p or float(p.stock)<q:
                flash(f"Insufficient stock for {p.name if p else 'product'}.","danger"); return redirect(url_for("pos"))
            total=q*float(p.selling_price);subtotal+=total;items.append((p,q,total))
        if not items: flash("Add at least one item.","danger");return redirect(url_for("pos"))
        total=max(0,subtotal-discount)
        if payment<total: flash("Payment is insufficient.","danger");return redirect(url_for("pos"))
        sale=Sale(receipt_no=next_number("OR",Sale),customer_id=int(customer_id) if customer_id else None,subtotal=subtotal,discount=discount,total=total,payment=payment,change=payment-total,payment_method=request.form.get("payment_method","Cash"))
        db.session.add(sale);db.session.flush()
        for p,q,total_item in items:
            p.stock=float(p.stock)-q
            db.session.add(SaleItem(sale_id=sale.id,product_id=p.id,product_name=p.name,quantity=q,price=p.selling_price,total=total_item))
            db.session.add(StockMovement(product_id=p.id,movement_type="Sale",quantity=-q,reference=sale.receipt_no))
        db.session.commit()
        return redirect(url_for("receipt",sale_id=sale.id))
    return page("""<h1>Hardware POS</h1><div class="row"><div class="card"><h2>New Sale</h2><form method="post">
    <label>Customer</label><select name="customer_id"><option value="">Walk-in Customer</option>{% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select>
    <div id="items"><div class="item row"><div><label>Product</label><select name="product_id"><option value="">-- Select Product --</option>{% for p in products %}<option value="{{p.id}}">{{p.name}} | ₱{{money(p.selling_price)}} | Stock: {{p.stock}}</option>{% endfor %}</select></div><div><label>Quantity</label><input name="quantity" type="number" step="0.01" value="1"></div></div></div>
    <button type="button" class="btn gray no-print" onclick="addItem()">+ Add Item</button><br><br>
    <label>Discount</label><input type="number" step="0.01" name="discount" value="0"><label>Payment</label><input type="number" step="0.01" name="payment" required>
    <label>Payment Method</label><select name="payment_method"><option>Cash</option><option>GCash</option><option>Bank Transfer</option></select><button>Complete Sale & Print Receipt</button></form></div>
    <div class="card"><h2>Add Customer</h2><form method="post" action="{{url_for('add_customer')}}"><input name="name" placeholder="Customer Name" required><input name="contact" placeholder="Contact"><textarea name="address" placeholder="Address"></textarea><button class="btn green">Save Customer</button></form>
    <h2>Recent Sales</h2><table><tr><th>Receipt</th><th>Total</th><th></th></tr>{% for s in sales %}<tr><td>{{s.receipt_no}}</td><td>₱{{money(s.total)}}</td><td><a href="{{url_for('receipt',sale_id=s.id)}}">Print</a></td></tr>{% endfor %}</table></div></div>
    <script>function addItem(){document.getElementById('items').insertAdjacentHTML('beforeend',document.querySelector('.item').outerHTML)}</script>""",products=products,customers=customers,sales=Sale.query.order_by(Sale.id.desc()).limit(10).all())

@app.route("/customers/add", methods=["POST"])
@login_required
def add_customer():
    db.session.add(Customer(name=request.form["name"],contact=request.form.get("contact",""),address=request.form.get("address","")));db.session.commit()
    flash("Customer saved.","success");return redirect(request.referrer or url_for("pos"))

@app.route("/receipt/<int:sale_id>")
@login_required
def receipt(sale_id):
    s=db.session.get(Sale,sale_id) or abort(404)
    return page("""<div class="card" style="max-width:700px;margin:auto"><div class="right no-print"><button onclick="window.print()">🖨 Print Receipt</button></div>
    <div style="text-align:center"><h1>HURE HARDWARE</h1><b>OFFICIAL SALES RECEIPT</b><p>Receipt No: {{s.receipt_no}}<br>{{s.created_at.strftime('%Y-%m-%d %I:%M %p')}}</p></div>
    <p>Customer: {{s.customer.name if s.customer else 'Walk-in Customer'}}</p><table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr>{% for i in s.items %}<tr><td>{{i.product_name}}</td><td>{{i.quantity}}</td><td>₱{{money(i.price)}}</td><td>₱{{money(i.total)}}</td></tr>{% endfor %}
    <tr><td colspan="3">Subtotal</td><td>₱{{money(s.subtotal)}}</td></tr><tr><td colspan="3">Discount</td><td>₱{{money(s.discount)}}</td></tr><tr><th colspan="3">TOTAL</th><th>₱{{money(s.total)}}</th></tr><tr><td colspan="3">Payment</td><td>₱{{money(s.payment)}}</td></tr><tr><td colspan="3">Change</td><td>₱{{money(s.change)}}</td></tr></table>
    <p style="text-align:center">Thank you for your purchase!</p></div>""",s=s)


# ============================================================
# ORDERS + DELIVERY RECEIPT
# ============================================================

@app.route("/orders", methods=["GET","POST"])
@login_required
def orders():
    products=Product.query.filter_by(active=True).order_by(Product.name).all();customers=Customer.query.order_by(Customer.name).all()
    if request.method=="POST":
        cid=request.form.get("customer_id") or None
        order=Order(order_no=next_number("SO",Order),customer_id=int(cid) if cid else None,delivery_address=request.form.get("delivery_address",""),notes=request.form.get("notes",""))
        db.session.add(order);db.session.flush();total=0
        for pid,qty in zip(request.form.getlist("product_id"),request.form.getlist("quantity")):
            if not pid or float(qty or 0)<=0:continue
            p=db.session.get(Product,int(pid));q=float(qty);line=q*float(p.selling_price);total+=line
            db.session.add(OrderItem(order_id=order.id,product_id=p.id,product_name=p.name,quantity=q,price=p.selling_price,total=line))
        order.total=total;db.session.commit();flash("Sales order created.","success");return redirect(url_for("order_receipt",order_id=order.id))
    return page("""<h1>Customer Orders</h1><div class="row"><div class="card"><h2>New Order</h2><form method="post">
    <label>Customer</label><select name="customer_id"><option value="">Walk-in / New</option>{% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}</select><label>Delivery Address</label><textarea name="delivery_address"></textarea>
    <div id="orderitems"><div class="orderitem row"><div><select name="product_id"><option value="">Product</option>{% for p in products %}<option value="{{p.id}}">{{p.name}} - ₱{{money(p.selling_price)}}</option>{% endfor %}</select></div><div><input name="quantity" type="number" step="0.01" value="1"></div></div></div>
    <button type="button" class="btn gray" onclick="addOrderItem()">+ Add Item</button><br><br><label>Notes</label><textarea name="notes"></textarea><button>Create Order</button></form></div>
    <div class="card"><h2>Orders</h2><table><tr><th>Order</th><th>Customer</th><th>Total</th><th>Status</th><th></th></tr>{% for o in orders %}<tr><td>{{o.order_no}}</td><td>{{o.customer.name if o.customer else 'Walk-in'}}</td><td>₱{{money(o.total)}}</td><td>{{o.status}}</td><td><a href="{{url_for('order_receipt',order_id=o.id)}}">Print</a> | <a href="{{url_for('create_delivery',order_id=o.id)}}">Delivery</a></td></tr>{% endfor %}</table></div></div>
    <script>function addOrderItem(){document.getElementById('orderitems').insertAdjacentHTML('beforeend',document.querySelector('.orderitem').outerHTML)}</script>""",products=products,customers=customers,orders=Order.query.order_by(Order.id.desc()).all())

@app.route("/order/<int:order_id>/receipt")
@login_required
def order_receipt(order_id):
    o=db.session.get(Order,order_id) or abort(404)
    return page("""<div class="card" style="max-width:700px;margin:auto"><div class="right no-print"><button onclick="window.print()">Print Order</button></div><h1 style="text-align:center">HURE HARDWARE</h1><h2 style="text-align:center">SALES ORDER</h2>
    <p><b>Order No:</b> {{o.order_no}}<br><b>Date:</b> {{o.created_at.strftime('%Y-%m-%d')}}<br><b>Customer:</b> {{o.customer.name if o.customer else 'Walk-in'}}<br><b>Delivery Address:</b> {{o.delivery_address}}</p>
    <table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr>{% for i in o.items %}<tr><td>{{i.product_name}}</td><td>{{i.quantity}}</td><td>₱{{money(i.price)}}</td><td>₱{{money(i.total)}}</td></tr>{% endfor %}<tr><th colspan="3">TOTAL</th><th>₱{{money(o.total)}}</th></tr></table><br><div class="row"><p>Prepared by: __________________</p><p>Approved by: __________________</p></div></div>""",o=o)

@app.route("/order/<int:order_id>/delivery", methods=["GET","POST"])
@login_required
def create_delivery(order_id):
    o=db.session.get(Order,order_id) or abort(404)
    if request.method=="POST":
        d=Delivery(delivery_no=next_number("DR",Delivery),order_id=o.id,customer_id=o.customer_id,driver=request.form.get("driver",""),vehicle=request.form.get("vehicle",""),status="For Delivery")
        o.status="For Delivery";db.session.add(d);db.session.commit();return redirect(url_for("delivery_receipt",delivery_id=d.id))
    return page("""<div class="card" style="max-width:600px"><h1>Create Delivery</h1><h2>{{o.order_no}}</h2><p>Customer: {{o.customer.name if o.customer else 'Walk-in'}}</p><form method="post"><label>Driver / Delivery Personnel</label><input name="driver"><label>Vehicle</label><input name="vehicle"><button>Create Delivery Receipt</button></form></div>""",o=o)

@app.route("/deliveries")
@login_required
def deliveries():
    return page("""<h1>Deliveries</h1><div class="card"><table><tr><th>Delivery No</th><th>Order</th><th>Customer</th><th>Driver</th><th>Status</th><th>Print</th></tr>{% for d in deliveries %}<tr><td>{{d.delivery_no}}</td><td>{{d.order.order_no if d.order else ''}}</td><td>{{d.customer.name if d.customer else ''}}</td><td>{{d.driver}}</td><td>{{d.status}}</td><td><a href="{{url_for('delivery_receipt',delivery_id=d.id)}}">Delivery Receipt</a></td></tr>{% endfor %}</table></div>""",deliveries=Delivery.query.order_by(Delivery.id.desc()).all())

@app.route("/delivery/<int:delivery_id>/receipt")
@login_required
def delivery_receipt(delivery_id):
    d=db.session.get(Delivery,delivery_id) or abort(404)
    return page("""<div class="card" style="max-width:700px;margin:auto"><div class="right no-print"><button onclick="window.print()">🖨 Print Delivery Receipt</button></div>
    <h1 style="text-align:center">HURE HARDWARE</h1><h2 style="text-align:center">DELIVERY RECEIPT</h2><p><b>DR No:</b> {{d.delivery_no}}<br><b>Order No:</b> {{d.order.order_no if d.order else ''}}<br><b>Customer:</b> {{d.customer.name if d.customer else ''}}<br><b>Address:</b> {{d.order.delivery_address if d.order else ''}}<br><b>Driver:</b> {{d.driver}}<br><b>Vehicle:</b> {{d.vehicle}}</p>
    {% if d.order %}<table><tr><th>Item</th><th>Quantity</th></tr>{% for i in d.order.items %}<tr><td>{{i.product_name}}</td><td>{{i.quantity}}</td></tr>{% endfor %}</table>{% endif %}
    <br><div class="row"><p>Prepared by:<br><br>______________________</p><p>Delivered by:<br><br>______________________</p><p>Received by:<br><br>______________________</p></div></div>""",d=d)


# ============================================================
# REPORTS
# ============================================================

@app.route("/reports")
@login_required
@admin_required
def reports():
    total_sales=db.session.query(db.func.coalesce(db.func.sum(Sale.total),0)).scalar()
    total_inventory=db.session.query(db.func.coalesce(db.func.sum(Product.stock*Product.cost_price),0)).scalar()
    payroll_total=db.session.query(db.func.coalesce(db.func.sum(Payroll.net_pay),0)).scalar()
    return page("""<h1>Reports</h1><div class="grid"><div class="stat"><small>Total Sales</small><strong>₱{{money(total_sales)}}</strong></div><div class="stat"><small>Inventory Value</small><strong>₱{{money(total_inventory)}}</strong></div><div class="stat"><small>Total Payroll</small><strong>₱{{money(payroll_total)}}</strong></div><div class="stat"><small>Completed Sales</small><strong>{{sales}}</strong></div></div>
    <div class="card"><h2>Low Stock Report</h2><table><tr><th>Product</th><th>Stock</th><th>Reorder Level</th></tr>{% for p in low %}<tr><td>{{p.name}}</td><td>{{p.stock}}</td><td>{{p.reorder_level}}</td></tr>{% endfor %}</table></div>""",total_sales=total_sales,total_inventory=total_inventory,payroll_total=payroll_total,sales=Sale.query.count(),low=Product.query.filter(Product.stock<=Product.reorder_level).all())


# ============================================================
# INITIAL SETUP
# ============================================================

def initialize():
    with app.app_context():
        db.create_all()
        admin_username=os.getenv("ADMIN_USERNAME","admin")
        admin_password=os.getenv("ADMIN_PASSWORD","Admin123!")
        admin=User.query.filter_by(username=admin_username).first()
        if not admin:
            db.session.add(User(full_name="System Administrator",username=admin_username,password_hash=generate_password_hash(admin_password),role="admin"))
            db.session.commit()

initialize()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
