from pydantic import BaseModel


class OuputHashPair(BaseModel):
    output: str
    sha256: str

