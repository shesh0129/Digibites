import json
import os
import re
import secrets
from io import BytesIO
# pyrefly: ignore [missing-import]
from flask import Blueprint, current_app, request, jsonify, session, send_file
# pyrefly: ignore [missing-import]
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
from validators import secure_validate, ValidationError, ValidationHelper

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

GMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@gmail\.com$', re.IGNORECASE)
LRN_RE = re.compile(r'^\d{12}$')
GRADE_LEVELS = {str(grade) for grade in range(7, 13)}
MAX_STUDENT_ID_BYTES = 5 * 1024 * 1024


def _student_id_directory():
    return os.path.join(current_app.instance_path, 'student-id-verification')


def _valid_student_id_image(filename, contents):
    extension = os.path.splitext(filename)[1].lower()
    if extension == '.png':
        return contents.startswith(b'\x89PNG\r\n\x1a\n')
    if extension in {'.jpg', '.jpeg'}:
        return contents.startswith(b'\xff\xd8\xff') and contents.endswith(b'\xff\xd9')
    if extension == '.webp':
        return len(contents) >= 12 and contents[:4] == b'RIFF' and contents[8:12] == b'WEBP'
    return False


@auth_bp.errorhandler(413)
def student_upload_too_large(_):
    return jsonify({"success": False, "message": "The upload is too large. Please use a smaller image."}), 413


def _validate_gmail(email: str) -> str | None:
    """Return error string or None if valid @gmail.com address."""
    if not email:
        return "Email is required."
    if not GMAIL_RE.match(email.strip()):
        return "Only Gmail addresses (@gmail.com) are accepted."
    return None


