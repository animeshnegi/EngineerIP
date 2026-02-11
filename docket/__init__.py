from flask import Blueprint

docket_bp = Blueprint(
    'docket',
    __name__,
    url_prefix='/docket',
    template_folder='templates/docket',
    static_folder='../static'
)

from . import routes  # Import routes after defining blueprint