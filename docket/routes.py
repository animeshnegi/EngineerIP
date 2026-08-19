from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app, send_from_directory
from docket.models import db, User, UploadedFile, FileRecord, FileType, UploadStatus, Attorney, Inventor, Case, Deadline, NotificationLog, USPTOApiLog, Configuration, Country, FeeSchedule, AutomationLog, Document, MaintenanceFee, OfficeAction, StatusHistory, DeadlineType, CaseStatus, CaseType, NotificationType, Project, ProjectFile, ProjectMessage, ProjectNotification
from datetime import datetime, timedelta, date
import holidays
import time
import requests
import hashlib
import secrets
import re
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, func
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from threading import Thread
import pandas as pd
import uuid
import os
import json
from sqlalchemy import desc



docket_bp = Blueprint('docket', __name__, template_folder='templates')



# Simple session-based authentication (no Flask-Login needed)
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('docket.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def get_current_user_id():
    """Get current user ID from session"""
    return session.get('user_id')

def get_current_user():
    """Get current user object from session"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

def get_current_user_name():
    """Get current user's full name"""
    user = get_current_user()
    if user:
        return f"{user.first_name} {user.last_name}"
    return 'Guest'

def is_user_logged_in():
    """Check if user is logged into docket system"""
    return session.get('user_id') is not None

def format_file_size(bytes):
    """Format file size from bytes to human readable format"""
    if bytes is None:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Authentication Routes
@docket_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to index
    if 'user_id' in session:
        return redirect(url_for('docket.docindex'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.password == hash_password(password):
            # Login successful
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_name'] = f"{user.first_name} {user.last_name}"

            
            if remember_me:
                session.permanent = True
            
            flash('Login successful!', 'success')
            return redirect(url_for('docket.docindex'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')



@docket_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('docket.login'))

@docket_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Simple token generation (for demo)
            token = secrets.token_urlsafe(32)
            session['reset_token'] = token
            session['reset_email'] = email
            
            flash(f'Password reset token (demo): {token}', 'info')
        else:
            flash('If that email exists, a reset link has been sent.', 'info')
        
        return redirect(url_for('docket.login'))
    
    return render_template('docket/forgot_password.html')

@docket_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')
    
    # Verify token (simplified for demo)
    if not token or token != session.get('reset_token'):
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('docket.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = session.get('reset_email')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('docket/reset_password.html', token=token)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('docket/reset_password.html', token=token)
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = hash_password(password)
            db.session.commit()
            
            # Clear reset session
            session.pop('reset_token', None)
            session.pop('reset_email', None)
            
            flash('Password updated successfully!', 'success')
            return redirect(url_for('docket.login'))
    
    return render_template('docket/reset_password.html', token=token)



# Your existing docket routes (protected)
@docket_bp.route('/')
@login_required
def docindex():
    try:
        user_name = session.get('user_name', 'User')
        return render_template('docket_index.html', user_name=user_name)
    except Exception as e:
        return render_template('docket_index.html', user_name='User')




@docket_bp.route('/debug-upload', methods=['POST'])
@login_required
def debug_upload():
    """Debug endpoint to test file upload"""
    print("DEBUG: /debug-upload called")
    user_id = get_current_user_id()
    print(f"DEBUG: User ID: {user_id}")
    print(f"DEBUG: Files: {request.files}")
    print(f"DEBUG: Form: {request.form}")
    
    return jsonify({
        'success': True,
        'message': 'Debug endpoint working',
        'user_id': user_id,
        'files_received': len(request.files)
    })

@docket_bp.route('/debug-status')
@login_required
def debug_status():
    """Debug endpoint to test scraping status"""
    print("DEBUG: /debug-status called")
    user_id = get_current_user_id()
    print(f"DEBUG: User ID: {user_id}")
    
    return jsonify({
        'success': True,
        'message': 'Status endpoint working',
        'user_id': user_id
    })











# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_user_upload_folder(user_id, file_type):
    """Create user-specific folder for uploads"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{file_type}_{user_id}_{timestamp}"
    folder_path = os.path.join(UPLOAD_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def process_uploaded_file(file, file_type, user_id):
    """Process uploaded file and save to database"""
    try:
        # Create user-specific folder
        upload_folder = create_user_upload_folder(user_id, file_type.value)
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{file_type.value}_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = os.path.join(upload_folder, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Read file and extract numbers
        if file_extension == 'csv':
            df = pd.read_csv(file_path, header=None)
        else:  # Excel files
            df = pd.read_excel(file_path, header=None)
        
        # Extract numbers from first column
        numbers = df[0].astype(str).str.strip().tolist()
        total_records = len(numbers)
        
        # Create database entry for uploaded file (without current_item)
        uploaded_file = UploadedFile(
            user_id=user_id,
            filename=unique_filename,
            original_filename=original_filename,
            file_path=file_path,
            file_type=file_type,
            total_records=total_records,
            upload_date=datetime.utcnow()
        )
        db.session.add(uploaded_file)
        db.session.flush()  # Get the ID
        
        # Create file records for each number
        for number in numbers:
            file_record = FileRecord(
                uploaded_file_id=uploaded_file.id,
                record_number=number,
                status=UploadStatus.UPLOADED
            )
            db.session.add(file_record)
        
        db.session.commit()
        
        return uploaded_file, numbers
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error processing file: {str(e)}")


# Scraping Functions
def setup_headless_driver():
    """Setup completely headless Chrome driver"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-images")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1920,1080")
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def scrape_trademark_data(tm_number):
    """Scrape single trademark data"""
    print(f"DEBUG: Starting scrape for TM {tm_number}")
    driver = setup_headless_driver()
    try:
        url = f"https://tsdr.uspto.gov/#caseNumber={tm_number}&caseSearchType=US_APPLICATION&caseType=DEFAULT&searchType=statusSearch"
        print(f"DEBUG: Loading URL: {url}")
        driver.get(url)
        
        # Wait for dynamic content
        print("DEBUG: Waiting for page to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='key' and contains(text(), 'Status:')]"))
        )
        
        time.sleep(1)
        
        # Extract data
        print("DEBUG: Extracting data...")
        data = {
            'TM Number': tm_number,
            'Mark': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Mark:')]/following-sibling::div[1]"),
            'Application Filing Date': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Application Filing Date:')]/following-sibling::div[1]"),
            'Status Date': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Status Date:')]/following-sibling::div[1]"),
            'Register': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Register:')]/following-sibling::div[1]"),
            'Mark Type': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Mark Type:')]/following-sibling::div[1]"),
            'Owner Name': get_text_by_xpath(driver, "//div[contains(text(),'Owner Name:')]/following-sibling::div[1]"),
            'Owner Address': get_text_by_xpath(driver, "//div[contains(text(),'Owner Address:')]/following-sibling::div[1]", join_lines=True),
            'Entity': get_text_by_xpath(driver, "//div[contains(text(),'Legal Entity Type:')]/following-sibling::div[1]"),
            'Attorney Name': get_text_by_xpath(driver, "//div[contains(text(),'Attorney Name:')]/following-sibling::div[1]"),
            'Status': get_text_by_xpath(driver, "//div[@class='key' and contains(text(), 'Status:')]/following-sibling::div[1]"),
            'scraped_at': datetime.utcnow().isoformat()
        }
        
        print(f"DEBUG: Successfully scraped data for {tm_number}")
        return data
        
    except Exception as e:
        print(f"DEBUG: Error scraping {tm_number}: {str(e)}")
        return {'error': str(e), 'TM Number': tm_number}
    finally:
        driver.quit()
        print("DEBUG: Driver closed")

def get_text_by_xpath(driver, xpath, join_lines=False):
    """Helper function to get text by XPath"""
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        if not elements:
            return ""
        
        if join_lines:
            lines = [element.get_attribute('textContent').strip() for element in elements if element.get_attribute('textContent').strip()]
            return ', '.join(lines) if lines else ""
        else:
            text = elements[0].get_attribute('textContent').strip()
            return text if text else ""
    except Exception:
        return ""

def scrape_patent_data(patent_number):
    """Scrape single patent data - placeholder for patent scraping"""
    # This would be your patent scraping logic
    time.sleep(0.5)  # Simulate processing
    return {
        'Patent Number': patent_number,
        'Title': f"Patent {patent_number}",
        'Status': 'Pending',
        'scraped_at': datetime.utcnow().isoformat()
    }

# Background Processing Functions
def process_trademark_file_background(app, uploaded_file_id, user_id):
    """Background function to process trademark file with app instance"""
    print(f"DEBUG: Background thread started - app: {type(app)}, file_id: {uploaded_file_id}, user_id: {user_id}")
    
    try:
        # Use the application context with the passed app instance
        with app.app_context():
            print("DEBUG: Inside app context")
            
            uploaded_file = UploadedFile.query.get(uploaded_file_id)
            if not uploaded_file:
                print(f"DEBUG: Uploaded file {uploaded_file_id} not found")
                return
            
            print(f"DEBUG: Starting processing for file {uploaded_file_id} with {uploaded_file.total_records} records")
            
            uploaded_file.status = UploadStatus.PROCESSING
            db.session.commit()
            print("DEBUG: Set status to PROCESSING")

            # Get all records for this file
            records = FileRecord.query.filter_by(uploaded_file_id=uploaded_file_id).all()
            print(f"DEBUG: Found {len(records)} records to process")
            
            total_records = len(records)
            
            for i, record in enumerate(records):
                print(f"DEBUG: Processing record {i+1}/{total_records}: {record.record_number}")
                
                # Update progress in database
                uploaded_file = UploadedFile.query.get(uploaded_file_id)
                uploaded_file.processed_records = i + 1
                db.session.commit()
                print(f"DEBUG: Updated processed_records to {i+1}")
                
                try:
                    # Use mock data for testing first
                    print(f"DEBUG: Mock scraping data for {record.record_number}")
                    scraped_data = scrape_trademark_data(record.record_number)
                    
                    record.scraped_data = json.dumps(scraped_data)
                    record.status = UploadStatus.COMPLETED
                    record.processed_date = datetime.utcnow()
                    print(f"DEBUG: Marked record {record.record_number} as COMPLETED")
                    
                    db.session.commit()
                    print("DEBUG: Committed record changes")
                    
                except Exception as e:
                    print(f"DEBUG: Exception processing record {record.record_number}: {str(e)}")
                    record.status = UploadStatus.FAILED
                    record.error_message = str(e)
                    uploaded_file = UploadedFile.query.get(uploaded_file_id)
                    uploaded_file.failed_records = FileRecord.query.filter_by(
                        uploaded_file_id=uploaded_file_id,
                        status=UploadStatus.FAILED
                    ).count()
                    db.session.commit()
                    print("DEBUG: Committed failure changes")
                
                time.sleep(2)  # Simulate processing time so we can see progress
            
            # Mark file as completed
            uploaded_file = UploadedFile.query.get(uploaded_file_id)
            uploaded_file.status = UploadStatus.COMPLETED
            db.session.commit()
            print("DEBUG: Marked file as COMPLETED")
            
    except Exception as e:
        print(f"DEBUG: Exception in background processing: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Try to mark as failed even if there's an error
        try:
            with app.app_context():
                uploaded_file = UploadedFile.query.get(uploaded_file_id)
                if uploaded_file:
                    uploaded_file.status = UploadStatus.FAILED
                    db.session.commit()
        except:
            pass




def process_patent_file_background(app, uploaded_file_id, user_id):
    """Background function to process patent file"""
    # Get the app instance from the current thread
    from flask import current_app
    
    # Use the application context for the entire function
    with current_app.app_context():
        try:
            uploaded_file = UploadedFile.query.get(uploaded_file_id)
            if not uploaded_file:
                return
            
            uploaded_file.status = UploadStatus.PROCESSING
            db.session.commit()

            # Get all records for this file
            records = FileRecord.query.filter_by(uploaded_file_id=uploaded_file_id).all()
            
            total_records = len(records)
            
            for i, record in enumerate(records):
                # Update progress in database
                uploaded_file = UploadedFile.query.get(uploaded_file_id)
                uploaded_file.processed_records = i + 1
                db.session.commit()
                
                try:
                    # For now, using placeholder - implement actual patent scraping
                    scraped_data = scrape_patent_data(record.record_number)
                    
                    record.scraped_data = json.dumps(scraped_data)
                    record.status = UploadStatus.COMPLETED
                    record.processed_date = datetime.utcnow()
                    db.session.commit()
                    
                except Exception as e:
                    record.status = UploadStatus.FAILED
                    record.error_message = str(e)
                    uploaded_file = UploadedFile.query.get(uploaded_file_id)
                    uploaded_file.failed_records = FileRecord.query.filter_by(
                        uploaded_file_id=uploaded_file_id,
                        status=UploadStatus.FAILED
                    ).count()
                    db.session.commit()
                
                time.sleep(0.5)
            
            # Mark file as completed
            uploaded_file = UploadedFile.query.get(uploaded_file_id)
            uploaded_file.status = UploadStatus.COMPLETED
            db.session.commit()
            
        except Exception as e:
            uploaded_file = UploadedFile.query.get(uploaded_file_id)
            if uploaded_file:
                uploaded_file.status = UploadStatus.FAILED
                db.session.commit()
            print(f"Error in patent background processing: {str(e)}")


@docket_bp.route('/add-case', methods=['GET', 'POST'])
@login_required
def addcase():
    if request.method == 'POST':
        patent_file = request.files.get('patent_file')
        tm_file = request.files.get('tm_file')
        file_type = request.form.get('file_type')
        
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            user_id = get_current_user_id()
            
            # Process Trademark File
            if tm_file and tm_file.filename and file_type == 'trademark':
                if tm_file.content_length > MAX_FILE_SIZE:
                    if is_ajax:
                        return jsonify({'success': False, 'error': 'Trademark file is too large. Maximum size is 16MB.'})
                    flash('Trademark file is too large. Maximum size is 16MB.', 'error')
                    return render_template('add-case.html')
                
                if not allowed_file(tm_file.filename):
                    if is_ajax:
                        return jsonify({'success': False, 'error': 'Invalid file type for trademark. Please upload CSV or Excel files.'})
                    flash('Invalid file type for trademark. Please upload CSV or Excel files.', 'error')
                    return render_template('add-case.html')
                
                uploaded_file, numbers = process_uploaded_file(tm_file, FileType.TRADEMARK, user_id)
                print(f"DEBUG: File processed successfully. Uploaded file ID: {uploaded_file.id}, Numbers found: {len(numbers)}")
                
                # Start background processing - pass ALL required arguments
                from flask import current_app
                app_instance = current_app._get_current_object()
                
                # Make sure we pass all 3 arguments: app, uploaded_file_id, user_id
                thread = Thread(
                    target=process_trademark_file_background, 
                    args=(app_instance, uploaded_file.id, user_id)  # All 3 arguments
                )
                thread.daemon = True
                thread.start()
                print(f"DEBUG: Background thread started for trademark processing with file ID: {uploaded_file.id}, user ID: {user_id}")
                
                if is_ajax:
                    response_data = {
                        'success': True, 
                        'message': f'Trademark file uploaded successfully. Processing {len(numbers)} trademark numbers.',
                        'file_id': uploaded_file.id
                    }
                    print(f"DEBUG: Returning AJAX response: {response_data}")
                    return jsonify(response_data)
                else:
                    flash(f'Trademark file uploaded successfully. Found {len(numbers)} trademark numbers.', 'success')
                    return render_template('add-case.html')
            
            # Process Patent File
            elif patent_file and patent_file.filename and file_type == 'patent':
                if patent_file.content_length > MAX_FILE_SIZE:
                    if is_ajax:
                        return jsonify({'success': False, 'error': 'Patent file is too large. Maximum size is 16MB.'})
                    flash('Patent file is too large. Maximum size is 16MB.', 'error')
                    return render_template('add-case.html')
                
                if not allowed_file(patent_file.filename):
                    if is_ajax:
                        return jsonify({'success': False, 'error': 'Invalid file type for patent. Please upload CSV or Excel files.'})
                    flash('Invalid file type for patent. Please upload CSV or Excel files.', 'error')
                    return render_template('add-case.html')
                
                uploaded_file, numbers = process_uploaded_file(patent_file, FileType.PATENT, user_id)
                print(f"DEBUG: Patent file processed successfully. Uploaded file ID: {uploaded_file.id}, Numbers found: {len(numbers)}")
                
                # Start background processing for patent - pass ALL required arguments
                from flask import current_app
                app_instance = current_app._get_current_object()
                
                thread = Thread(
                    target=process_patent_file_background, 
                    args=(app_instance, uploaded_file.id, user_id)  # All 3 arguments
                )
                thread.daemon = True
                thread.start()
                print(f"DEBUG: Background thread started for patent processing with file ID: {uploaded_file.id}, user ID: {user_id}")
                
                if is_ajax:
                    response_data = {
                        'success': True, 
                        'message': f'Patent file uploaded successfully. Processing {len(numbers)} patent numbers.',
                        'file_id': uploaded_file.id
                    }
                    return jsonify(response_data)
                else:
                    flash(f'Patent file uploaded successfully. Found {len(numbers)} patent numbers.', 'success')
                    return render_template('add-case.html')
            
            else:
                error_msg = 'No file selected or invalid file type'
                print(f"DEBUG: {error_msg}")
                if is_ajax:
                    return jsonify({'success': False, 'error': error_msg})
                flash(error_msg, 'error')
                return render_template('add-case.html')
            
        except Exception as e:
            error_msg = f'Error processing files: {str(e)}'
            print(f"DEBUG: Exception in addcase: {error_msg}")
            import traceback
            print(traceback.format_exc())
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg})
            flash(error_msg, 'error')
            return render_template('add-case.html')
    
    # GET request - show the upload form
    print("DEBUG: addcase GET request")
    user_name = session.get('user_name', 'User')
    return render_template('add-case.html', user_name=user_name)

@docket_bp.route('/scraping-progress')
@login_required
def scraping_progress():
    file_id = request.args.get('file_id')
    return render_template('scraping-progress.html', file_id=file_id)

@docket_bp.route('/scraping-status')
@login_required
def scraping_status():
    """API endpoint to get current scraping progress"""
    try:
        user_id = get_current_user_id()
        
        print(f"DEBUG: scraping-status - Looking for active files for user {user_id}")
        
        # Alternative approach: Get any file that's not completed or failed
        uploaded_file = UploadedFile.query.filter_by(
            user_id=user_id
        ).filter(
            UploadedFile.status != UploadStatus.COMPLETED,
            UploadedFile.status != UploadStatus.FAILED
        ).order_by(UploadedFile.upload_date.desc()).first()
        
        # If no active processing, get the most recent completed file
        if not uploaded_file:
            uploaded_file = UploadedFile.query.filter_by(
                user_id=user_id
            ).order_by(UploadedFile.upload_date.desc()).first()
        
        print(f"DEBUG: scraping-status - Found file: {uploaded_file.id if uploaded_file else 'None'}")
        
        if not uploaded_file:
            return jsonify({
                'progress': {
                    'total': 0,
                    'processed': 0,
                    'successful': 0,
                    'failed': 0,
                    'current_item': 'No active processing',
                    'file_type': 'none'
                },
                'complete': True
            })
        
        # Calculate progress from database
        completed_records = FileRecord.query.filter_by(
            uploaded_file_id=uploaded_file.id,
            status=UploadStatus.COMPLETED
        ).count()
        
        failed_records = FileRecord.query.filter_by(
            uploaded_file_id=uploaded_file.id,
            status=UploadStatus.FAILED
        ).count()
        
        # Generate current_item message based on progress
        if uploaded_file.status == UploadStatus.UPLOADED:
            current_item_msg = "Waiting to start processing..."
        elif uploaded_file.status == UploadStatus.PROCESSING:
            if uploaded_file.processed_records == 0:
                current_item_msg = "Starting processing..."
            elif uploaded_file.processed_records < uploaded_file.total_records:
                progress_percent = (uploaded_file.processed_records / uploaded_file.total_records) * 100
                current_item_msg = f"Processing {uploaded_file.processed_records} of {uploaded_file.total_records} records ({progress_percent:.1f}%)..."
            else:
                current_item_msg = "Finalizing..."
        else:  # COMPLETED or FAILED
            current_item_msg = "Processing completed!"
        
        progress_data = {
            'file_id': uploaded_file.id,
            'total': uploaded_file.total_records,
            'processed': uploaded_file.processed_records,
            'successful': completed_records,
            'failed': failed_records,
            'current_item': current_item_msg,
            'file_type': uploaded_file.file_type.value
        }
        
        complete = uploaded_file.status in [UploadStatus.COMPLETED, UploadStatus.FAILED]
        
        print(f"DEBUG: scraping-status - Progress data: {progress_data}")
        print(f"DEBUG: scraping-status - Complete: {complete}")
        
        return jsonify({
            'progress': progress_data,
            'complete': complete
        })
        
    except Exception as e:
        print(f"ERROR in scraping-status: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'progress': {
                'total': 0,
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'current_item': f'Error: {str(e)}',
                'file_type': 'error'
            },
            'complete': True
        })