@auth_bp.route('/register', methods=['POST'])
def register():
    """Submit a student account for staff verification."""
    if request.content_length and request.content_length > current_app.config['MAX_CONTENT_LENGTH']:
        return jsonify({"success": False, "message": "The upload is too large. Please use a smaller image."}), 413

    data = request.form.to_dict()

    try:
        cleaned = secure_validate(data, {
            'full_name': ['required', 'name', 'min:2', 'max:100'],
            'password':  ['required', 'min:8', 'max:100'],
            'phone':     ['required', 'ph_mobile'],
            'section':   ['required', 'min:1', 'max:100'],
        })
    except ValidationError as e:
        return jsonify(e.to_response()), 422

    email = (data.get('email') or data.get('username') or '').strip().lower()
    lrn = (data.get('lrn') or '').strip()
    grade = (data.get('grade') or '').strip()
    errors = {}

    email_err = _validate_gmail(email)
    if email_err:
        errors['email'] = email_err
    phone_compact = re.sub(r'[\s().-]', '', cleaned['phone'])
    if not re.fullmatch(r'(?:09\d{9}|\+?639\d{9}|9\d{9})', phone_compact):
        errors['phone'] = "Enter a valid Philippine mobile number."
    if not LRN_RE.fullmatch(lrn):
        errors['lrn'] = "Enter the 12-digit Learner Reference Number (LRN)."
    if grade not in GRADE_LEVELS:
        errors['grade'] = "Select a grade from 7 through 12."

    id_file = request.files.get('student_id_file')
    if not id_file or not id_file.filename:
        errors['student_id_file'] = "Upload a photo of your current school ID."
        image_contents = b''
    else:
        image_contents = id_file.stream.read(MAX_STUDENT_ID_BYTES + 1)
        if len(image_contents) > MAX_STUDENT_ID_BYTES:
            errors['student_id_file'] = "School ID image must be 5 MB or smaller."
        elif not _valid_student_id_image(id_file.filename, image_contents):
            errors['student_id_file'] = "Use a valid PNG, JPG, or WEBP image of your school ID."

    if errors:
        return jsonify({"success": False, "message": "Please check the highlighted fields.", "errors": errors}), 422

    full_name = ValidationHelper.title_case_name(cleaned['full_name'])
    phone = '0' + ValidationHelper.normalize_ph_mobile(cleaned['phone'])
    pw_hash   = generate_password_hash(cleaned['password'])

    conn = None
    stored_filename = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, role, verification_status FROM users WHERE username = %s", (email,))
            existing_user = cursor.fetchone()
            can_resubmit = bool(
                existing_user
                and existing_user['role'] == 'customer'
                and existing_user.get('verification_status') == 'rejected'
            )
            if existing_user and not can_resubmit:
                return jsonify({
                    "success": False,
                    "message": "This Gmail address is already registered.",
                    "errors": {"email": "Email already registered."}
                }), 409

            if can_resubmit:
                cursor.execute("SELECT id FROM users WHERE lrn = %s AND id <> %s", (lrn, existing_user['id']))
            else:
                cursor.execute("SELECT id FROM users WHERE lrn = %s", (lrn,))
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "This LRN is already associated with an account.",
                    "errors": {"lrn": "LRN already registered."}
                }), 409

            os.makedirs(_student_id_directory(), exist_ok=True)
            extension = os.path.splitext(id_file.filename)[1].lower()
            stored_filename = f"{secrets.token_hex(16)}{extension}"
            with open(os.path.join(_student_id_directory(), stored_filename), 'wb') as id_image:
                id_image.write(image_contents)

            if can_resubmit:
                user_id = existing_user['id']
                cursor.execute(
                    "UPDATE users SET password_hash = %s, full_name = %s, phone_number = %s, grade_level = %s, "
                    "section = %s, lrn = %s, student_id_filename = %s, verification_status = 'pending', "
                    "verification_note = NULL WHERE id = %s",
                    (pw_hash, full_name, phone, grade, cleaned['section'], lrn, stored_filename, user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, phone_number, grade_level, section, "
                    "lrn, student_id_filename, verification_status) "
                    "VALUES (%s, %s, %s, 'customer', %s, %s, %s, %s, %s, 'pending')",
                    (email, pw_hash, full_name, phone, grade, cleaned['section'], lrn, stored_filename)
                )
                user_id = cursor.lastrowid
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Application submitted. You can sign in after school staff verify your details.",
            "user": {
                "id":        user_id,
                "email":     email,
                "username":  email,
                "full_name": full_name,
                "phone":     phone,
                "grade":     grade,
                "section":   cleaned['section'],
                "role":      "customer",
                "verification_status": "pending",
            }
        }), 201
    except Exception:
        if conn is not None:
            conn.rollback()
        if stored_filename:
            try:
                os.remove(os.path.join(_student_id_directory(), stored_filename))
            except OSError:
                current_app.logger.exception("Could not remove an uncommitted student ID upload")
        current_app.logger.exception("Student registration failed")
        return jsonify({"success": False, "message": "Registration is temporarily unavailable. Please try again."}), 503
    finally:
        if conn is not None:
            conn.close()


@auth_bp.route('/admin/student-verifications', methods=['GET'])
def list_student_verifications():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, full_name, phone_number, grade_level, section, lrn, created_at FROM users "
                "WHERE role = 'customer' AND verification_status = 'pending' ORDER BY created_at ASC"
            )
            rows = cursor.fetchall()
        return jsonify({
            "success": True,
            "data": [{
                "id": row['id'],
                "email": row['username'],
                "full_name": row['full_name'],
                "phone": row['phone_number'],
                "grade": row['grade_level'],
                "section": row['section'],
                "lrn": row['lrn'],
                "created_at": row['created_at'].strftime('%Y-%m-%d %H:%M') if row.get('created_at') else '',
                "document_url": f"/api/auth/admin/student-verifications/{row['id']}/document",
            } for row in rows],
        })
    except Exception:
        current_app.logger.exception("Could not load student verification queue")
        return jsonify({"success": False, "message": "Could not load verification requests."}), 503
    finally:
        conn.close()


