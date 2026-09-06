#!/usr/bin/env python3
"""Backward-compatible entrypoint for the former Deal Radar name.

The canonical product and module are WeChat Intelligence Hub and
``wechat_intelligence_hub.py``. Deal Radar remains one module of that product.
"""

from wechat_intelligence_hub import *  # noqa: F401,F403
from wechat_intelligence_hub import main


if __name__ == "__main__":
    main()