@docket_bp.route('/download-results/<int:file_id>')
@login_required
def download_results(file_id):
    """Download scraping results as Excel file"""
    uploaded_file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    
    # Get all successful records
    records = FileRecord.query.filter_by(
        uploaded_file_id=file_id, 
        status=UploadStatus.COMPLETED
    ).all()
    
    # Convert to DataFrame
    data = []
    for record in records:
        if record.scraped_data:
            scraped_data = json.loads(record.scraped_data)
            data.append(scraped_data)
    
    if data:
        df = pd.DataFrame(data)
        # Save to Excel and return as download
        # Implementation depends on your file serving method
        pass
    
    flash('No data available for download', 'info')
    return redirect(url_for('docket.addcase'))













































# Below are the Project Tracking and Notification System components
@docket_bp.route('/My-desk', methods=['GET', 'POST'])
@login_required
def mydesk():
    if request.method == 'POST':
        data = request.form
        
        # Create new project
        if data.get('action') == 'create_project':
            try:
                current_user = get_current_user()
                if not current_user:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                # Generate unique RefID
                import uuid
                ref_id = f"PROJ-{uuid.uuid4().hex[:8].upper()}"
                
                # Get form data
                name = data.get('name')
                description = data.get('description', '')
                due_date_str = data.get('due_date')
                category = data.get('category', 'Other')
                budget = data.get('budget', 0.0)
                
                if not name:
                    return jsonify({'success': False, 'error': 'Project name is required'})
                
                if not due_date_str:
                    return jsonify({'success': False, 'error': 'Due date is required'})
                
                # Create project
                project = Project(
                    user_id=current_user.id,
                    name=name,
                    ref_id=ref_id,
                    description=description,
                    due_date=datetime.strptime(due_date_str, '%Y-%m-%d').date(),
                    status='active',
                    category=category,
                    budget=float(budget) if budget else 0.0
                )
                db.session.add(project)
                db.session.flush()  # Get project.id without committing
                

                project_msg = ProjectMessage(
                    project_id=project.id,
                    user_id=current_user.id,
                    message=project.description,
                    is_admin=False
                )

                db.session.add(project_msg)

                # Create user folder structure
                user_folder = os.path.join('projects_data', f"user_{current_user.id}")
                project_folder = os.path.join(user_folder, f"project_{project.id}")
                os.makedirs(project_folder, exist_ok=True)
                
                # Handle file uploads
                files_list = request.files.getlist('files[]')  # Store once
                files_count = len(files_list)
                print(f"Processing {files_count} files")     


                uploaded_files = []
                
                for file in files_list:
                    if file and file.filename and file.filename.strip():
                        # Create secure filename
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{filename}"
                        
                        # Save file
                        filepath = os.path.join(project_folder, unique_filename)
                        file.save(filepath)
                        
                        # Save file record to database
                        project_file = ProjectFile(
                            project_id=project.id,
                            filename=filename,
                            file_path=filepath,
                            file_type=filename.split('.')[-1] if '.' in filename else '',
                            file_size=os.path.getsize(filepath),
                            uploaded_by=current_user.id
                        )
                        db.session.add(project_file)
                        uploaded_files.append(filename)
                
                # Commit everything
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'project_id': project.id,
                    'ref_id': ref_id,
                    'message': 'Project created successfully!',
                    'uploaded_files': uploaded_files
                })
                
            except ValueError as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': f'Invalid data: {str(e)}'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)})
    
    # GET request handling - FIXED VERSION
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('docket.login'))
        
    # GET request handling - FIXED VERSION
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('docket.login'))
        
    # Get all projects for the user
    projects = Project.query.filter_by(user_id=current_user.id, is_deleted=False)\
        .order_by(desc(Project.created_at)).all()
    
    # Create a list of projects with all the data we need
    projects_with_data = []
    today = date.today()
    
    for project in projects:
        # Calculate days until due
        days_until_due = project.get_days_until_due()
        
        # Get file count
        file_count = ProjectFile.query.filter_by(
            project_id=project.id, 
            is_deleted=False
        ).count()
        
        # FIXED: Get new messages count using is_seen field
        new_messages_count = ProjectMessage.query.filter_by(
            project_id=project.id,
            is_admin=True,      # Messages from admin
            is_seen=False       # Not seen by client (using your actual field name)
        ).count()
        
        # Create a dictionary with all project data
        project_data = {
            'id': project.id,
            'name': project.name,
            'ref_id': project.ref_id,
            'description': project.description,
            'due_date': project.due_date,
            'status': project.status,
            'created_at': project.created_at,
            'updated_at': project.updated_at,
            'days_until_due': days_until_due,
            'file_count': file_count,
            'new_messages_count': new_messages_count,
            'has_new_messages': new_messages_count > 0,
        }
        
        projects_with_data.append(project_data)
        
        # Check for due dates approaching
        if 0 <= days_until_due <= 7:
            # Check if reminder already sent today
            sent_today = ProjectNotification.query.filter_by(
                project_id=project.id,
                notification_type='due_date_reminder',
                days_before=days_until_due
            ).filter(
                func.date(ProjectNotification.sent_at) == today
            ).first()
            
            # if not sent_today and current_user.email_notifications:
                # Send email reminder
                # send_due_date_reminder(project, days_until_due)
    
    user_name = session.get('user_name', 'User')
    
    return render_template('cli-portal.html', 
                         projects=projects_with_data, 
                         today=today,
                         user_name=user_name)