@auth_bp.route('/admin/student-verifications/<int:user_id>/document', methods=['GET'])
def get_student_verification_document(user_id):
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id_filename FROM users WHERE id = %s AND role = 'customer' "
                "AND verification_status = 'pending'",
                (user_id,)
            )
            row = cursor.fetchone()
        if not row or not row.get('student_id_filename'):
            return jsonify({"success": False, "message": "Pending school ID not found."}), 404
        stored_filename = os.path.basename(row['student_id_filename'])
        document_path = os.path.join(_student_id_directory(), stored_filename)
        with open(document_path, 'rb') as document:
            document_contents = document.read(MAX_STUDENT_ID_BYTES + 1)
        if len(document_contents) > MAX_STUDENT_ID_BYTES:
            return jsonify({"success": False, "message": "Stored school ID exceeds the allowed size."}), 413
        return send_file(
            BytesIO(document_contents),
            as_attachment=True,
            download_name=f"student-id-{user_id}{os.path.splitext(stored_filename)[1]}",
            mimetype='application/octet-stream',
        )
    except Exception:
        current_app.logger.exception("Could not retrieve student verification document")
        return jsonify({"success": False, "message": "Could not retrieve the school ID."}), 503
    finally:
        conn.close()


@auth_bp.route('/admin/student-verifications/<int:user_id>/review', methods=['POST'])
def review_student_verification(user_id):
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    note = str(data.get('note') or '').strip()[:500]
    if decision not in {'approved', 'rejected'}:
        return jsonify({"success": False, "message": "Choose approve or reject."}), 422
    if decision == 'rejected' and not note:
        return jsonify({"success": False, "message": "A reason is required when rejecting an application."}), 422

    conn = get_db_connection()
    stored_filename = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id_filename FROM users WHERE id = %s AND role = 'customer' "
                "AND verification_status = 'pending'",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"success": False, "message": "Pending verification request not found."}), 404

            stored_filename = row.get('student_id_filename')
            cursor.execute(
                "UPDATE users SET verification_status = %s, verification_note = %s, "
                "student_id_filename = NULL WHERE id = %s",
                (decision, note or None, user_id)
            )
        conn.commit()
        if stored_filename:
            try:
                os.remove(os.path.join(_student_id_directory(), os.path.basename(stored_filename)))
            except FileNotFoundError:
                pass
            except OSError:
                current_app.logger.exception("Could not delete reviewed student ID document")
        return jsonify({"success": True, "message": f"Student account {decision}.", "decision": decision})
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not review student verification request")
        return jsonify({"success": False, "message": "Could not save the verification decision."}), 503
    finally:
        conn.close()


def _is_admin_session():
    return 'user_id' in session and session.get('role') == 'admin'


@auth_bp.route('/admin/users', methods=['GET'])
def list_admin_users():
    if not _is_admin_session():
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, full_name, created_at FROM users "
                "WHERE role = 'admin' ORDER BY full_name, id"
            )
            rows = cursor.fetchall()
        return jsonify({"success": True, "data": [{
            "id": row['id'],
            "email": row['username'],
            "full_name": row['full_name'],
            "created_at": row['created_at'].strftime('%Y-%m-%d') if row.get('created_at') else '',
        } for row in rows]})
    except Exception:
        current_app.logger.exception("Could not load staff accounts")
        return jsonify({"success": False, "message": "Could not load staff accounts."}), 503
    finally:
        conn.close()


