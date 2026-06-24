# -*- coding:utf-8 -*-
from flask import Blueprint
from libs.external_api import ExternalApi

bp = Blueprint('service_api', __name__, url_prefix='/v1')
api = ExternalApi(bp)

from .v03 import classify_segment
from .v03 import migrate
from .v03 import recommend

from .common import llms
from .common import embedding
from .common import knowledge

from .biz import upload
from .biz import keywords
from .biz import issuing_level
from .biz import tree
from .biz import document_category
from .biz import document_type
from .biz import agency_issued
from .biz import position
from .biz import industry_sector
from .biz import signer
from .biz import document
from .biz import decree_status
from .biz import resource
from .biz import document_report
from .biz import relationship
from .biz import regulated_object
from .biz import social_relation
from .biz import relationship_article
from .biz import authority
from .biz import effective_update
from .biz import tree_classifier