from models import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, Float, Enum, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum


# Association tables for many-to-many relationships
case_attorney_association = Table('case_attorney_association', db.Model.metadata,
    Column('case_id', Integer, ForeignKey('cases.id')),
    Column('attorney_id', Integer, ForeignKey('attorneys.id'))
)

case_inventor_association = Table('case_inventor_association', db.Model.metadata,
    Column('case_id', Integer, ForeignKey('cases.id')),
    Column('inventor_id', Integer, ForeignKey('inventors.id'))
)

class CaseType(enum.Enum):
    PATENT = "patent"
    TRADEMARK = "trademark"
    DESIGN_PATENT = "design_patent"
    PCT_APPLICATION = "pct_application"

class CaseStatus(enum.Enum):
    DRAFT = "draft"
    FILED = "filed"
    PENDING = "pending"
    EXAMINATION = "examination"
    ALLOWED = "allowed"
    GRANTED = "granted"
    REGISTERED = "registered"
    ABANDONED = "abandoned"
    REJECTED = "rejected"
    APPEAL = "appeal"
    OPPOSITION = "opposition"
    CANCELLATION = "cancellation"

class DeadlineType(enum.Enum):
    OFFICE_ACTION_RESPONSE = "office_action_response"
    ISSUE_FEE_PAYMENT = "issue_fee_payment"
    MAINTENANCE_FEE_1 = "maintenance_fee_1"
    MAINTENANCE_FEE_2 = "maintenance_fee_2"
    MAINTENANCE_FEE_3 = "maintenance_fee_3"
    STATEMENT_OF_USE = "statement_of_use"
    RENEWAL = "renewal"
    SECTION_8 = "section_8"
    SECTION_15 = "section_15"
    APPEAL_BRIEF = "appeal_brief"
    RCE_FILING = "rce_filing"
    PETITION_FEE = "petition_fee"
    PCT_NATIONAL_PHASE = "pct_national_phase"
    PRIORITY_CLAIM = "priority_claim"

class NotificationType(enum.Enum):
    STATUS_CHANGE = "status_change"
    DEADLINE_REMINDER = "deadline_reminder"
    OFFICE_ACTION = "office_action"
    GRANT_NOTICE = "grant_notice"
    MAINTENANCE_REMINDER = "maintenance_reminder"
    RENEWAL_REMINDER = "renewal_reminder"
    SYSTEM_ALERT = "system_alert"



class FileType(enum.Enum):
    PATENT = "patent"
    TRADEMARK = "trademark"

class UploadStatus(enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(Enum(FileType), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(UploadStatus), default=UploadStatus.UPLOADED)
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)

    # Relationships
    user = relationship("User", backref="uploaded_files")
    file_records = relationship("FileRecord", backref="uploaded_file", cascade="all, delete-orphan")

class FileRecord(db.Model):
    __tablename__ = 'file_records'

    id = Column(Integer, primary_key=True)
    uploaded_file_id = Column(Integer, ForeignKey('uploaded_files.id'), nullable=False)
    record_number = Column(String(100), nullable=False)  # Patent/TM number
    scraped_data = Column(Text)  # JSON stored scraped data
    status = Column(Enum(UploadStatus), default=UploadStatus.UPLOADED)
    error_message = Column(Text)
    processed_date = Column(DateTime)

    # Add indexes for better performance
    __table_args__ = (
        db.Index('idx_record_number', 'record_number'),
        db.Index('idx_uploaded_file_status', 'uploaded_file_id', 'status'),
    )



class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(500), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    notification_preferences = Column(String(50), default='30,14,7,1')  # days before
    auto_sync = Column(Boolean, default=True)
    timezone = Column(String(50), default='America/New_York')
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    profile_image = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(50),default='User')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    cases = relationship("Case", back_populates="user")
    notification_logs = relationship("NotificationLog", back_populates="user")

    def get_notification_preferences_list(self):
        return [int(x.strip()) for x in self.notification_preferences.split(',')]