@auth_bp.route('/admin/users', methods=['POST'])
def create_admin_user():
    if not _is_admin_session():
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not all(isinstance(data.get(key), str) for key in ('full_name', 'email', 'password')):
        return jsonify({"success": False, "message": "Name, Gmail, and password must be text values."}), 422
    try:
        cleaned = secure_validate(data, {
            'full_name': ['required', 'name', 'min:2', 'max:100'],
            'password': ['required', 'min:8', 'max:100'],
        })
    except ValidationError as error:
        return jsonify(error.to_response()), 422

    email = (data.get('email') or '').strip().lower()
    email_error = _validate_gmail(email)
    if email_error:
        return jsonify({"success": False, "message": email_error, "errors": {"email": email_error}}), 422

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (email,))
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "This Gmail address is already registered.",
                    "errors": {"email": "Email already registered."},
                }), 409
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role, verification_status) "
                "VALUES (%s, %s, %s, 'admin', 'approved')",
                (email, generate_password_hash(cleaned['password']), ValidationHelper.title_case_name(cleaned['full_name']))
            )
            user_id = cursor.lastrowid
        conn.commit()
        return jsonify({"success": True, "message": "Staff account created.", "user": {
            "id": user_id, "email": email, "full_name": ValidationHelper.title_case_name(cleaned['full_name']),
        }}), 201
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not create staff account")
        return jsonify({"success": False, "message": "Could not create the staff account."}), 503
    finally:
        conn.close()


