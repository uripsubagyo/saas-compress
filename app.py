from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User
from PIL import Image
import os
import io
from datetime import datetime, timedelta
import boto3
from botocore.client import Config

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# MinIO S3 configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "tk-image-storage")

s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

# Helper function
def upload_to_minio(file_bytes, object_name, content_type="image/jpeg"):
    s3_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=object_name,
        Body=file_bytes,
        ContentType=content_type
    )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'warning')
            return redirect(url_for('register'))
            
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password, method='scrypt')
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Account created successfully!', 'success')
        return redirect(url_for('pricing'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/upgrade/<plan>', methods=['POST'])
@login_required
def upgrade(plan):
    # Fake payment simulation
    current_user.subscription_tier = 'pro'
    
    # Set fake expiry based on plan
    if plan == 'weekly':
        duration = timedelta(weeks=1)
    elif plan == 'monthly':
        duration = timedelta(days=30)
    elif plan == 'yearly':
        duration = timedelta(days=365)
    else:
        duration = timedelta(days=30) # Default
        
    current_user.subscription_end_date = datetime.utcnow() + duration
    db.session.commit()
    
    flash(f'Payment successful! You are now subscribed to the {plan} plan.', 'success')
    return redirect(url_for('index'))

@app.route('/compress', methods=['GET', 'POST'])
def compress():
    if request.method == 'POST':
        # Check Usage Limits
        is_pro = False
        is_guest = not current_user.is_authenticated
        
        if not is_guest:
            is_pro = current_user.subscription_tier == 'pro'
            
            # Reset daily count if new day
            today = datetime.utcnow().date()
            if current_user.last_usage_date != today:
                current_user.daily_usage_count = 0
                current_user.last_usage_date = today
                db.session.commit()
            
            if not is_pro and current_user.daily_usage_count >= 5:
                flash('Daily limit reached (5/5). Upgrade to Pro for unlimited access!', 'warning')
                return redirect(url_for('pricing'))
        else:
            # Guest Limit
            guest_usage = session.get('guest_usage', 0)
            if guest_usage >= 1:
                flash('Guest limit reached (1/1). Please register for more access.', 'info')
                return redirect(url_for('register'))

        if 'image' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
            
        # Check size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)

        # Upload original image to MinIO
        original_path = f"original/{current_user.id if not is_guest else 'guest'}/{file.filename}"
        upload_to_minio(file.read(), original_path, file.content_type)
        
        max_size = 10 * 1024 * 1024 if is_pro else 2 * 1024 * 1024
        
        if file_length > max_size:
            flash(f'File too large. Limit is {"10MB" if is_pro else "2MB"}.', 'warning')
            return redirect(request.url)
        
        # Validate Image
        try:
            img = Image.open(file)
            img.verify()
        except Exception:
            flash("Invalid image file", "danger")
            return redirect(request.url)
            
        # Process Image
        try:
            img = Image.open(file)
            buffer = io.BytesIO()
            
            # Options
            quality = 85 # Default
            if is_pro and request.form.get('quality'):
                quality = int(request.form.get('quality'))
                
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            buffer.seek(0)

            # Upload processed image to MinIO
            processed_path = f"processed/{current_user.id if not is_guest else 'guest'}/compressed_{file.filename}"
            upload_to_minio(buffer.getvalue(), processed_path, "image/jpeg")
            
            # Increment Usage Count
            if not is_guest:
                current_user.daily_usage_count += 1
                db.session.commit()
            else:
                session['guest_usage'] = session.get('guest_usage', 0) + 1
            
            return send_file(
                buffer, 
                as_attachment=True, 
                download_name=f'compressed_{file.filename.rsplit(".", 1)[0]}.jpg', 
                mimetype='image/jpeg'
            )
            
        except Exception as e:
            flash(f'Error processing image: {e}', 'danger')
            return redirect(request.url)

    return render_template('compress.html')

@app.route('/resize', methods=['GET', 'POST'])
def resize():
    if request.method == 'POST':
        # Check Usage Limits
        is_pro = False
        is_guest = not current_user.is_authenticated
        
        if not is_guest:
            is_pro = current_user.subscription_tier == 'pro'
            
            # Reset daily count if new day
            today = datetime.utcnow().date()
            if current_user.last_usage_date != today:
                current_user.daily_usage_count = 0
                current_user.last_usage_date = today
                db.session.commit()
            
            if not is_pro and current_user.daily_usage_count >= 5:
                flash('Daily limit reached (5/5). Upgrade to Pro for unlimited access!', 'warning')
                return redirect(url_for('pricing'))
        else:
            # Guest Limit
            guest_usage = session.get('guest_usage', 0)
            if guest_usage >= 1:
                flash('Guest limit reached (1/1). Please register for more access.', 'info')
                return redirect(url_for('register'))

        if 'image' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
            
        # Check size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)

        # Upload original image to MinIO
        original_path = f"original/{current_user.id if not is_guest else 'guest'}/{file.filename}"
        upload_to_minio(file.read(), original_path, file.content_type)
        
        max_size = 10 * 1024 * 1024 if is_pro else 2 * 1024 * 1024
        
        if file_length > max_size:
            flash(f'File too large. Limit is {"10MB" if is_pro else "2MB"}.', 'warning')
            return redirect(request.url)
        
        # Validate Image
        try:
            img = Image.open(file)
            img.verify()
        except Exception:
            flash("Invalid image file", "danger")
            return redirect(request.url)
            
        # Process Image
        try:
            img = Image.open(file)
            img_mimetype = "image/jpeg" if img.format == "JPEG" or "JPG" else "image/png"
            buffer = io.BytesIO()
                
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            width = int(request.form.get('width', 800))
            height = int(request.form.get('height', 800))

            resized_img = img.resize((width, height))
            resized_img.save(buffer, format=img.format)
            buffer.seek(0)

            # Upload processed image to MinIO
            processed_path = f"processed/{current_user.id if not is_guest else 'guest'}/resized_{file.filename}"
            upload_to_minio(buffer.getvalue(), processed_path, img_mimetype)
            
            # Increment Usage Count
            if not is_guest:
                current_user.daily_usage_count += 1
                db.session.commit()
            else:
                session['guest_usage'] = session.get('guest_usage', 0) + 1
            
            return send_file(
                buffer, 
                as_attachment=True, 
                download_name=f'resized_{file.filename.rsplit(".", 1)[0]}.jpg', 
                mimetype=img_mimetype
            )
            
        except Exception as e:
            flash(f'Error processing image: {e}', 'danger')
            return redirect(request.url)

    return render_template('resize.html')

@app.route('/admin')
@login_required
def admin():
    # In a real app, restrict to admin users
    if not current_user.is_admin:
        # For prototype prototype debugging, maybe let anyone access OR just check the flag
        # We can set the first user as admin manually or just allow it if we didn't add logic to create admin.
        # Let's enforce the flag, but I will make sure to seed an admin or user can manually edit DB.
        # Actually, let's just allow it for now or flash a warning but show it for the prototype demonstration if they register as admin?
        # User requested: "protect this route, require login". 
        # But also "Admin Dashboard".
        # I'll rely on the is_admin flag.
        if not current_user.is_admin:
             flash('Access denied. Admin only.', 'danger')
             return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('dashboard.html', users=users)

# Create tables logic with retry and admin seeding
import time
from sqlalchemy.exc import OperationalError

with app.app_context():
    # Retry loop for DB connection (wait for Postgres)
    max_retries = 10
    for i in range(max_retries):
        try:
            db.create_all()
            
            # Auto-create Admin if not exists
            if not User.query.filter_by(username='admin').first():
                admin_user = User(
                    username='admin',
                    password_hash=generate_password_hash('admin123', method='scrypt'),
                    is_admin=True,
                    subscription_tier='pro'
                )
                db.session.add(admin_user)
                db.session.commit()
                print("Admin user created: admin / admin123")
            
            break
        except OperationalError:
            if i == max_retries - 1:
                raise
            print("Database not ready, verifying in 2s...")
            time.sleep(2)

if __name__ == '__main__':
    app.run(debug=True)