# Helper function to mark admin messages as seen
# Add this helper function in your client routes section
def mark_all_admin_messages_as_seen(project_id, user_id):
    """
    Mark all admin messages as seen when client sends a message
    """
    try:
        messages_to_mark = ProjectMessage.query.filter_by(
            project_id=project_id,
            is_admin=True,
            is_seen=False
        ).all()
        
        for message in messages_to_mark:
            message.is_seen = True
            message.seen_at = datetime.utcnow()
        
        db.session.commit()
        return len(messages_to_mark)
    except Exception as e:
        db.session.rollback()
        print(f"Error marking messages as seen: {e}")
        return 0


@docket_bp.route('/api/send-msg', methods=['POST'])
@login_required
def api_send_message():
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'success': False, 'error': 'User not found. Please login again.'})
        
        print(f"DEBUG CLIENT SEND: User ID: {current_user.id}, Name: {current_user.first_name}")
        
        # Handle both FormData (with file) and JSON (without file)
        file_data = None
        if 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()
            file_data = request.files.get('file')
        else:
            data = request.get_json()
        
        print(f"DEBUG CLIENT SEND: Action: {data.get('action')}")
        print(f"DEBUG CLIENT SEND: Has file: {bool(file_data)}")
        
        if data.get('action') == 'send_message':
            project_id = data.get('project_id')
            message = data.get('message', '').strip()
            
            if not project_id:
                return jsonify({'success': False, 'error': 'Project ID is required'})
            
            # Allow sending file without text
            if not message and not file_data:
                return jsonify({'success': False, 'error': 'Please type a message or attach a file'})
            
            # Verify project exists and user has access
            project = Project.query.get(project_id)
            if not project:
                return jsonify({'success': False, 'error': 'Project not found'})
            
            if project.user_id != current_user.id:
                return jsonify({'success': False, 'error': 'Unauthorized access to this project'})
            
            # MARK ALL PREVIOUS ADMIN MESSAGES AS SEEN
            mark_all_admin_messages_as_seen(project_id, current_user.id)
            
            file_id = None
            
            # Handle file upload if present (OPTIONAL)
            if file_data and file_data.filename:
                try:
                    # Validate file size (30MB limit)
                    file_data.seek(0, 2)  # Seek to end
                    file_size = file_data.tell()
                    file_data.seek(0)  # Reset to beginning
                    
                    MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB
                    if file_size > MAX_FILE_SIZE:
                        return jsonify({
                            'success': False, 
                            'error': f'File too large. Maximum size is 10MB'
                        })
                    
                    # Create secure filename
                    filename = secure_filename(file_data.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    # Save file to disk
                    user_folder = os.path.join('projects_data', f"user_{current_user.id}")
                    project_folder = os.path.join(user_folder, f"project_{project_id}")
                    os.makedirs(project_folder, exist_ok=True)
                    
                    filepath = os.path.join(project_folder, unique_filename)
                    file_data.save(filepath)
                    
                    # Save file record to database
                    project_file = ProjectFile(
                        project_id=project_id,
                        filename=filename,
                        file_path=filepath,
                        file_type=filename.split('.')[-1].lower() if '.' in filename else '',
                        file_size=file_size,
                        uploaded_by=current_user.id,
                    )
                    
                    db.session.add(project_file)
                    db.session.flush()  # Get the file ID without committing
                    file_id = project_file.id
                    
                    print(f"DEBUG CLIENT SEND: File saved - ID: {file_id}, Name: {filename}")
                    
                except Exception as file_error:
                    print(f"DEBUG CLIENT SEND: File upload error: {str(file_error)}")
                    # Don't fail the whole request if file upload fails
                    # Continue without file attachment
            
            # Save the message (with or without file)
            project_msg = ProjectMessage(
                project_id=project_id,
                user_id=current_user.id,
                message=message or '[File attached]',
                is_admin=False,  # Client message
                is_seen=False,   # IMPORTANT: Client messages start as unseen by admin
                file_id=file_id  # Link to file if exists
            )
            
            db.session.add(project_msg)
            db.session.commit()
            
            print(f"DEBUG CLIENT SEND: Message saved - ID: {project_msg.id}")
            print(f"DEBUG CLIENT SEND: is_admin: {project_msg.is_admin}")
            print(f"DEBUG CLIENT SEND: is_seen: {project_msg.is_seen}")
            print(f"DEBUG CLIENT SEND: Linked to file: {file_id}")
            
            return jsonify({
                'success': True, 
                'message_id': project_msg.id,
                'has_file': bool(file_id),
                'file_id': file_id,
                'is_admin': False,
                'is_seen': False
            })
        
        return jsonify({'success': False, 'error': 'Invalid action'})
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG CLIENT SEND: Error in api_send_message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})



