
# Workforce Job Management System (WJMS)

A production-ready web application for a private business to assign work, track individual employee acknowledgment, collect Done/Not Done status and comments, and monitor all job responses from an Admin dashboard.

## Main workflow

Business Admin creates a job and selects one or more employees.

Each employee logs in using their own account.

The employee acknowledges receipt by submitting their response, selects Pending, Done, or Not Done, and can enter comments/remarks.

The Admin sees the complete job list, each assigned employee, acknowledgment time, status, last update, and comments.

A job can only be cleared/archived when every assigned employee is marked Done.

## Included

- Individual employee accounts
- Admin dashboard
- Job creation and assignment
- Multi-employee assignments
- Individual acknowledgment
- Pending / Done / Not Done
- Comments and remarks
- Automatic timestamps
- Complete Admin monitoring
- Job detail/history view
- Employee account creation
- Password reset
- Account disable/enable
- Secure password hashing
- PostgreSQL support
- Mobile-friendly interface
- Production deployment files

## Default accounts

Admin: `admin` / `admin123`

Sample employee: `worker1` / `1234`

Change the Admin password immediately after first login and disable the sample employee account after creating your real employee accounts.

## Run locally

Python 3.11+:

`pip install -r requirements.txt`

`python app.py`

Then open `http://127.0.0.1:5000`

## Online deployment

Use a persistent PostgreSQL database and configure:

- `SECRET_KEY` — a long random secret
- `DATABASE_URL` — PostgreSQL connection string
- `COOKIE_SECURE=1`

The included Dockerfile and render.yaml are deployment templates. A hosting account and database are still required to create the public Internet URL.

## Recommended next business features

The system can be expanded with:
- Employee departments/teams
- Supervisor/manager accounts
- Job priority and due dates
- Recurring jobs
- Photo proof of completed work
- Admin verification/approval
- Notifications by email/SMS/push
- Attendance/time-in and time-out
- Payroll-linked work records
- Excel/PDF reports
- Audit logs
- Dashboard charts


## Job Order assignment modes

- All Workers: the JO is visible to every active worker. The first worker to accept becomes responsible. Other workers do not need to acknowledge.
- Specific Worker(s): the JO is assigned only to selected workers, with individual responses.
- One Specific Worker: select one worker.
