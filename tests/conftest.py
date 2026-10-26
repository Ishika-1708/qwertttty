import sys
import backend
import backend.aggregations
import backend.config
import backend.contract
import backend.data_quality
import backend.forecast_comparison
import backend.main
import backend.metrics
import backend.providers
import backend.service
import backend.api
import backend.api.routes
import backend.api.schemas

sys.modules["module2"] = backend
sys.modules["module2.aggregations"] = backend.aggregations
sys.modules["module2.config"] = backend.config
sys.modules["module2.contract"] = backend.contract
sys.modules["module2.data_quality"] = backend.data_quality
sys.modules["module2.forecast_comparison"] = backend.forecast_comparison
sys.modules["module2.main"] = backend.main
sys.modules["module2.metrics"] = backend.metrics
sys.modules["module2.providers"] = backend.providers
sys.modules["module2.service"] = backend.service
sys.modules["module2.api"] = backend.api
sys.modules["module2.api.routes"] = backend.api.routes
sys.modules["module2.api.schemas"] = backend.api.schemas
