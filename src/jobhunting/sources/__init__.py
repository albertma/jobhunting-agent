"""职位来源集合"""
from .base import JobSource
from .remotive import RemotiveSource
from .cryptjobslist import CryptoJobsListSource
from .web3career import Web3CareerSource
from .remoteok import RemoteOKSource

__all__ = [
    "JobSource",
    "RemotiveSource",
    "CryptoJobsListSource",
    "Web3CareerSource",
    "RemoteOKSource",
]


def get_source(name: str, config: dict) -> JobSource | None:
    mapping = {
        "remotive": RemotiveSource,
        "cryptjobslist": CryptoJobsListSource,
        "web3career": Web3CareerSource,
        "remoteok": RemoteOKSource,
    }
    cls = mapping.get(name)
    return cls(config) if cls else None
