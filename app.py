
import os
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "CHANGE-ME-BEFORE-PUBLIC-DEPLOYMENT")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

db_url = os.environ.get("DATABASE_URL", "sqlite:///workers.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True)
    name=Column(String(150),nullable=False)
    username=Column(String(80),unique=True,nullable=False,index=True)
    password_hash=Column(String(255),nullable=False)
    role=Column(String(20),nullable=False,default="worker")
    active=Column(Integer,nullable=False,default=1)

class Job(Base):
    __tablename__="jobs"
    id=Column(Integer,primary_key=True)
    title=Column(String(200),nullable=False)
    description=Column(Text,nullable=False)
    priority=Column(String(20),nullable=False,default="Normal")
    due_date=Column(String(30),nullable=True)
    created_at=Column(DateTime,nullable=False)
    created_by=Column(Integer,ForeignKey("users.id"),nullable=False)
    assignments=relationship("Assignment",back_populates="job",cascade="all, delete-orphan")

class Assignment(Base):
    __tablename__="assignments"
    id=Column(Integer,primary_key=True)
    job_id=Column(Integer,ForeignKey("jobs.id"),nullable=False)
    worker_id=Column(Integer,ForeignKey("users.id"),nullable=False)
    acknowledged_at=Column(DateTime,nullable=True)
    status=Column(String(20),nullable=False,default="Pending")
    comment=Column(Text,nullable=True)
    updated_at=Column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint("job_id","worker_id",name="uq_job_worker"),)
    job=relationship("Job",back_populates="assignments")
    worker=relationship("User")

Base.metadata.create_all(engine)

def now():
    return datetime.now(timezone.utc)

def seed():
    db=SessionLocal()
    if not db.query(User).filter_by(role="admin").first():
        db.add(User(name="Administrator",username="admin",password_hash=generate_password_hash("admin123"),role="admin"))
    if not db.query(User).filter_by(username="worker1").first():
        db.add(User(name="Sample Worker",username="worker1",password_hash=generate_password_hash("1234"),role="worker"))
    db.commit(); db.close()
seed()

def current_user():
    uid=session.get("user_id")
    if not uid:return None
    db=SessionLocal(); u=db.get(User,uid); db.close()
    return u

def required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            u=current_user()
            if not u or not u.active:
                session.clear(); return redirect(url_for("login"))
            if role and u.role!=role: abort(403)
            return fn(*args,**kwargs)
        return wrapper
    return deco

@app.context_processor
def inject_user():
    return {"me": current_user()}

@app.route("/",methods=["GET"])
def home():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        db=SessionLocal()
        u=db.query(User).filter(func.lower(User.username)==request.form["username"].strip().lower()).first()
        ok=u and u.active and check_password_hash(u.password_hash,request.form["password"])
        db.close()
        if ok:
            session.clear(); session["user_id"]=u.id
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@required()
def dashboard():
    db=SessionLocal(); u=db.get(User,session["user_id"])
    if u.role=="admin":
        jobs=db.query(Job).options(joinedload(Job.assignments).joinedload(Assignment.worker)).order_by(Job.id.desc()).all()
        workers=db.query(User).filter_by(role="worker",active=1).order_by(User.name).all()
        stats={
          "jobs":len(jobs),
          "done":sum(1 for j in jobs for a in j.assignments if a.status=="Done"),
          "notdone":sum(1 for j in jobs for a in j.assignments if a.status=="Not Done"),
          "pending":sum(1 for j in jobs for a in j.assignments if a.status=="Pending"),
        }
        db.close()

today_total = 0

return render_template(
    "admin.html",
    jobs=jobs,
    workers=workers,
    stats=stats,
    today_total=today_total
)
    jobs=db.query(Assignment).options(joinedload(Assignment.job)).filter_by(worker_id=u.id).join(Job).order_by(Job.id.desc()).all()
    db.close(); return render_template("worker.html",jobs=jobs)

