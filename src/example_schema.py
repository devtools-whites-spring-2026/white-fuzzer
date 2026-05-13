from src.schema_model import SchemaNode

schema = SchemaNode(
    name="request",
    kind="object",
    mutable=False,
    properties={
        "title": SchemaNode(name="title", kind="string", mutable=True),
        "status": SchemaNode(
            name="status",
            kind="enum",
            mutable=True,
            enum_values=["new", "done"],
        ),
        "id": SchemaNode(name="id", kind="integer", mutable=False),
    },
)