@docket_bp.route('/get-project-messages/<int:project_id>')
@login_required
def get_project_messages(project_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 401
        
    # Verify user has access to this project
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Load messages with their attached files
    messages = ProjectMessage.query\
        .options(db.joinedload(ProjectMessage.attached_file))\
        .filter_by(project_id=project_id)\
        .order_by(ProjectMessage.created_at.asc())\
        .all()
    
    messages_data = []
    for msg in messages:
        # Determine sender first
        if msg.is_admin:
            sender = 'Admin'
        elif msg.user_id == current_user.id:
            sender = 'You'
        else:
            # This shouldn't happen, but just in case
            user = User.query.get(msg.user_id)
            sender = user.first_name if user else 'Unknown'
        
        # Initialize message data - ADD is_seen field
        message_data = {
            'id': msg.id,
            'message': msg.message,
            'is_admin': msg.is_admin,
            'is_seen': msg.is_seen,  # ADD THIS LINE
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'sender': sender
        }
        
        # Handle file logic
        has_file = bool(msg.file_id)
        message_data['has_file'] = has_file
        
        if has_file and msg.attached_file:
            # Check if file is deleted
            if msg.attached_file.is_deleted:
                # File exists but is deleted
                message_data['has_file'] = False
                message_data['file_deleted'] = True
                message_data['file_was_deleted'] = True
                message_data['original_filename'] = msg.attached_file.filename
            else:
                # File exists and is NOT deleted
                file = msg.attached_file
                message_data['file'] = {
                    'id': file.id,
                    'filename': file.filename,
                    'file_type': file.file_type,
                    'file_size': file.file_size,
                    'uploaded_at': file.uploaded_at.strftime('%Y-%m-%d %H:%M') if file.uploaded_at else None,
                    'is_deleted': file.is_deleted
                }
                message_data['has_file'] = True
        elif has_file and not msg.attached_file:
            # file_id exists but file record doesn't (orphaned)
            message_data['has_file'] = False
            message_data['file_missing'] = True
        
        messages_data.append(message_data)
    
    return jsonify(messages_data)




@docket_bp.route('/get-project-files/<int:project_id>/files')
@login_required
def get_project_files(project_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 401
        
    # Verify user has access to this project
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    files = ProjectFile.query.filter_by(project_id=project_id, is_deleted=False)\
        .order_by(desc(ProjectFile.uploaded_at))\
        .all()
    
    files_data = []
    for file in files:
        # Determine if file was sent by current user or received from someone else
        is_sent_by_me = file.uploaded_by == current_user.id
        
        # Get uploader name (you might need to query the User table)
        uploader_name = "You" if is_sent_by_me else "Other User"
        
        # If you have a User model, you can get the actual name:
        # uploader = User.query.get(file.uploaded_by)
        # uploader_name = uploader.name if uploader else "Unknown"
        
        files_data.append({
            'id': file.id,
            'filename': file.filename,
            'file_type': file.file_type,
            'file_size': file.file_size,
            'uploaded_at': file.uploaded_at.strftime('%Y-%m-%d %H:%M'),
            'uploaded_by': uploader_name,
            'description': file.description if hasattr(file, 'description') else '',
            'is_sent_by_me': is_sent_by_me
        })
    
    return jsonify(files_data)





@docket_bp.route('/api/project/<int:project_id>')
@login_required
def get_project_details(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify({
        'id': project.id,
        'name': project.name,
        'user_id': project.user_id,
        'ref_id': project.ref_id,
        'description': project.description,
        'due_date': project.due_date.isoformat(),
        'status': project.status,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat()


    })




@docket_bp.route('/download-project-file/<int:file_id>')
@login_required
def download_project_file(file_id):
    current_user = get_current_user()
    if not current_user:
        return "Unauthorized", 401
        
    file_record = ProjectFile.query.get_or_404(file_id)
    
    # Verify user has access to this file
    project = Project.query.get_or_404(file_record.project_id)
    if project.user_id != current_user.id:
        return "Unauthorized", 403
    
    directory = os.path.dirname(file_record.file_path)
    filename = os.path.basename(file_record.file_path)
    
    return send_from_directory(directory, filename, as_attachment=True)







@docket_bp.route('/api/delete-project/<int:project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        # # Delete related records
        # ProjectMessage.query.filter_by(project_id=project_id).delete()
        # ProjectFile.query.filter_by(project_id=project_id).delete()
        
        # # Delete project
        # db.session.delete(project)
        project.is_deleted = True
        project.updated_at = datetime.utcnow()
        project.status = 'deleted'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@docket_bp.route('/api/project/<int:project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        project.status = 'completed'
        project.updated_at = datetime.utcnow()

        db.session.commit()
        return jsonify({'success': True, 'message': 'Project completed successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})




@docket_bp.route('/delete-project-file/<int:fileID>', methods=['DELETE'])
@login_required
def delete_project_file(fileID):
    try:
        current_user = get_current_user()
        file_record = ProjectFile.query.get_or_404(fileID)
        
        # Verify user has access to this file
        project = Project.query.get_or_404(file_record.project_id)

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        file_record.is_deleted = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'File deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})



@docket_bp.route('/api/project/<int:project_id>/share-link', methods=['GET'])
@login_required
def get_share_link(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        # Generate share token (you can use JWT or simple token)
        import secrets
        token = secrets.token_urlsafe(16)
        
        # Store token in database (optional)
        share_link = f"{request.host_url}share/project/{token}"
        
        return jsonify({
            'success': True, 
            'share_link': share_link,
            'token': token
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/api/project/<int:project_id>/status', methods=['PUT'])
@login_required
def update_project_status(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['active', 'on_hold', 'completed', 'cancelled']:
            return jsonify({'success': False, 'error': 'Invalid status'})
        
        project.status = status
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Status updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})















# Helper function to send due date reminders
def send_due_date_reminder(project, days_until_due):
    # from app import mail
    # from flask_mail import Message
    
    try:
        # Send to admin
        admin_email = "admin@yourfirm.com"  # Replace with actual admin email
        
        admin_msg = Message(
            subject=f'Project Due Date Reminder: {project.ref_id}',
            recipients=[admin_email],
            body=f"""
            Project: {project.name}
            Reference ID: {project.ref_id}
            Client: {project.user.first_name} {project.user.last_name}
            Due Date: {project.due_date}
            Days Remaining: {days_until_due} days
            
            Please check the project deliverables.
            """
        )
        # mail.send(admin_msg)
        
        # Send to client if enabled
        if project.user.email_notifications:
            client_msg = Message(
                subject=f'Your Project Due Date Reminder: {project.ref_id}',
                recipients=[project.user.email],
                body=f"""
                Dear {project.user.first_name},
                
                This is a reminder that your project "{project.name}" is due in {days_until_due} days.
                Due Date: {project.due_date}
                Reference ID: {project.ref_id}
                
                Please ensure all requirements are met before the due date.
                
                Best regards,
                Your Team
                """
            )
            # mail.send(client_msg)
        
        # Log the notification
        notification = ProjectNotification(
            project_id=project.id,
            notification_type='due_date_reminder',
            days_before=days_until_due,
            recipient_email=project.user.email
        )
        db.session.add(notification)
        db.session.commit()
        
    except Exception as e:
        print(f"Failed to send reminder email: {e}")
        db.session.rollback()

def send_project_notification_email(project_id, notification_type, user):
    # Implement email sending logic here
    pass





@docket_bp.route('/get-project-statistics', methods=['GET'])
@login_required
def get_project_statistics():
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'})
    
    try:
        # Get all projects for the user
        projects = Project.query.filter_by(user_id=current_user.id, is_deleted=False).all()
        
        total_projects = len(projects)
        
        # Calculate active projects (not completed and not overdue)
        active_projects = 0
        overdue_projects = 0
        completed_projects = 0
        new_messages = 0
        
        today = datetime.utcnow().date()
        
        for project in projects:
            if project.status and project.status.lower() == 'completed':
                completed_projects += 1
            else:
                if project.due_date:
                    days_until_due = (project.due_date - today).days
                    if days_until_due < 0:
                        overdue_projects += 1
                    else:
                        active_projects += 1
                else:
                    active_projects += 1
            
            # FIXED: Count new messages using is_seen
            project_new_messages = ProjectMessage.query.filter_by(
                project_id=project.id,
                is_admin=True,
                is_seen=False  # Using your actual field name
            ).count()
            new_messages += project_new_messages
        
        return jsonify({
            'success': True,
            'total': total_projects,
            'active': active_projects,
            'overdue': overdue_projects,
            'completed': completed_projects,
            'new_messages': new_messages
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/get-all-projects', methods=['GET'])
@login_required
def get_all_projects():
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'})
    
    try:
        projects = Project.query.filter_by(user_id=current_user.id, is_deleted=False)\
            .order_by(desc(Project.created_at))\
            .all()
        
        projects_data = []
        for project in projects:
            # Calculate days until due
            days_until_due = project.get_days_until_due()
            
            # Get file count
            file_count = ProjectFile.query.filter_by(
                project_id=project.id, 
                is_deleted=False
            ).count()
            
            # FIXED: Get new messages count using is_seen
            new_messages_count = ProjectMessage.query.filter_by(
                project_id=project.id,
                is_admin=True,
                is_seen=False  # Using your actual field name
            ).count()
            
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'ref_id': project.ref_id,
                'description': project.description,
                'due_date': project.due_date.isoformat() if project.due_date else None,
                'status': project.status,
                'created_at': project.created_at.isoformat() if project.created_at else None,
                'days_until_due': days_until_due,
                'file_count': file_count,
                'new_messages_count': new_messages_count,
                'has_new_messages': new_messages_count > 0
            })
        
        # Get statistics
        stats_response = get_project_statistics()
        stats_data = json.loads(stats_response.get_data(as_text=True))
        
        return jsonify({
            'success': True,
            'projects': projects_data,
            'statistics': stats_data if stats_data['success'] else {}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/get-project-info/<int:project_id>')
@login_required
def get_project_info(project_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'})
    
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized access'})
        
        # Get file count
        file_count = ProjectFile.query.filter_by(
            project_id=project.id, 
            is_deleted=False
        ).count()
        
        project_data = {
            'id': project.id,
            'name': project.name,
            'ref_id': project.ref_id,
            'description': project.description,
            'due_date': project.due_date.isoformat() if project.due_date else None,
            'status': project.status,
            'created_at': project.created_at.isoformat() if project.created_at else None,
            'updated_at': project.updated_at.isoformat() if project.updated_at else None,
            'file_count': file_count
        }
        
        return jsonify({
            'success': True,
            'project': project_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/api/mark-messages-seen/<int:project_id>', methods=['POST'])
@login_required
def mark_messages_seen(project_id):
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Verify project access
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        # FIXED: Actually mark admin messages as seen using is_seen
        messages_to_mark = ProjectMessage.query.filter_by(
            project_id=project_id,
            is_admin=True,
            is_seen=False  # Using your actual field name
        ).all()
        
        for message in messages_to_mark:
            message.is_seen = True  # Use your field name
            message.seen_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'count': len(messages_to_mark),
            'message': f'Marked {len(messages_to_mark)} messages as seen'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/api/project/<int:project_id>/reopen', methods=['POST'])
@login_required
def reopen_project(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        project.status = 'active'
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project reopened successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/api/project/<int:project_id>/request-extension', methods=['POST'])
@login_required
def request_extension(project_id):
    try:
        current_user = get_current_user()
        project = Project.query.get_or_404(project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        new_due_date = data.get('due_date')
        reason = data.get('reason')
        
        if not new_due_date:
            return jsonify({'success': False, 'error': 'New due date is required'})
        
        # Here you would typically:
        # 1. Save the extension request to the database
        # 2. Send a notification to the admin
        # 3. Maybe send an email
        
        # For now, just return success
        return jsonify({
            'success': True, 
            'message': 'Extension request sent to admin'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/upload-project-file/<int:project_id>', methods=['POST'])
@login_required
def upload_project_file(project_id):
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Verify project access
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Create secure filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        
        # Save file to disk
        user_folder = os.path.join('projects_data', f"user_{current_user.id}")
        project_folder = os.path.join(user_folder, f"project_{project_id}")
        os.makedirs(project_folder, exist_ok=True)
        
        filepath = os.path.join(project_folder, unique_filename)
        file.save(filepath)
        
        # Save file record to database
        project_file = ProjectFile(
            project_id=project_id,
            filename=filename,
            file_path=filepath,
            file_type=filename.split('.')[-1].lower() if '.' in filename else '',
            file_size=os.path.getsize(filepath),
            uploaded_by=current_user.id,
            description=request.form.get('description', '')
        )
        
        db.session.add(project_file)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'file_id': project_file.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@docket_bp.route('/download-all-project-files/<int:project_id>')
@login_required
def download_all_project_files(project_id):
    current_user = get_current_user()
    if not current_user:
        return "Unauthorized", 401
        
    # Verify project access
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return "Unauthorized", 403
    
    # For now, just redirect to the first file or show a message
    # You would need to implement zip file creation here
    return "File download functionality coming soon!", 200



@docket_bp.route('/debug-message-status/<int:project_id>')
@login_required
def debug_message_status(project_id):
    """Debug route to check message statuses"""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 401
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    messages = ProjectMessage.query.filter_by(project_id=project_id).all()
    
    debug_info = {
        'project_id': project_id,
        'project_name': project.name,
        'total_messages': len(messages),
        'admin_messages': {
            'total': sum(1 for m in messages if m.is_admin),
            'unseen': sum(1 for m in messages if m.is_admin and not m.is_seen),
            'seen': sum(1 for m in messages if m.is_admin and m.is_seen)
        },
        'client_messages': {
            'total': sum(1 for m in messages if not m.is_admin),
            'unseen': sum(1 for m in messages if not m.is_admin and not m.is_seen),
            'seen': sum(1 for m in messages if not m.is_admin and m.is_seen)
        },
        'messages': [
            {
                'id': m.id,
                'is_admin': m.is_admin,
                'is_seen': m.is_seen,
                'seen_at': m.seen_at.isoformat() if m.seen_at else None,
                'message': m.message[:50] + '...' if len(m.message) > 50 else m.message,
                'created_at': m.created_at.isoformat()
            } for m in messages
        ]
    }
    
    return jsonify(debug_info)












































class AdvancedDueDateCalculator:
    def __init__(self):
        self.us_holidays = holidays.US(years=range(2020, 2030))
        self.deadline_rules = self.load_deadline_rules()
    
    def load_deadline_rules(self):
        """Load all USPTO deadline rules"""
        return {
            'patent': {
                'office_action_response': {'days': 180, 'extensions': [1, 2, 3, 4, 5]},
                'issue_fee_payment': {'days': 90, 'grace_period': 180},
                'maintenance_1': {'years': 3.5, 'grace_period': 180},
                'maintenance_2': {'years': 7.5, 'grace_period': 180},
                'maintenance_3': {'years': 11.5, 'grace_period': 180},
                'petition_fee': {'days': 30},
                'appeal_brief': {'days': 60},
                'rce_filing': {'days': 30}
            },
            'trademark': {
                'office_action_response': {'days': 180, 'extensions': [6]},
                'statement_of_use': {'days': 180, 'extensions': [6, 6, 6, 6, 6]},
                'renewal': {'years': 10, 'grace_period': 180},
                'section_8': {'years': 6, 'grace_period': 180},
                'section_15': {'years': 5}
            }
        }
    
    def calculate_all_deadlines(self, case_data, new_status):
        """Calculate all applicable deadlines based on status change"""
        deadlines = []
        app_type = case_data['type']
        
        if new_status == 'OFFICE ACTION RECEIVED':
            deadline = self.calculate_office_action_deadline(case_data['filing_date'])
            deadlines.append({
                'type': 'office_action_response',
                'due_date': deadline,
                'trigger_event': 'Office Action Received',
                'statutory_period': '6 months'
            })
        
        elif new_status == 'NOTICE OF ALLOWANCE':
            deadline = self.calculate_issue_fee_deadline(datetime.now().date())
            deadlines.append({
                'type': 'issue_fee_payment',
                'due_date': deadline,
                'trigger_event': 'Notice of Allowance',
                'statutory_period': '3 months'
            })
        
        elif new_status == 'GRANTED':
            # Calculate all maintenance fees
            maintenance_dates = self.calculate_maintenance_fees(datetime.now().date())
            for i, (period, date) in enumerate(maintenance_dates.items(), 1):
                deadlines.append({
                    'type': f'maintenance_fee_{i}',
                    'due_date': date,
                    'trigger_event': 'Patent Grant',
                    'statutory_period': f'{3.5 * i} years'
                })
        
        elif new_status == 'PUBLISHED':
            if app_type == 'trademark':
                soi_deadline = self.calculate_statement_of_use_deadline(datetime.now().date())
                deadlines.append({
                    'type': 'statement_of_use',
                    'due_date': soi_deadline,
                    'trigger_event': 'Notice of Allowance',
                    'statutory_period': '6 months'
                })
        
        return deadlines
    
    def adjust_for_business_days(self, date):
        """Adjust date to ensure it's a business day"""
        while self.is_weekend(date) or self.is_holiday(date):
            date += timedelta(days=1)
        return date
    
    def get_notification_dates(self, due_date, preferences=[30, 14, 7]):
        """Calculate notification dates considering weekends"""
        notification_dates = []
        for days_before in preferences:
            notification_date = due_date - timedelta(days=days_before)
            # If notification falls on weekend, send on previous Friday
            if self.is_weekend(notification_date):
                days_to_friday = (notification_date.weekday() - 4) % 7
                notification_date -= timedelta(days=days_to_friday)
            notification_dates.append(notification_date)
        return notification_dates
    
    def is_weekend(self, date):
        return date.weekday() >= 5
    
    def is_holiday(self, date):
        return date in self.us_holidays

class NotificationEngine:
    def __init__(self):
        self.email_config = {
            'smtp_server': 'smtp.gmail.com',
            'port': 587,
            'sender_email': 'docketmaster@yourfirm.com',
            'password': 'your_password'
        }
    
    def send_notification(self, recipient, subject, message, notification_type):
        """Send email notification"""

        return False
    
    def generate_status_change_message(self, case_data, old_status, new_status):
        """Generate message for status change notifications"""
        return f"""
        <h3>Status Update: {case_data['title']}</h3>
        <p><strong>Case:</strong> {case_data['application_number']}</p>
        <p><strong>Previous Status:</strong> {old_status}</p>
        <p><strong>New Status:</strong> {new_status}</p>
        <p><strong>Update Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
        <p>Please check the DocketMaster system for updated deadlines and actions.</p>
        """

# Initialize services

calculator = AdvancedDueDateCalculator()
notifier = NotificationEngine()

# API Routes
@docket_bp.route('/api/automation/status', methods=['GET'])
def get_automation_status():
    """Get current automation status"""
    return jsonify({
        'uspto_scraping': 'Running',
        'last_scrape': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'notifications_sent_today': 8,
        'cases_updated_today': 12
    })

@docket_bp.route('/api/cases/<int:case_id>/deadlines', methods=['GET'])
def get_case_deadlines(case_id):
    """Get all deadlines for a case"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('''
        SELECT * FROM deadlines 
        WHERE case_id = %s 
        ORDER BY due_date
    ''', (case_id,))
    deadlines = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(deadlines)

@docket_bp.route('/api/notifications/settings', methods=['POST'])
def update_notification_settings():
    """Update notification preferences"""
    data = request.json
    user_id = data['user_id']
    preferences = data.get('preferences', [30, 14, 7])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET notification_preferences = %s 
        WHERE id = %s
    ''', (','.join(map(str, preferences)), user_id))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'Notification preferences updated'})

# Helper Functions
def update_case_status(case_id, new_status):
    """Update case status and trigger deadline calculations"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get current case data
    cursor.execute('SELECT * FROM cases WHERE id = %s', (case_id,))
    case = cursor.fetchone()
    
    if case:
        # Calculate new deadlines based on status change
        deadlines = calculator.calculate_all_deadlines(case, new_status)
        
        # Update case status
        cursor.execute('''
            UPDATE cases SET status = %s, last_updated = %s 
            WHERE id = %s
        ''', (new_status, datetime.now(), case_id))
        
        # Insert new deadlines
        for deadline in deadlines:
            cursor.execute('''
                INSERT INTO deadlines (case_id, deadline_type, due_date, trigger_event, statutory_period)
                VALUES (%s, %s, %s, %s, %s)
            ''', (case_id, deadline['type'], deadline['due_date'], 
                  deadline['trigger_event'], deadline['statutory_period']))
        
        # Log status change
        cursor.execute('''
            INSERT INTO status_history (case_id, old_status, new_status, change_date)
            VALUES (%s, %s, %s, %s)
        ''', (case_id, case['status'], new_status, datetime.now()))
        
        # Send status change notification
        send_status_change_notification(case, case['status'], new_status)
    
    conn.commit()
    cursor.close()
    conn.close()

def send_due_date_notifications():
    """Send due date notifications based on user preferences"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get upcoming deadlines with user preferences
    cursor.execute('''
        SELECT d.*, c.title, c.application_number, u.email, u.notification_preferences
        FROM deadlines d
        JOIN cases c ON d.case_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE d.due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
        AND d.notification_sent = FALSE
    ''')
    upcoming_deadlines = cursor.fetchall()
    
    for deadline in upcoming_deadlines:
        days_until = (deadline['due_date'] - datetime.now().date()).days
        prefs = [int(p) for p in deadline['notification_preferences'].split(',')]
        
        if days_until in prefs:
            # Send notification
            subject = f"Deadline Reminder: {deadline['title']}"
            message = f"""
            <h3>Upcoming Deadline Alert</h3>
            <p><strong>Case:</strong> {deadline['title']} ({deadline['application_number']})</p>
            <p><strong>Deadline Type:</strong> {deadline['deadline_type']}</p>
            <p><strong>Due Date:</strong> {deadline['due_date']} (in {days_until} days)</p>
            <p><strong>Trigger Event:</strong> {deadline['trigger_event']}</p>
            <p>Please take appropriate action before the deadline.</p>
            """
            
            if notifier.send_notification(deadline['email'], subject, message, 'deadline_reminder'):
                # Mark as sent
                cursor.execute('''
                    UPDATE deadlines SET notification_sent = TRUE 
                    WHERE id = %s
                ''', (deadline['id'],))
    
    conn.commit()
    cursor.close()
    conn.close()

def send_status_change_notification(case, old_status, new_status):
    """Send notification for status changes"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT email FROM users WHERE id = %s', (case['user_id'],))
    user = cursor.fetchone()
    
    if user:
        subject = f"Status Change: {case['title']}"
        message = notifier.generate_status_change_message(case, old_status, new_status)
        
        notifier.send_notification(user['email'], subject, message, 'status_change')
    
    cursor.close()
    conn.close()




@docket_bp.route('/profile')
@login_required
def user_profile():
    # Get user statistics
    user_Id = get_current_user_id()
    total_cases = Case.query.filter_by(user_id=user_Id).count()
    
    active_statuses = [CaseStatus.FILED.value, CaseStatus.PENDING.value, 
                      CaseStatus.EXAMINATION.value, CaseStatus.APPEAL.value]
    active_cases = Case.query.filter_by(user_id=user_Id).filter(
        Case.status.in_(active_statuses)
    ).count()
    
    pending_deadlines = Deadline.query.join(Case).filter(
        Case.user_id == user_Id,
        Deadline.status == 'pending'
    ).count()

    total_uploads = UploadedFile.query.filter_by(user_id=user_Id).count()
    
    # Get case type distribution
    case_distribution = db.session.query(
        Case.type, db.func.count(Case.id)
    ).filter_by(user_id=user_Id).group_by(Case.type).all()
    case_distribution = {str(t[0].value): t[1] for t in case_distribution}
    
    # Prepare data for chart
    case_type_labels = []
    case_type_counts = []
    type_colors = {}
    type_colors_list = []
    
    # Define colors for each case type
    colors = {
        'patent': '#4e73df',
        'trademark': '#1cc88a',
        'design_patent': '#f6c23e',
        'pct_application': '#36b9cc'
    }
    
    for case_type in CaseType:
        label = case_type.value.replace('_', ' ').title()
        count = case_distribution.get(case_type.value, 0)
        color = colors.get(case_type.value, '#858796')
        
        case_type_labels.append(label)
        case_type_counts.append(count)
        type_colors[case_type.value] = color
        type_colors_list.append(color)
    
    # Get recent activities
    recent_activities = get_recent_activities(user_Id)
    
    # Get project count
    total_projects = Project.query.filter_by(
        user_id=user_Id, 
        is_deleted=False
    ).count()
    user_name = session.get('user_name', 'User')

    return render_template('user_profile.html',
                         current_user=get_current_user(),
                         user_name=user_name,
                         total_cases=total_cases,
                         active_cases=active_cases,
                         pending_deadlines=pending_deadlines,
                         total_uploads=total_uploads,
                         case_distribution=case_distribution,
                         case_type_labels=case_type_labels,
                         case_type_counts=case_type_counts,
                         type_colors=type_colors,
                         type_colors_list=type_colors_list,
                         recent_activities=recent_activities,
                         total_projects=total_projects)



def get_recent_activities(user_id, limit=5):
    """Get recent user activities"""
    activities = []
    
    # Get recent case updates
    recent_cases = Case.query.filter_by(user_id=user_id)\
        .order_by(Case.updated_at.desc()).limit(limit).all()
    
    for case in recent_cases:
        activities.append({
            'type': 'case',
            'title': f'Case Updated: {case.case_number}',
            'description': f'{case.title}',
            'timestamp': case.updated_at
        })
    
    # Get recent uploads if we don't have enough cases
    if len(activities) < limit:
        recent_uploads = UploadedFile.query.filter_by(user_id=user_id)\
            .order_by(UploadedFile.upload_date.desc())\
            .limit(limit - len(activities)).all()
        
        for upload in recent_uploads:
            activities.append({
                'type': 'upload',
                'title': f'File Uploaded: {upload.original_filename}',
                'description': f'{upload.file_type.value.upper()} file processed',
                'timestamp': upload.upload_date
            })
    
    # Get recent project updates if still need more
    if len(activities) < limit:
        recent_projects = Project.query.filter_by(user_id=user_id, is_deleted=False)\
            .order_by(Project.updated_at.desc())\
            .limit(limit - len(activities)).all()
        
        for project in recent_projects:
            activities.append({
                'type': 'project',
                'title': f'Project Updated: {project.name}',
                'description': f'Ref: {project.ref_id}',
                'timestamp': project.updated_at
            })
    
    return activities[:limit]


def allowed_image_file(filename):
    """Check if the file is an allowed image type"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_user_directory(user_id):
    """Create user directory if it doesn't exist"""
    user_dir = os.path.join(current_app.root_path, 'static', 'user_data', str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
    return user_dir



@docket_bp.route('/profile/update', methods=['POST'])  # Add leading slash
@login_required
def update_profile():
    try:
        data = request.form.to_dict()
        
        # Get current user from session
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 401
        
        # Update basic profile information
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.phone = data.get('phone', user.phone)
        user.timezone = data.get('timezone', user.timezone)
        user.email_notifications = 'email_notifications' in data
        user.sms_notifications = 'sms_notifications' in data
        user.auto_sync = 'auto_sync' in data
        
        # Update notification preferences
        notification_days = data.get('notification_days', '30,14,7,1')
        if notification_days:
            try:
                days = [int(d.strip()) for d in notification_days.split(',')]
                days = sorted(set(days))
                user.notification_preferences = ','.join(map(str, days))
            except ValueError:
                user.notification_preferences = '30,14,7,1'
        
        db.session.commit()
        
        # Update session user name if changed
        session['user_name'] = f"{user.first_name} {user.last_name}"
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating profile: {str(e)}'
        }), 500


@docket_bp.route('profile/upload-image', methods=['POST'])
@login_required  # Your custom decorator
def upload_profile_image():
    try:
        if 'profile_image' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file uploaded'
            }), 400
        
        file = request.files['profile_image']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            }), 400
        
        if not allowed_image_file(file.filename):
            return jsonify({
                'success': False,
                'message': 'File type not allowed. Please upload PNG, JPG, JPEG, GIF, or WEBP'
            }), 400
        
        # Get current user
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 401
        
        # Create user directory
        user_dir = ensure_user_directory(user_id)
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"profile_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Save file
        file_path = os.path.join(user_dir, unique_filename)
        file.save(file_path)
        
        # Delete old profile image if exists
        if hasattr(user, 'profile_image') and user.profile_image:
            old_image_path = os.path.join(current_app.root_path, 'static', user.profile_image.lstrip('/'))
            if os.path.exists(old_image_path):
                try:
                    os.remove(old_image_path)
                except:
                    pass
        
        # Update user record with image path
        relative_path = f"/static/user_data/{user_id}/{unique_filename}"
        
        # Add profile_image field to User model if not exists
        if hasattr(user, 'profile_image'):
            user.profile_image = relative_path
        else:
            # If you haven't added the field to model, you can store it in a separate table
            # For now, just return the path
            pass
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile image uploaded successfully',
            'image_url': relative_path
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error uploading image: {str(e)}'
        }), 500



# Helper route to get current user data
@docket_bp.route('profile/data')
@login_required  # Your custom decorator
def get_profile_data():
    """Get current user profile data"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 401
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone or '',
            'timezone': user.timezone,
            'email_notifications': user.email_notifications,
            'sms_notifications': user.sms_notifications,
            'auto_sync': user.auto_sync,
            'notification_preferences': user.notification_preferences,
            'profile_image': getattr(user, 'profile_image', None)
        }
    })

@docket_bp.route('/docket/profile/change-password', methods=['POST'])
@login_required  # Your custom decorator
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            return jsonify({
                'success': False,
                'message': 'All password fields are required'
            }), 400
        
        # Get current user
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 401
        
        # Verify current password
        hashed_current = hash_password(current_password)
        if hashed_current != user.password:
            return jsonify({
                'success': False,
                'message': 'Current password is incorrect'
            }), 400
        
        # Check if new passwords match
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': 'New passwords do not match'
            }), 400
        
        # Check password strength
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'Password must be at least 8 characters long'
            }), 400
        
        # Update password
        hashed_new = hash_password(new_password)
        user.password = hashed_new
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error changing password: {str(e)}'
        }), 500













