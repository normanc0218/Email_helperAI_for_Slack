import os
from dotenv import load_dotenv
load_dotenv()

if os.getenv("EVAL_MODE", "").lower() == "true":
    from .eval_setup import install as _install_eval_mocks
    _install_eval_mocks()

from .database import init_db
init_db()

from .agent import root_agent

__all__ = ["root_agent"]
