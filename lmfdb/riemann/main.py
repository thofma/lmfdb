from lmfdb.base import app
import flask
from flask import render_template, request

mod = flask.Blueprint('riemann', __name__, template_folder="templates")
title = "Riemann zeta function"