class Attorney(db.Model):
    __tablename__ = 'attorneys'

    id = Column(Integer, primary_key=True, autoincrement=True)
    bar_number = Column(String(50), unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    phone = Column(String(20))
    firm_name = Column(String(255))
    jurisdiction = Column(String(100))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    cases = relationship("Case", secondary=case_attorney_association, back_populates="attorneys")

class Inventor(db.Model):
    __tablename__ = 'inventors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    address = Column(Text)
    citizenship = Column(String(100))
    created_at = Column(DateTime, default=func.now())

    # Relationships
    cases = relationship("Case", secondary=case_inventor_association, back_populates="inventors")

class Case(db.Model):
    __tablename__ = 'cases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_number = Column(String(50), unique=True, nullable=False, index=True)  # Internal case number
    application_number = Column(String(50), nullable=False, index=True)  # USPTO application number
    type = Column(Enum(CaseType), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Filing information
    filing_date = Column(Date, nullable=False, index=True)
    filing_country = Column(String(2), default='US')  #ISO country code
    priority_date = Column(Date)
    priority_number = Column(String(100))

    # Status information
    status = Column(Enum(CaseStatus), default=CaseStatus.DRAFT, index=True)
    uspto_status = Column(String(200))  # Raw status from USPTO
    uspto_last_checked = Column(DateTime)
    uspto_data = Column(Text)  # JSON data from USPTO

    # Important dates
    examination_date = Column(Date)
    publication_date = Column(Date)
    allowance_date = Column(Date)
    grant_date = Column(Date)
    expiration_date = Column(Date)

    # Financial information
    fee_status = Column(Enum('paid', 'unpaid', 'overdue'), default='unpaid')
    estimated_fees = Column(Float, default=0.0)
    actual_fees = Column(Float, default=0.0)

    # Relationships
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    user = relationship("User", back_populates="cases")
    attorneys = relationship("Attorney", secondary=case_attorney_association, back_populates="cases")
    inventors = relationship("Inventor", secondary=case_inventor_association, back_populates="cases")

    # Related objects
    deadlines = relationship("Deadline", back_populates="case", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    office_actions = relationship("OfficeAction", back_populates="case", cascade="all, delete-orphan")
    maintenance_fees = relationship("MaintenanceFee", back_populates="case", cascade="all, delete-orphan")

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_case_type_status', 'type', 'status'),
        Index('idx_case_filing_date', 'filing_date'),
        Index('idx_case_user_status', 'user_id', 'status'),
    )

class Deadline(db.Model):
    __tablename__ = 'deadlines'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    deadline_type = Column(Enum(DeadlineType), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)

    # Date information
    trigger_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    statutory_period = Column(String(100))  # e.g., "6 months", "3 years"

    # Status and tracking
    status = Column(Enum('pending', 'completed', 'overdue', 'extended', 'cancelled'), default='pending', index=True)
    completed_date = Column(Date)
    extended_date = Column(Date)
    extension_days = Column(Integer, default=0)

    # Notification tracking
    notification_sent = Column(Boolean, default=False)
    last_notification_sent = Column(DateTime)

    # Relationships
    case = relationship("Case", back_populates="deadlines")
    notification_logs = relationship("NotificationLog", back_populates="deadline")

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_deadline_due_date_status', 'due_date', 'status'),
        Index('idx_deadline_case_type', 'case_id', 'deadline_type'),
    )

class StatusHistory(db.Model):
    __tablename__ = 'status_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)

    # Status information
    old_status = Column(String(200))
    new_status = Column(String(200), nullable=False)
    status_description = Column(Text)

    # Source information
    source = Column(Enum('uspto_scraper', 'manual', 'system', 'email'), default='system')
    source_reference = Column(String(255))  # URL, document reference, etc.

    # Relationships
    case = relationship("Case", back_populates="status_history")

    # Timestamps
    change_date = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index('idx_status_history_case_date', 'case_id', 'change_date'),
    )