@app.route("/admin/jobs/create",methods=["POST"])
@required("admin")
def create_job():
    title=request.form.get("title","").strip()
    desc=request.form.get("description","").strip()
    priority=request.form.get("priority","Normal")
    due=request.form.get("due_date","").strip()
    ids=[int(x) for x in request.form.getlist("workers") if x.isdigit()]
    if not title or not desc or not ids:
        flash("Enter the job details and select at least one worker."); return redirect(url_for("dashboard"))
    db=SessionLocal()
    job=Job(title=title,description=desc,priority=priority if priority in ("Low","Normal","High","Urgent") else "Normal",due_date=due or None,created_at=now(),created_by=session["user_id"])
    db.add(job); db.flush()
    valid=db.query(User).filter(User.id.in_(ids),User.role=="worker",User.active==1).all()
    for w in valid: db.add(Assignment(job_id=job.id,worker_id=w.id))
    db.commit(); db.close(); flash("Job delivered to the selected workers."); return redirect(url_for("dashboard"))

@app.route("/worker/job/<int:aid>",methods=["POST"])
@required("worker")
def worker_update(aid):
    db=SessionLocal(); a=db.query(Assignment).filter_by(id=aid,worker_id=session["user_id"]).first()
    if not a: db.close(); abort(404)
    status=request.form.get("status","Pending")
    if status not in ("Pending","Done","Not Done"): status="Pending"
    comment=request.form.get("comment","").strip()
    t=now()
    if not a.acknowledged_at: a.acknowledged_at=t
    a.status=status; a.comment=comment; a.updated_at=t
    db.commit(); db.close(); flash("Your acknowledgment and job status were saved."); return redirect(url_for("dashboard"))

@app.route("/admin/job/<int:jid>")
@required("admin")
def job_detail(jid):
    db=SessionLocal(); job=db.query(Job).options(joinedload(Job.assignments).joinedload(Assignment.worker)).get(jid)
    if not job: db.close(); abort(404)
    db.close(); return render_template("job_detail.html",job=job)

@app.route("/admin/job/<int:jid>/archive",methods=["POST"])
@required("admin")
def archive(jid):
    db=SessionLocal(); job=db.get(Job,jid)
    if not job: db.close(); abort(404)
    if not job.assignments or not all(a.status=="Done" for a in job.assignments):
        db.close(); flash("Only jobs where every assigned worker is Done can be cleared."); return redirect(url_for("dashboard"))
    db.delete(job); db.commit(); db.close(); flash("Job cleared/archived."); return redirect(url_for("dashboard"))

@app.route("/admin/workers/create",methods=["POST"])
@required("admin")
def create_worker():
    name=request.form.get("name","").strip(); username=request.form.get("username","").strip(); pw=request.form.get("password","")
    if not name or not username or not pw: flash("Complete all worker account fields."); return redirect(url_for("dashboard"))
    db=SessionLocal()
    if db.query(User).filter(func.lower(User.username)==username.lower()).first():
        db.close(); flash("Username already exists."); return redirect(url_for("dashboard"))
    db.add(User(name=name,username=username,password_hash=generate_password_hash(pw),role="worker")); db.commit(); db.close()
    flash("Worker account created."); return redirect(url_for("dashboard"))

@app.route("/admin/worker/<int:wid>/password",methods=["POST"])
@required("admin")
def reset_password(wid):
    pw=request.form.get("password","")
    if len(pw)<4: flash("Password must be at least 4 characters."); return redirect(url_for("dashboard"))
    db=SessionLocal(); u=db.get(User,wid)
    if u and u.role=="worker": u.password_hash=generate_password_hash(pw); db.commit(); flash("Worker password reset.")
    db.close(); return redirect(url_for("dashboard"))

@app.route("/admin/worker/<int:wid>/disable",methods=["POST"])
@required("admin")
def disable(wid):
    db=SessionLocal(); u=db.get(User,wid)
    if u and u.role=="worker": u.active=0; db.commit()
    db.close(); return redirect(url_for("dashboard"))

@app.route("/admin/worker/<int:wid>/enable",methods=["POST"])
@required("admin")
def enable(wid):
    db=SessionLocal(); u=db.get(User,wid)
    if u and u.role=="worker": u.active=1; db.commit()
    db.close(); return redirect(url_for("dashboard"))

@app.route("/admin/change-password",methods=["POST"])
@required("admin")
def change_admin_password():
    pw=request.form.get("password","")
    if len(pw)<8: flash("Admin password must be at least 8 characters."); return redirect(url_for("dashboard"))
    db=SessionLocal(); u=db.get(User,session["user_id"]); u.password_hash=generate_password_hash(pw); db.commit(); db.close()
    flash("Admin password changed."); return redirect(url_for("dashboard"))

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
