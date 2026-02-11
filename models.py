# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import validates



db = SQLAlchemy()

class Base(db.Model):
    __abstract__ = True

class pages(Base):
    Srno = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    title = db.Column(db.String(50))
    bg = db.Column(db.String(50))
    sub = db.Column(db.String(50))
    content = db.Column(db.Text)
    sam1 = db.Column(db.String(50))
    sam2 = db.Column(db.String(50))
    sam3 = db.Column(db.String(50))    
    content2 = db.Column(db.Text)
    link = db.Column(db.String(50))

# Add other models (blogs, query) similarly...

# Pulling data For BLOGS 

class blogs(Base):
    meta = db.Column(db.String(50), primary_key = False)
    srno = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(50), primary_key = False)
    image = db.Column(db.String(50), primary_key = False)
    category = db.Column(db.String(50), primary_key = False)
    author = db.Column(db.String(50), primary_key = False)
    author_img = db.Column(db.String(50), primary_key = False)
    content = db.Column(db.Text, primary_key = False)
    link = db.Column(db.String(50), primary_key = False)
    date = db.Column(db.DateTime, primary_key = False)

# DB class For querry model 

class query(Base):
    srno = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String, primary_key = False)
    email = db.Column(db.String, primary_key = False)
    subject = db.Column(db.String, primary_key = False)
    message = db.Column(db.String, primary_key = False)


# DB class For testomony 

class testomony(Base):
    srno = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String, primary_key = False)
    image = db.Column(db.String, primary_key = False)
    designaiton = db.Column(db.String, primary_key = False)
    stars = db.Column(db.Integer, primary_key = False)
    content = db.Column(db.Text, primary_key = False)
    video = db.Column(db.String, primary_key = False)
    date = db.Column(db.DateTime, primary_key = False)


class campaignrecipient(Base):
    recipient_id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    email = db.Column(db.String, primary_key = False)
    first_name = db.Column(db.String, primary_key = False)
    last_name = db.Column(db.Text, primary_key = False)
    custom_id = db.Column(db.Text, primary_key = False)
    sent = db.Column(db.Boolean, primary_key = False, default=False, nullable=False)










# models.py
class Template(Base): 
    __tablename__ = 'template'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class Contact(Base):
    __tablename__ = 'contact'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    custom_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    datasets = db.relationship('DatasetContact', back_populates='contact')
    campaign_recipients = db.relationship('CampaignRecipient', back_populates='contact')
    unsubscribes = db.relationship('Unsubscriber', back_populates='contact')
    
    @validates('email')
    def validate_email(self, key, email):
        if not email or '@' not in email:
            raise ValueError("Invalid email address")
        return email.lower().strip()

class Unsubscriber(Base):
    __tablename__ = 'unsubscriber'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', back_populates='unsubscribes')
    campaign = db.relationship('Campaign')

class Dataset(Base):
    __tablename__ = 'dataset'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    record_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    contacts = db.relationship('DatasetContact', back_populates='dataset')
    campaigns = db.relationship('Campaign', back_populates='dataset')


# The relationship b/w the dataset and contact
class DatasetContact(Base):
    __tablename__ = 'dataset_contact'
    
    dataset_id = db.Column(db.Integer, db.ForeignKey('dataset.id'), primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    dataset = db.relationship('Dataset', back_populates='contacts')
    contact = db.relationship('Contact', back_populates='datasets')

class Campaign(Base):
    __tablename__ = 'campaign'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    sender_email = db.Column(db.String(255), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey('dataset.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    next_run = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('active', 'paused', 'completed', name='status_enum'), 
                      default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completion = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Relationships
    emails = db.relationship('CampaignEmail', backref='campaign', cascade='all, delete-orphan', order_by='CampaignEmail.sequence_order')
    dataset = db.relationship('Dataset', back_populates='campaigns')
    recipients = db.relationship('CampaignRecipient', back_populates='campaign')
    unsubscribes = db.relationship('Unsubscriber', back_populates='campaign')

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "next_run": self.next_run,
            "completion": self.completion,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset.name if self.dataset else None,
            "emails": [email.to_dict() for email in self.emails],  # optional
            "recipient_count": len(self.recipients),
            "unsubscribes": len(self.unsubscribes),
        }
    
    @validates('sender_email')
    def validate_sender_email(self, key, email):
        if not email or '@' not in email:
            raise ValueError("Invalid sender email")
        return email.lower().strip()


class CampaignEmail(db.Model):
    __tablename__ = 'campaignemail'
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'))
    subject = db.Column(db.String(255), nullable=False)
    delay_days = db.Column(db.Integer, nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False, default=0)
    # Relationships
    template = db.relationship('Template', backref='campaign_emails')

    def to_dict(self):
            return {
                "id": self.id,
                "campaign_id": self.campaign_id,
                "template_id": self.template_id,
                "template_name": self.template.name if self.template else None,
                "subject": self.subject,
                "delay_days": self.delay_days,
                "sequence_order": self.sequence_order
            }


class CampaignRecipient(Base):
    __tablename__ = 'campaign_recipient'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    email_index = db.Column(db.Integer, nullable=False)
    sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    opened = db.Column(db.Boolean, default=False)
    opened_at = db.Column(db.DateTime)
    unsubscribed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = db.relationship('Campaign', back_populates='recipients')
    contact = db.relationship('Contact', back_populates='campaign_recipients')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'contact_id', name='_campaign_contact_uc'),
    )














# Helper functions for pages 
def content(slug):
    page = pages.query.filter_by(link=slug).first()  # Query your database model (assuming 'pages' is your model)
    return page  # Ensure to return a dictionary

def content_blog(slug):
    return blogs.query.filter_by(link=slug).first()

