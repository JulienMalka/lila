from pydantic import BaseModel


class OuputHashPair(BaseModel):
    output_path: str
    output_hash: str

