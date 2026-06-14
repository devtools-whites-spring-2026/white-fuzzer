import sys

sys.path.append("/your/path/to/whitefuzzer")

from src import *
from src.mutatable_request import *
from src.mutator import *
from src.openapi_schema import *


def _extract_all_endpoint_schemas() -> list[EndpointSchema]:
    from drf_yasg import openapi
    from testy.swagger.custom_schema_generation import SchemaGenerator

    generator = SchemaGenerator(
        info=openapi.Info(
            title="testy API",
            default_version="v2",
            description="testy API",
        ),
        version="v2",
    )

    schema = generator.get_schema(public=True)
    schema_dict = schema.as_odict()
    all_endpoints = parse_openapi_schema(schema_dict)
    return all_endpoints
