#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由注册入口
"""

from .api import register_api_routes
from .pages import register_page_routes


def register_routes(app):
    """注册所有路由"""
    register_page_routes(app)
    register_api_routes(app)