class OfficeAction(db.Model):
    __tablename__ = 'office_actions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)

    # OA information
    oa_number = Column(String(50), nullable=False)
    oa_type = Column(Enum('final', 'non-final', 'advisory', 'examiner', 'restriction'), nullable=False)
    mailing_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False, index=True)

    # Content
    summary = Column(Text)
    rejection_types = Column(String(500))  # JSON array of rejection types
    examiner_name = Column(String(100))
    art_unit = Column(String(10))

    # Response tracking
    response_filed = Column(Boolean, default=False)
    response_date = Column(Date)
    response_document_id = Column(Integer, ForeignKey('documents.id'))

    # Relationships
    case = relationship("Case", back_populates="office_actions")
    response_document = relationship("Document", foreign_keys=[response_document_id])

    # Timestamps
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_oa_case_due_date', 'case_id', 'due_date'),
    )

class MaintenanceFee(db.Model):
    __tablename__ = 'maintenance_fees'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)

    # Fee information
    fee_number = Column(Integer, nullable=False)  # 1, 2, or 3
    due_date = Column(Date, nullable=False, index=True)
    grace_period_end = Column(Date, nullable=False)
    amount = Column(Float)
    small_entity_amount = Column(Float)

    # Payment status
    status = Column(Enum('upcoming', 'due', 'paid', 'overdue', 'grace_period'), default='upcoming')
    paid_date = Column(Date)
    payment_reference = Column(String(100))

    # Relationships
    case = relationship("Case", back_populates="maintenance_fees")

    __table_args__ = (
        Index('idx_mf_case_fee_number', 'case_id', 'fee_number'),
        Index('idx_mf_due_date_status', 'due_date', 'status'),
    )

class Document(db.Model):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)

    # Document information
    document_type = Column(Enum('application', 'office_action', 'response', 'assignment', 'drawings', 'other'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))

    # Metadata
    title = Column(String(255))
    description = Column(Text)
    pages = Column(Integer)

    # USPTO information
    uspto_document_id = Column(String(100))
    filing_date = Column(Date)
    confirmation_number = Column(String(100))

    # Relationships
    case = relationship("Case", back_populates="documents")

    # Timestamps
    uploaded_at = Column(DateTime, default=func.now(), index=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_document_case_type', 'case_id', 'document_type'),
    )

class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    deadline_id = Column(Integer, ForeignKey('deadlines.id'), index=True)

    # Notification details
    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    channel = Column(Enum('email', 'sms', 'in_app', 'webhook'), default='email')
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255))
    message = Column(Text, nullable=False)

    # Status and tracking
    status = Column(Enum('sent', 'delivered', 'failed', 'opened', 'clicked'), default='sent')
    error_message = Column(Text)
    message_id = Column(String(255))  # For email/SMS tracking

    # Relationships
    user = relationship("User", back_populates="notification_logs")
    case = relationship("Case")
    deadline = relationship("Deadline", back_populates="notification_logs")

    # Timestamps
    sent_at = Column(DateTime, default=func.now(), index=True)
    delivered_at = Column(DateTime)
    opened_at = Column(DateTime)

    __table_args__ = (
        Index('idx_notification_sent_at_type', 'sent_at', 'notification_type'),
        Index('idx_notification_user_date', 'user_id', 'sent_at'),
    )

class AutomationLog(db.Model):
    __tablename__ = 'automation_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Task information
    task_name = Column(String(100), nullable=False, index=True)
    task_type = Column(Enum('uspto_scraping', 'deadline_calculation', 'notification', 'maintenance', 'reporting'), nullable=False)

    # Execution details
    execution_time = Column(DateTime, default=func.now(), index=True)
    duration_seconds = Column(Float)
    records_processed = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)

    # Status
    status = Column(Enum('started', 'completed', 'failed', 'partial'), default='completed')
    error_message = Column(Text)
    stack_trace = Column(Text)

    # Additional data
    parameters = Column(Text)  # JSON parameters
    results = Column(Text)  # JSON results

    __table_args__ = (
        Index('idx_automation_task_date', 'task_name', 'execution_time'),
    )

