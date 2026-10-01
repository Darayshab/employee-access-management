import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

def log_event(cursor, action, performed_by="System"):
    """Helper function to record security audit logs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO audit_logs (action, performed_by, timestamp)
        VALUES (?, ?, ?)
    """, (action, performed_by, timestamp))

def init_db():
    conn = sqlite3.connect("employees.db")
    cursor = conn.cursor()
    
    # 1. EMPLOYEES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department TEXT NOT NULL,
            job_title TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    """)

    # 2. ROLES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL
        )
    """)

    default_roles = [
        ('Standard Employee', 'Basic access to view directory and request access'),
        ('Security Analyst', 'Can view audit logs and security metrics'),
        ('IT Administrator', 'Full access to manage employees and grant permissions')
    ]
    cursor.executemany("INSERT OR IGNORE INTO roles (role_name, description) VALUES (?, ?)", default_roles)

    # 3. EMPLOYEE_ROLES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_roles (
            employee_id TEXT NOT NULL,
            role_name TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id),
            FOREIGN KEY (role_name) REFERENCES roles (role_name)
        )
    """)

    # 4. ACCESS_REQUESTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            system_name TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        )
    """)

    # 5. AUDIT_LOGS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    conn = sqlite3.connect("employees.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT employee_id, name, email, department, job_title, status FROM employees")
    employees = cursor.fetchall()
    
    cursor.execute("SELECT role_name, description FROM roles")
    roles = cursor.fetchall()

    cursor.execute("""
        SELECT ar.id, ar.employee_id, e.name, ar.system_name, ar.reason, ar.status 
        FROM access_requests ar
        JOIN employees e ON ar.employee_id = e.employee_id
    """)
    access_requests = cursor.fetchall()

    cursor.execute("SELECT action, performed_by, timestamp FROM audit_logs ORDER BY id DESC LIMIT 10")
    audit_logs = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM employees")
    total_employees = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'Pending'")
    pending_approvals = cursor.fetchone()[0]
    
    conn.close()

    return render_template(
        "index.html", 
        employees=employees, 
        roles=roles, 
        access_requests=access_requests,
        audit_logs=audit_logs,
        total_employees=total_employees,
        pending_approvals=pending_approvals
    )

@app.route("/add_employee", methods=["POST"])
def add_employee():
    emp_id = request.form.get("employee_id")
    name = request.form.get("name")
    email = request.form.get("email")
    department = request.form.get("department")
    job_title = request.form.get("job_title")
    assigned_role = request.form.get("role_name")

    if emp_id and name and email:
        try:
            conn = sqlite3.connect("employees.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO employees (employee_id, name, email, department, job_title)
                VALUES (?, ?, ?, ?, ?)
            """, (emp_id, name, email, department, job_title))
            
            if assigned_role:
                cursor.execute("""
                    INSERT INTO employee_roles (employee_id, role_name)
                    VALUES (?, ?)
                """, (emp_id, assigned_role))

            log_event(cursor, f"Created employee profile for {name} ({emp_id}) with role '{assigned_role}'", performed_by="Admin")

            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            pass

    return redirect(url_for("home"))

@app.route("/request_access", methods=["POST"])
def request_access():
    emp_id = request.form.get("employee_id")
    system_name = request.form.get("system_name")
    reason = request.form.get("reason")

    if emp_id and system_name and reason:
        conn = sqlite3.connect("employees.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO access_requests (employee_id, system_name, reason)
            VALUES (?, ?, ?)
        """, (emp_id, system_name, reason))

        log_event(cursor, f"Employee {emp_id} requested access to {system_name}", performed_by=f"Employee:{emp_id}")

        conn.commit()
        conn.close()

    return redirect(url_for("home"))

@app.route("/update_request/<int:request_id>/<string:new_status>")
def update_request(request_id, new_status):
    if new_status in ["Approved", "Denied"]:
        conn = sqlite3.connect("employees.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT employee_id, system_name FROM access_requests WHERE id = ?", (request_id,))
        req_info = cursor.fetchone()

        cursor.execute("""
            UPDATE access_requests
            SET status = ?
            WHERE id = ?
        """, (new_status, request_id))

        if req_info:
            log_event(cursor, f"{new_status} access request #{request_id} for {req_info[0]} to {req_info[1]}", performed_by="Admin")

        conn.commit()
        conn.close()

    return redirect(url_for("home"))

# ==========================================
# REST API ENDPOINTS (Steps 24 & 25)
# ==========================================

@app.route("/api/employees", methods=["GET"])
def api_get_employees():
    conn = sqlite3.connect("employees.db")
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, name, email, department, job_title, status FROM employees")
    rows = cursor.fetchall()
    conn.close()

    employees = [
        {
            "employee_id": row[0],
            "name": row[1],
            "email": row[2],
            "department": row[3],
            "job_title": row[4],
            "status": row[5]
        }
        for row in rows
    ]
    return jsonify({"status": "success", "count": len(employees), "employees": employees})

@app.route("/api/audit-logs", methods=["GET"])
def api_get_audit_logs():
    conn = sqlite3.connect("employees.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, action, performed_by, timestamp FROM audit_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    logs = [
        {
            "id": row[0],
            "action": row[1],
            "performed_by": row[2],
            "timestamp": row[3]
        }
        for row in rows
    ]
    return jsonify({"status": "success", "count": len(logs), "audit_logs": logs})

if __name__ == "__main__":
    app.run(debug=True)