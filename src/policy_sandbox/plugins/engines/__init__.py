"""Built-in simulation engines with automatic registration."""

from policy_sandbox.plugins.registry import import_modules

import_modules(__path__, __name__)
