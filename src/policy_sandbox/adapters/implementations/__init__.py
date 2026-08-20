"""Auto-discover built-in aggregate data adapters."""

from policy_sandbox.plugins.registry import import_modules

import_modules(__path__, __name__)
