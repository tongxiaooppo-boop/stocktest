#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ui/ — 前端 UI 模組（v3.2）
瀑布流渲染 + 共用元件
"""

from .components import FIELD_CN_MAP, cn, _radar_chart
from .sidebar import render_sidebar
from .waterfall_info import render_waterfall_1
from .waterfall_charts import render_waterfall_2
from .waterfall_scores import render_waterfall_3
from .waterfall_ai import render_waterfall_4
from .waterfall_debug import render_waterfall_5
from .waterfall_bt_summary import render_waterfall_6