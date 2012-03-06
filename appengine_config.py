import datetime
from gaesessions import SessionMiddleware
def webapp_add_wsgi_middleware(app):
    app = SessionMiddleware(app, cookie_key="5VQUvnDP6GuQbZfPaLai39s4Ou8RpM3DMbSs2wIewQTCvwcsUK", lifetime=datetime.timedelta(hours=2))
    return app