from pydantic import BaseModel, RootModel
from typing import Dict, List


class OutputHashPair(BaseModel):
    output_path: str
    output_hash: str
    output_sig: str

class Derivation(BaseModel): 
    id: int
    drv_hash: str

class DerivationList(RootModel):
    root: List[Derivation]
    model_config = {
        "json_schema_extra": {
            "examples": [
               [
                {
                    "id": 1,
                    "drv_hash": "wi7zzh67w2vv1m4vi3czv8iwbxaijs5r-htop-3.3.0"
                },
                {
                    "id": 2,
                    "drv_hash": "qjnshgfgzidg198g9bm2ildqvlyaxaab-libidn2-2.3.7"
                },
                {
                    "id": 3,
                    "drv_hash": "19xrcsw2p2hgnska18s7qflz6wpxpby3-curl-8.6.0"
                }
               ] 
            ]
        }
    }




class DerivationAttestation(RootModel):
    root: Dict[str, Dict[str, int]]
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "/nix/store/84wcm74cp3k2i504ggwkgf4ikdyk0y3m-curl-8.6.0": {
                        "181hm4vvznw09jzxdraj8x46648fbbv7a3l9ngj7gp0i7idai2as": 3,
                        "55d4c01fe39618b34cad5db1d212d9e6206c35da2ee4b5c798d3": 2
                    },
                    "/nix/store/fh7vxc5xgiwl6z7vwq5c3lj84mpcs4br-curl-8.6.0-bin": {
                        "19l03dn34mwlanws95w4apa6c52pm9b4xldbbd3kidaqybladjv6": 5
                    },
                    "/nix/store/p7xwmisyjskm9kmy1nb356v9qqymrr3h-curl-8.6.0-man": {
                        "1wf0j69qvy0glqn77janyh10m75qdy67vlb8vmgn97aq88g8r53g": 5
                    }
                }
            ]
        }
    }



