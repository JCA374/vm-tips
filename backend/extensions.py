"""Flask extensions -- instantiated without app, bound in create_app()."""
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

mail = Mail()
limiter = Limiter(get_remote_address)
