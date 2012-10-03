# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
from gaesessions import SessionMiddleware
def webapp_add_wsgi_middleware(app):
    app = SessionMiddleware(app, cookie_key="5VQUvnDP6GuQbZfPaLai39s4Ou8RpM3DMbSs2wIewQTCvwcsUK", lifetime=datetime.timedelta(hours=2))
    return app