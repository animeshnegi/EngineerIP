# campaigns.py
from flask import Blueprint, request, render_template, jsonify, current_app, redirect, url_for, session, flash
from models import db, pages, campaignrecipient
import csv
import os
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from sqlalchemy import text

campaign_bp = Blueprint('campaign', __name__, url_prefix='/campaigns')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}

# CSV Utility Functions
def read_csv():
    csv_file_path = current_app.config['CSV_FILE_PATH']
    data = []
    try:
        with open(csv_file_path, mode='r') as file:
            reader = csv.reader(file)
            header = next(reader)
            data.append(header)
            for row in reader:
                data.append(row)
    except (FileNotFoundError, StopIteration):
        data = [["email", "first_name", "last_name", "custom_id"]]
        write_csv(data)
    return data

def write_csv(data):
    csv_file_path = current_app.config['CSV_FILE_PATH']
    with open(csv_file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)


# [Include all other CSV utility functions here]


def append_csv_data(new_file_path, main_file_path):
    """Appends data from a new CSV file to the main CSV file, skipping header"""
    with open(new_file_path, mode='r') as new_file:
        new_reader = csv.reader(new_file)
        next(new_reader)  # Skip header row of new file
        
        with open(main_file_path, mode='a', newline='') as main_file:
            main_writer = csv.writer(main_file)
            for row in new_reader:
                main_writer.writerow(row)





def delete_row(recipient_id):
    recipient = campaignrecipient.query.get(recipient_id)
    if recipient:
        db.session.delete(recipient)
        db.session.commit()

def remove_recipient_from_db(recipient_id):
    """
    Removes a recipient from the database by their ID.
    """
    recipient = campaignrecipient.query.get(recipient_id)

    db.session.delete(recipient)
    db.session.commit()
    




def empty_csv_file():
    write_csv([])


def read_recipients_from_csv(file_path):
    """
    Reads a CSV file and returns a list of recipients and their data.
    """
    recipients_list = []
    try:
        with open(file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                recipients_list.append({
                    "email": row['email'],
                    "first_name": row['first_name'],
                    "last_name": row['last_name'],
                    "custom_id": row['custom_id']
                })
    except UnicodeDecodeError as e:
        print(f"Error decoding CSV file: {e}")
    return recipients_list




# Email sending functions
def send_email(recipient_id, to_email, first_name, last_name, custom_id, html_template, from_email, subject):
    api_key = current_app.config['API_KEY']
    base_url = current_app.config['BASE_URL']
    
    personalized_body = html_template \
        .replace("{{first_name}}", first_name or '') \
        .replace("{{last_name}}", last_name or '') \
        .replace("{{email}}", to_email or '') \
        .replace("{{custom_id}}", custom_id or '')

    payload = {
        "apikey": api_key,
        "subject": subject,
        "from": from_email,
        "to": to_email,
        "bodyHtml": personalized_body,
        "isTransactional": True
    }
    
    try:
        response = requests.post(base_url, data=payload,timeout=10)
        if response.status_code == 200:
            current_app.logger.info(f"Email sent to {to_email}")
            remove_recipient_from_db(recipient_id)
        else:
            current_app.logger.error(f"Email failed to {to_email}: {response.text}")
    except Exception as e:
        current_app.logger.error(f"Email error: {str(e)}")

@campaign_bp.route('/dashboard', methods=['GET', 'POST'])
def campaign_dashboard():
    if not session.get('admin_logged_in'):
        flash('You must be logged in as admin to view the dashboard.', 'warning')
        return redirect(url_for('main.admin_login', error="To view this page you need to be logged in as admin"))   


    page = pages.query.filter_by(link='camp').first()
    
    if request.method == 'POST':
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                temp_path = os.path.join(upload_folder, filename)
                file.save(temp_path)

                # Open and read CSV, then insert to DB
                with open(temp_path, newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        # Adjust field names as per your model
                        recipient = campaignrecipient(
                            first_name=row.get('first_name', ''),
                            last_name=row.get('last_name', ''),
                            email=row.get('email', ''),
                            custom_id=row.get('custom_id', ''),
                            sent=False 
                        )
                        db.session.add(recipient)

                    db.session.commit()

                os.remove(temp_path)

        # Handle other CSV operations
        action = request.form.get('action')
        if action == 'delete_row':
            recipient_id = request.form.get('recipient_id')
            if recipient_id and recipient_id.isdigit():
                delete_row(int(recipient_id))

        elif action == 'edit_row':
            recipient_id_raw = request.form.get('recipient_id')
            
            if recipient_id_raw and recipient_id_raw.isdigit():
                recipient_id = int(recipient_id_raw)
                recipient = campaignrecipient.query.get(recipient_id)

                if recipient:
                    recipient.email = request.form.get('email', '')
                    recipient.first_name = request.form.get('first_name', '')
                    recipient.last_name = request.form.get('last_name', '')
                    recipient.custom_id = request.form.get('custom_id', '')
                    db.session.commit()
            else:
                flash('Invalid recipient ID provided.', 'danger')


        elif action == 'empty_csv':
            with db.engine.connect() as conn:
                conn.execute(text('DELETE FROM campaignrecipient'))
                conn.execute(text('ALTER TABLE campaignrecipient AUTO_INCREMENT = 1'))
                conn.commit()

        return redirect(url_for('campaign.campaign_dashboard'))
    


    page = request.args.get('page', 1, type=int)
    per_page = 500  # Posts per page

    pagination = campaignrecipient.query.order_by(campaignrecipient.recipient_id.asc()).paginate(page=page, per_page=per_page)
    recipients = pagination.items
    length_recipients = campaignrecipient.query.count()

    return render_template('Camp/dashboard.html', 
                         page=page, 
                         recipients=recipients, 
                         enumerate=enumerate,pagination=pagination, length_recipients=length_recipients)



@campaign_bp.route('/send_campaign', methods=['POST'])
def send_campaign():
    from_email = request.form.get("from_email")
    subject = request.form.get("subject")
    html_content = request.form.get("html_content")

    app = current_app._get_current_object()  # Get actual Flask app instance

    try:
        recipients = campaignrecipient.query.all()

        def send_with_context(recipient):
            with app.app_context():
                send_email(
                    recipient.recipient_id,  
                    recipient.email,
                    recipient.first_name,
                    recipient.last_name,
                    recipient.custom_id,
                    html_content,
                    from_email,
                    subject
                )

        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = [executor.submit(send_with_context, r) for r in recipients]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    app.logger.error(f"Error sending email: {e}")

        return jsonify({"message": "Campaign completed successfully"}), 200

    except Exception as e:
        app.logger.exception("Campaign failed")
        return jsonify({"error": str(e)}), 500