@auth_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
def update_admin_user(user_id):
    if not _is_admin_session():
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not all(isinstance(data.get(key), str) for key in ('full_name', 'email')):
        return jsonify({"success": False, "message": "Name and Gmail must be text values."}), 422
    if data.get('password') is not None and not isinstance(data['password'], str):
        return jsonify({"success": False, "message": "Password must be a text value."}), 422
    try:
        cleaned = secure_validate(data, {'full_name': ['required', 'name', 'min:2', 'max:100']})
        password = data.get('password') or ''
        if password:
            secure_validate({'password': password}, {'password': ['min:8', 'max:100']})
    except ValidationError as error:
        return jsonify(error.to_response()), 422

    email = (data.get('email') or '').strip().lower()
    email_error = _validate_gmail(email)

    full_name = ValidationHelper.title_case_name(cleaned['full_name'])
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username FROM users WHERE id = %s AND role = 'admin'", (user_id,))
            existing_user = cursor.fetchone()
            if not existing_user:
                return jsonify({"success": False, "message": "Staff account not found."}), 404
            if email_error and email != existing_user['username']:
                return jsonify({"success": False, "message": email_error, "errors": {"email": email_error}}), 422

            cursor.execute("SELECT id FROM users WHERE username = %s AND id <> %s", (email, user_id))
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "This Gmail address is already registered.",
                    "errors": {"email": "Email already registered."},
                }), 409

            if password:
                cursor.execute(
                    "UPDATE users SET username = %s, full_name = %s, password_hash = %s "
                    "WHERE id = %s AND role = 'admin'",
                    (email, full_name, generate_password_hash(password), user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET username = %s, full_name = %s WHERE id = %s AND role = 'admin'",
                    (email, full_name, user_id)
                )
        conn.commit()
        if session.get('user_id') == user_id:
            session['username'] = email
            session['email'] = email
            session['full_name'] = full_name
        return jsonify({"success": True, "message": "Staff account updated."})
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not update staff account")
        return jsonify({"success": False, "message": "Could not update the staff account."}), 503
    finally:
        conn.close()


@auth_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_admin_user(user_id):
    if not _is_admin_session():
        return jsonify({"success": False, "message": "Administrator access required."}), 403
    if session.get('user_id') == user_id:
        return jsonify({"success": False, "message": "You cannot delete your own signed-in account."}), 409

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role = 'admin' FOR UPDATE")
            admin_ids = cursor.fetchall()
            if len(admin_ids) <= 1:
                return jsonify({"success": False, "message": "The last administrator account cannot be deleted."}), 409
            cursor.execute("DELETE FROM users WHERE id = %s AND role = 'admin'", (user_id,))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "Staff account not found."}), 404
        conn.commit()
        return jsonify({"success": True, "message": "Staff account deleted."})
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not delete staff account")
        return jsonify({"success": False, "message": "Could not delete the staff account."}), 503
    finally:
        conn.close()


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login for both Customer and Admin using email or username."""
    data     = request.get_json(silent=True) or {}
    ident    = (data.get('email') or data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not ident or not password:
        return jsonify({"success": False, "message": "Email/Username and password are required."}), 400

    # If domain provided, ensure only @gmail.com is allowed (except admin)
    if '@' in ident and not GMAIL_RE.match(ident):
        return jsonify({
            "success": False,
            "message": "Only Gmail addresses (@gmail.com) are accepted.",
            "errors": {"email": "Only @gmail.com addresses are accepted."}
        }), 422

    # Build candidates: e.g. "student1", "student1@gmail.com"
    prefix = ident.replace('@gmail.com', '')
    candidates = (ident, prefix, f"{prefix}@gmail.com")

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password_hash, full_name, role, allergies, verification_status, verification_note FROM users "
                "WHERE username = %s OR username = %s OR username = %s LIMIT 1",
                candidates
            )
            user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Invalid email/username or password."}), 401

        # Check password with fallback for demo accounts
        pw_ok = check_password_hash(user['password_hash'], password)
        if not pw_ok and prefix == 'student1' and password in ('student123', 'pass123'):
            pw_ok = True
        if not pw_ok and user['username'] == 'admin' and password == 'admin123':
            pw_ok = True

        if not pw_ok:
            return jsonify({"success": False, "message": "Invalid email/username or password."}), 401

        if user['role'] == 'customer':
            verification_status = user.get('verification_status') or 'approved'
            if verification_status == 'pending':
                return jsonify({
                    "success": False,
                    "verification_status": "pending",
                    "message": "Your student account is waiting for school staff verification.",
                }), 403
            if verification_status != 'approved':
                message = user.get('verification_note') if verification_status == 'rejected' else None
                return jsonify({
                    "success": False,
                    "verification_status": verification_status,
                    "message": message or "Your student account was not approved. Please contact school staff.",
                }), 403

        # Parse user allergies
        raw_allergies = user.get('allergies') or '[]'
        try:
            user_allergies = json.loads(raw_allergies) if isinstance(raw_allergies, str) else (raw_allergies if isinstance(raw_allergies, list) else [])
        except Exception:
            user_allergies = []

        # Build display email/username
        stored_email = user['username']
        session['user_id']   = user['id']
        session['email']     = stored_email
        session['username']  = stored_email
        session['full_name'] = user['full_name']
        session['role']      = user['role']
        session['allergies'] = user_allergies

        # Update last_active_at timestamp
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE id = %s", (user['id'],))
            conn.commit()
        except Exception:
            pass

        return jsonify({
            "success":  True,
            "message":  f"Welcome, {user['full_name']}!",
            "redirect": "/admin/dashboard" if user['role'] == 'admin' else "/customer/dashboard",
            "user": {
                "id":        user['id'],
                "email":     stored_email,
                "username":  stored_email,
                "full_name": user['full_name'],
                "role":      user['role'],
                "allergies": user_allergies,
            }
        })
    except Exception:
        current_app.logger.exception("Login request failed")
        return jsonify({
            "success": False,
            "message": "The login service is temporarily unavailable. Please try again later."
        }), 503
    finally:
        if conn is not None:
            conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "redirect": "/login"})


@auth_bp.route('/me', methods=['GET'])
def me():
    """Return current session user with latest allergies."""
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated."}), 401

    user_allergies = session.get('allergies', [])
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT allergies, full_name, role FROM users WHERE id = %s", (session['user_id'],))
            row = cursor.fetchone()
            if row:
                raw_allergies = row.get('allergies') or '[]'
                try:
                    user_allergies = json.loads(raw_allergies) if isinstance(raw_allergies, str) else (raw_allergies if isinstance(raw_allergies, list) else [])
                except Exception:
                    user_allergies = []
                session['allergies'] = user_allergies
                session['full_name'] = row.get('full_name', session['full_name'])
                session['role']      = row.get('role', session['role'])
    except Exception:
        pass
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "user": {
            "id":        session['user_id'],
            "email":     session.get('email', '') or session.get('username', ''),
            "username":  session.get('username', '') or session.get('email', ''),
            "full_name": session['full_name'],
            "role":      session['role'],
            "allergies": user_allergies,
        }
    })
