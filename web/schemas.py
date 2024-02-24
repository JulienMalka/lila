from pydantic import BaseModel


class OuputHashPair(BaseModel):
    output_name: str
    output_hash: str

