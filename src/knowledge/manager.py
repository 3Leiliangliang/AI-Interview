import asyncio
import os

from src.knowledge.base import KBNotFoundError, KnowledgeBase
from src.knowledge.chunking.ragflow_like.presets import deep_merge
from src.knowledge.factory import KnowledgeBaseFactory
from src.knowledge.metadata import normalize_kb_additional_params
from src.storage.postgres.models_business import User
from src.utils import logger
from src.utils.datetime_utils import utc_isoformat


class KnowledgeBaseManager:

    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

        self.kb_instances: dict[str, KnowledgeBase] = {}

        self._metadata_lock = asyncio.Lock()

    async def initialize(self):
        self._initialize_existing_kbs()
        logger.info("KnowledgeBaseManager initialized")

    async def _load_all_metadata(self):
        pass

    async def _migrate_existing_kbs_to_openviking(self) -> None:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        for row in rows:
            current_type = (row.kb_type or "").strip().lower()
            if current_type == "openviking":
                continue
            await kb_repo.update(row.db_id, {"kb_type": "openviking"})
            logger.info(
                "Migrated knowledge base %s from %s to openviking",
                row.db_id,
                row.kb_type or "unknown",
            )

    def _initialize_existing_kbs(self):
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        async def _async_init():
            kb_repo = KnowledgeBaseRepository()
            await self._migrate_existing_kbs_to_openviking()
            rows = await kb_repo.get_all()

            kb_types_in_use = set()
            for row in rows:
                kb_type = row.kb_type or "openviking"
                kb_types_in_use.add(kb_type)

            logger.info(f"[InitializeKB] 发现 {len(kb_types_in_use)} 种知识库类型: {kb_types_in_use}")

            for kb_type in kb_types_in_use:
                try:
                    kb_instance = self._get_or_create_kb_instance(kb_type)
                    await kb_instance._load_metadata()
                    logger.info(f"[InitializeKB] {kb_type} 实例已初始化")
                except Exception as e:
                    logger.error(f"Failed to initialize {kb_type} knowledge base: {e}")
                    import traceback

                    logger.error(traceback.format_exc())

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_init())
        except RuntimeError:
            asyncio.run(_async_init())

    def _get_or_create_kb_instance(self, kb_type: str) -> KnowledgeBase:
        if kb_type in self.kb_instances:
            return self.kb_instances[kb_type]

        kb_work_dir = os.path.join(self.work_dir, f"{kb_type}_data")
        kb_instance = KnowledgeBaseFactory.create(kb_type, kb_work_dir)

        self.kb_instances[kb_type] = kb_instance
        logger.info(f"Created {kb_type} knowledge base instance")
        return kb_instance

    async def move_file(self, db_id: str, file_id: str, new_parent_id: str | None) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.move_file(db_id, file_id, new_parent_id)

    async def rename_file(self, db_id: str, file_id: str, new_name: str) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.rename_file(db_id, file_id, new_name)

    async def _get_kb_for_database(self, db_id: str) -> KnowledgeBase:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_id(db_id)

        if kb is None:
            raise KBNotFoundError(f"Database {db_id} not found")

        kb_type = kb.kb_type or "openviking"

        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            raise KBNotFoundError(f"Unsupported knowledge base type: {kb_type}")

        return self._get_or_create_kb_instance(kb_type)

    def _get_kb_for_database_sync(self, db_id: str) -> KnowledgeBase:
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self._get_kb_for_database(db_id))
        except RuntimeError:
            return asyncio.run(self._get_kb_for_database(db_id))


    async def aget_kb(self, db_id: str) -> KnowledgeBase:
        return await self._get_kb_for_database(db_id)

    def get_kb(self, db_id: str) -> KnowledgeBase:
        return self._get_kb_for_database_sync(db_id)

    async def get_databases(self) -> dict:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        all_databases = []
        metadata_reloaded_types: set[str] = set()
        for row in rows:
            kb_type = row.kb_type or "openviking"
            kb_instance = self._get_or_create_kb_instance(kb_type)
            db_info = kb_instance.get_database_info(row.db_id)
            if not db_info and kb_type not in metadata_reloaded_types:
                try:
                    await kb_instance._load_metadata()
                    metadata_reloaded_types.add(kb_type)
                except Exception as e:
                    logger.warning(f"Failed to reload metadata for kb_type={kb_type}: {e}")
                db_info = kb_instance.get_database_info(row.db_id)

            if not db_info:
                logger.warning(f"Skip database due to missing metadata: db_id={row.db_id}, kb_type={kb_type}")
                continue

            db_info["share_config"] = self._normalize_share_config(row.share_config)
            db_info["additional_params"] = normalize_kb_additional_params(row.additional_params)
            all_databases.append(db_info)
        return {"databases": all_databases}

    @staticmethod
    def _normalize_share_config(share_config: dict | None) -> dict:
        raw_config = share_config or {}
        enabled_for_agents = raw_config.get("enabled_for_agents")
        if enabled_for_agents is None:
            enabled_for_agents = raw_config.get("is_shared", True)
        return {"enabled_for_agents": bool(enabled_for_agents)}

    async def check_accessible(self, user: dict, db_id: str) -> bool:
        if user.get("role") in {"superadmin", "admin"}:
            return True

        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_id(db_id)
        if kb is None:
            return False

        share_config = self._normalize_share_config(kb.share_config)
        return bool(share_config.get("enabled_for_agents", True))

    async def get_databases_by_raw_id(self, user_id: int) -> dict:
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user: User | None = await user_repo.get_by_id(id=int(user_id))
        if not user:
            logger.warning(f"User not found: {user_id}")
            return {"databases": []}
        return await self.get_databases_by_user(user)

    async def get_databases_by_user_id(self, user_id: str) -> dict:
        from src.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        user: User | None = await user_repo.get_by_user_id(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            return {"databases": []}
        return await self.get_databases_by_user(user)

    async def get_databases_by_user(self, user: User) -> dict:
        user_info = {"role": user.role}

        logger.info(f"Getting databases for user {user.id} with role {user.role}")

        all_databases = (await self.get_databases()).get("databases", [])

        if user_info.get("role") == "superadmin":
            return {"databases": all_databases}

        filtered_databases = []

        for db in all_databases:
            db_id = db.get("db_id")
            if not db_id:
                continue

            if await self.check_accessible(user_info, db_id):
                filtered_databases.append(db)

        return {"databases": filtered_databases}

    async def database_name_exists(self, database_name: str) -> bool:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from src.storage.postgres.manager import pg_manager

        if not pg_manager._initialized:
            pg_manager.initialize()

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        for row in rows:
            if (row.name or "").lower() == database_name.lower():
                return True
        return False

    async def create_folder(self, db_id: str, folder_name: str, parent_id: str = None) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.create_folder(db_id, folder_name, parent_id)

    async def create_database(
        self,
        database_name: str,
        description: str,
        kb_type: str = "openviking",
        embed_info: dict | None = None,
        share_config: dict | None = None,
        **kwargs,
    ) -> dict:
        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            available_types = list(KnowledgeBaseFactory.get_available_types().keys())
            raise ValueError(f"Unsupported knowledge base type: {kb_type}. Available types: {available_types}")

        if await self.database_name_exists(database_name):
            raise ValueError(f"????? '{database_name}' ???????????")

        share_config = self._normalize_share_config(share_config)

        kwargs = normalize_kb_additional_params(kwargs)

        kb_instance = self._get_or_create_kb_instance(kb_type)
        db_info = await kb_instance.create_database(database_name, description, embed_info, **kwargs)
        db_id = db_info["db_id"]

        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        updated = await kb_repo.update(db_id, {"share_config": share_config})
        if updated is None:
            await kb_repo.create(
                {
                    "db_id": db_id,
                    "name": database_name,
                    "description": description,
                    "kb_type": kb_type,
                    "embed_info": embed_info,
                    "llm_info": db_info.get("llm_info"),
                    "additional_params": kwargs.copy(),
                    "share_config": share_config,
                }
            )

        logger.info(f"Created {kb_type} database: {database_name} ({db_id}) with {kwargs}")
        db_info["share_config"] = share_config
        return db_info

    async def delete_database(self, db_id: str) -> dict:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        try:
            kb_instance = await self._get_kb_for_database(db_id)
            result = await kb_instance.delete_database(db_id)

            kb_repo = KnowledgeBaseRepository()
            await kb_repo.delete(db_id)
            return result
        except KBNotFoundError as e:
            logger.warning(f"Database {db_id} not found during deletion: {e}")
            return {"message": "????"}

    async def add_file_record(
        self, db_id: str, item: str, params: dict | None = None, operator_id: str | None = None
    ) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.add_file_record(db_id, item, params, operator_id)

    async def parse_file(self, db_id: str, file_id: str, operator_id: str | None = None) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.parse_file(db_id, file_id, operator_id)

    async def index_file(self, db_id: str, file_id: str, operator_id: str | None = None) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.index_file(db_id, file_id, operator_id)

    async def update_file_params(self, db_id: str, file_id: str, params: dict, operator_id: str | None = None) -> None:
        kb_instance = await self._get_kb_for_database(db_id)
        await kb_instance.update_file_params(db_id, file_id, params, operator_id)

    async def aquery(self, query_text: str, db_id: str, **kwargs) -> str:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.aquery(query_text, db_id, **kwargs)

    async def export_data(self, db_id: str, format: str = "zip", **kwargs) -> str:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.export_data(db_id, format=format, **kwargs)

    def query(self, query_text: str, db_id: str, **kwargs) -> str:
        kb_instance = self._get_kb_for_database_sync(db_id)
        return kb_instance.query(query_text, db_id, **kwargs)

    async def get_database_info(self, db_id: str) -> dict | None:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_id(db_id)
        if kb is None:
            return None

        try:
            kb_instance = await self._get_kb_for_database(db_id)
            db_info = kb_instance.get_database_info(db_id)
        except KBNotFoundError:
            db_info = {
                "db_id": db_id,
                "name": kb.name,
                "description": kb.description,
                "kb_type": kb.kb_type,
                "files": {},
                "row_count": 0,
                "status": "???",
            }

        db_info["additional_params"] = normalize_kb_additional_params(kb.additional_params)
        db_info["share_config"] = self._normalize_share_config(kb.share_config)
        db_info["mindmap"] = kb.mindmap
        db_info["sample_questions"] = kb.sample_questions or []
        db_info["query_params"] = kb.query_params

        return db_info

    async def delete_folder(self, db_id: str, folder_id: str) -> None:
        kb_instance = await self._get_kb_for_database(db_id)
        await kb_instance.delete_folder(db_id, folder_id)

    async def delete_file(self, db_id: str, file_id: str) -> None:
        kb_instance = await self._get_kb_for_database(db_id)
        await kb_instance.delete_file(db_id, file_id)

    async def update_content(self, db_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.update_content(db_id, file_ids, params or {})

    async def get_file_basic_info(self, db_id: str, file_id: str) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.get_file_basic_info(db_id, file_id)

    async def get_file_content(self, db_id: str, file_id: str) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.get_file_content(db_id, file_id)

    async def get_file_info(self, db_id: str, file_id: str) -> dict:
        kb_instance = await self._get_kb_for_database(db_id)
        return await kb_instance.get_file_info(db_id, file_id)

    def get_db_upload_path(self, db_id: str | None = None) -> str:
        if db_id:
            try:
                kb_instance = self._get_kb_for_database_sync(db_id)
                return kb_instance.get_db_upload_path(db_id)
            except KBNotFoundError:
                pass

        general_uploads = os.path.join(self.work_dir, "uploads")
        os.makedirs(general_uploads, exist_ok=True)
        return general_uploads

    async def file_name_existed_in_db(self, db_id: str | None, file_name: str | None) -> bool:
        if not db_id or not file_name:
            return False
        try:
            kb_instance = await self._get_kb_for_database(db_id)
        except KBNotFoundError:
            return False

        for file_info in kb_instance.files_meta.values():
            if file_info.get("database_id") != db_id:
                continue
            if file_info.get("status") == "failed":
                continue
            if file_info.get("file_name") == file_name:
                return True

        return False

    async def get_same_name_files(self, db_id: str, filename: str) -> list[dict]:
        if not db_id or not filename:
            return []
        try:
            kb_instance = await self._get_kb_for_database(db_id)
        except KBNotFoundError:
            return []

        same_name_files = []
        for file_id, file_info in kb_instance.files_meta.items():
            if file_info.get("database_id") != db_id:
                continue
            if file_info.get("status") == "failed":
                continue

            current_filename = file_info.get("filename", "")

            if current_filename.lower() == filename.lower():
                same_name_files.append(
                    {
                        "file_id": file_id,
                        "filename": current_filename,
                        "size": file_info.get("size", 0),
                        "created_at": file_info.get("created_at", ""),
                        "content_hash": file_info.get("content_hash", ""),
                    }
                )

        same_name_files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return same_name_files

    async def file_existed_in_db(self, db_id: str | None, content_hash: str | None) -> bool:
        if not db_id or not content_hash:
            return False

        try:
            kb_instance = await self._get_kb_for_database(db_id)
        except KBNotFoundError:
            return False

        for file_info in kb_instance.files_meta.values():
            if file_info.get("database_id") != db_id:
                continue
            if file_info.get("status") == "failed":
                continue
            if file_info.get("content_hash") == content_hash:
                return True

        return False

    async def update_database(
        self,
        db_id: str,
        name: str,
        description: str,
        llm_info: dict = None,
        additional_params: dict | None = None,
        share_config: dict | None = None,
    ) -> dict:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_id(db_id)
        if kb is None:
            raise ValueError(f"??? {db_id} ???")

        kb_instance = await self._get_kb_for_database(db_id)
        kb_instance.update_database(db_id, name, description, llm_info, additional_params)

        update_data: dict = {
            "name": name,
            "description": description,
        }
        if llm_info is not None:
            update_data["llm_info"] = llm_info

        if additional_params is not None:
            merged_additional_params = normalize_kb_additional_params(deep_merge(kb.additional_params or {}, additional_params))
            update_data["additional_params"] = merged_additional_params
            if db_id in kb_instance.databases_meta:
                kb_instance.databases_meta[db_id]["metadata"] = merged_additional_params

        if share_config is not None:
            update_data["share_config"] = share_config

        await kb_repo.update(db_id, update_data)

        return await self.get_database_info(db_id)

    def get_retrievers(self) -> dict[str, dict]:
        all_retrievers = {}

        for kb_instance in self.kb_instances.values():
            retrievers = kb_instance.get_retrievers()
            all_retrievers.update(retrievers)

        return all_retrievers


    def get_supported_kb_types(self) -> dict[str, dict]:
        return KnowledgeBaseFactory.get_available_types()

    def get_kb_instance_info(self) -> dict[str, dict]:
        info = {}
        for kb_type, kb_instance in self.kb_instances.items():
            info[kb_type] = {
                "work_dir": kb_instance.work_dir,
                "database_count": len(kb_instance.databases_meta),
                "file_count": len(kb_instance.files_meta),
            }
        return info

    async def get_statistics(self) -> dict:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from src.repositories.knowledge_file_repository import KnowledgeFileRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()

        stats = {"total_databases": len(rows), "kb_types": {}, "total_files": 0}

        for row in rows:
            kb_type = row.kb_type or "openviking"
            if kb_type not in stats["kb_types"]:
                stats["kb_types"][kb_type] = 0
            stats["kb_types"][kb_type] += 1

        file_repo = KnowledgeFileRepository()
        files = await file_repo.get_all()
        stats["total_files"] = len(files)

        return stats





    async def detect_data_inconsistencies(self) -> dict:
        return {
            "openviking": {"missing_resources": [], "missing_files": []},
            "total_missing_resources": 0,
            "total_missing_files": 0,
        }

    async def manual_consistency_check(self) -> dict:
        logger.info("Manual consistency check for OpenViking knowledge bases")
        return await self.detect_data_inconsistencies()

