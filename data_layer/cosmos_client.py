import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class CosmosDataClient:
    """Small Cosmos wrapper with graceful degradation when unavailable."""

    def __init__(
        self,
        endpoint: str,
        key: str,
        database_name: str,
        container_name: str,
    ) -> None:
        self._enabled = os.getenv("COSMOS_ENABLED", "true").lower() == "true"
        self._endpoint = endpoint
        self._key = key
        self._database_name = database_name
        self._container_name = container_name
        self._container = None

    @classmethod
    def from_env(cls) -> "CosmosDataClient":
        # Best-effort .env load so local runs do not depend on shell-exported env vars.
        try:
            from dotenv import load_dotenv  # type: ignore

            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=False)
        except Exception:
            pass

        return cls(
            endpoint=os.getenv("COSMOS_ENDPOINT", ""),
            key=os.getenv("COSMOS_KEY", ""),
            database_name=os.getenv("COSMOS_DATABASE", "JingHuPetProject"),
            container_name=os.getenv("COSMOS_CONTAINER", "MainData"),
        )

    def _connect(self) -> None:
        if self._container is not None:
            return
        missing = []
        if not self._endpoint:
            missing.append("COSMOS_ENDPOINT")
        if not self._key:
            missing.append("COSMOS_KEY")
        if not self._database_name:
            missing.append("COSMOS_DATABASE")
        if not self._container_name:
            missing.append("COSMOS_CONTAINER")

        if not self._enabled:
            raise RuntimeError("Cosmos disabled because COSMOS_ENABLED is not true")
        if missing:
            raise RuntimeError(f"Cosmos connection info missing: {', '.join(missing)}")

        try:
            from azure.cosmos import CosmosClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("azure-cosmos package is not installed") from exc

        client = CosmosClient(self._endpoint, credential=self._key)
        database = client.get_database_client(self._database_name)
        self._container = database.get_container_client(self._container_name)

    def query_items(self, query: str, parameters: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        self._connect()
        assert self._container is not None
        return list(
            self._container.query_items(
                query=query,
                parameters=parameters or [],
                enable_cross_partition_query=True,
            )
        )

    def upsert_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self._connect()
        assert self._container is not None
        return self._container.upsert_item(item)

    def ping(self) -> bool:
        try:
            items = self.query_items("SELECT TOP 1 c.id FROM c")
            return isinstance(items, list)
        except Exception:
            return False