class USPTOApiLog(db.Model):
    __tablename__ = 'uspto_api_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey('cases.id'), index=True)

    # API call details
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), default='GET')
    parameters = Column(Text)  # JSON parameters
    response_status = Column(Integer)
    response_data = Column(Text)  # Raw response data

    # Performance
    response_time_ms = Column(Integer)

    # Relationships
    case = relationship("Case")

    # Timestamps
    requested_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index('idx_uspto_log_case_date', 'case_id', 'requested_at'),
    )

class FeeSchedule(db.Model):
    __tablename__ = 'fee_schedules'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Fee information
    fee_type = Column(String(100), nullable=False, index=True)
    fee_code = Column(String(50))
    amount = Column(Float, nullable=False)
    small_entity_amount = Column(Float)
    micro_entity_amount = Column(Float)

    # Effective dates
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date)

    # Description
    description = Column(Text)
    category = Column(String(100))  # filing, maintenance, extension, etc.

    __table_args__ = (
        Index('idx_fee_type_effective', 'fee_type', 'effective_date'),
    )

class Country(db.Model):
    __tablename__ = 'countries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(2), unique=True, nullable=False)  # ISO code
    name = Column(String(100), nullable=False)
    patent_office_name = Column(String(100))
    trademark_office_name = Column(String(100))
    currency = Column(String(3), default='USD')

    # Timestamps
    created_at = Column(DateTime, default=func.now())

class Configuration(db.Model):
    __tablename__ = 'configurations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(Enum('string', 'integer', 'float', 'boolean', 'json'), default='string')
    description = Column(Text)
    category = Column(String(50), default='general')

    # Timestamps
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

















# Data base models for Project tracking


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    ref_id = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='Other')
    budget = db.Column(db.Float, default=0.0)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    is_deleted = db.Column(db.Boolean, default=False)
    feedback = db.Column(db.Text,nullable=True)
    completion_notes = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="projects")
    messages = relationship("ProjectMessage", back_populates="project", cascade="all, delete-orphan")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")

    def get_days_until_due(self):
        from datetime import date
        return (self.due_date - date.today()).days


class ProjectMessage(db.Model):
    __tablename__ = 'project_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(Text, nullable=False)
    is_admin = Column(Boolean, default=False)  # True if message is from admin
    is_seen = Column(Boolean, default=False, nullable=False)
    file_id = Column(Integer, ForeignKey('project_files.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    # For tracking if client has seen admin messages
    seen_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="messages")
    user = relationship("User")
     # Add this relationship to connect to files
    attached_file = relationship("ProjectFile", foreign_keys=[file_id])

class ProjectFile(db.Model):
    __tablename__ = 'project_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(50))
    file_size = Column(Integer)  # in bytes
    description = Column(Text)
    uploaded_by = Column(Integer, ForeignKey('users.id'))
    uploaded_at = Column(DateTime, default=func.now())
    is_deleted = Column(Boolean, default=False)

    # Relationships

    project = relationship("Project", back_populates="files")
    uploader = relationship("User")


# Add this to track notification sent status
class ProjectNotification(db.Model):
    __tablename__ = 'project_notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    notification_type = Column(String(50))  # 'due_date', 'deliverable', 'reminder'
    sent_at = Column(DateTime, default=func.now())
    days_before = Column(Integer)  # For due date reminders
    recipient_email = Column(String(255))

    project = relationship("Project")



class SharedFile(db.Model):
    __tablename__ = 'shared_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # NULL for guests
    session_id = Column(String(100), nullable=True, index=True)  # For guest users
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), default='other')
    category = Column(String(50), default='other')
    description = Column(Text)
    file_size = Column(Integer, default=0)
    share_token = Column(String(50), unique=True, nullable=False, index=True)
    share_url = Column(String(500))
    download_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    uploader_ip = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_accessed = Column(DateTime)

    # Relationships
    user = relationship("User", backref="shared_files")

    __table_args__ = (
        Index('idx_shared_files_user_id', 'user_id'),
        Index('idx_shared_files_session_id', 'session_id'),
        Index('idx_shared_files_share_token', 'share_token'),
        Index('idx_shared_files_created_at', 'created_at'),
        Index('idx_shared_files_is_deleted', 'is_deleted'),
    )
