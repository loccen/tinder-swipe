"""
PikPak API 服务
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pikpakapi import PikPakApi

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PikPakService:
    """PikPak API 服务"""

    # 视频文件扩展名
    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mkv",
        ".avi",
        ".wmv",
        ".mov",
        ".flv",
        ".webm",
        ".m4v",
        ".rmvb",
        ".rm",
        ".ts",
        ".m2ts",
    }

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        settings = get_settings()
        self.username = username or settings.pikpak_username
        self.password = password or settings.pikpak_password
        self._client: Optional[PikPakApi] = None

    async def _ensure_client(self) -> PikPakApi:
        """确保客户端已登录"""
        if self._client is None:
            self._client = PikPakApi(username=self.username, password=self.password)
            await self._client.login()
        return self._client

    async def login(self) -> bool:
        """登录 PikPak"""
        try:
            await self._ensure_client()
            return True
        except Exception as e:
            raise PikPakError(f"登录失败: {str(e)}")

    async def offline_download(self, url: str, parent_id: str = "") -> Dict[str, Any]:
        """
        添加离线下载任务

        Args:
            url: 磁力链接或其他支持的 URL
            parent_id: 保存目录的文件夹 ID (空字符串表示根目录)

        Returns:
            任务信息
        """
        client = await self._ensure_client()
        try:
            result = await client.offline_download(url, parent_id)
            return result
        except Exception as e:
            raise PikPakError(f"离线下载失败: {str(e)}")

    async def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """
        获取文件/文件夹信息

        注意: PikPakApi 没有直接的 get_file_info 方法，
        我们通过在父目录中查找来获取文件信息。

        Args:
            file_id: 文件或文件夹 ID

        Returns:
        """
        client = await self._ensure_client()
        try:
            logger.info(f"开始查找文件: file_id={file_id}")

            # PikPak 转存的文件默认保存在 "Pack From Shared" 目录
            # 先找到该目录的 ID
            root_result = await client.file_list(parent_id="", size=100)
            root_files = root_result.get("files", [])

            logger.info(f"根目录文件数量: {len(root_files)}")
            for f in root_files:
                logger.info(
                    f"根目录文件: id={f.get('id')}, name={f.get('name')}, kind={f.get('kind')}"
                )

            pack_folder_id = None
            for f in root_files:
                if (
                    f.get("name") == "Pack From Shared"
                    and f.get("kind") == "drive#folder"
                ):
                    pack_folder_id = f.get("id")
                    logger.info(f"找到 Pack From Shared 目录: id={pack_folder_id}")
                    break
                # 直接匹配
                if f.get("id") == file_id:
                    logger.info(f"在根目录找到文件: {f}")
                    return f

            # 在 Pack From Shared 目录下查找
            if pack_folder_id:
                pack_result = await client.file_list(parent_id=pack_folder_id, size=500)
                pack_files = pack_result.get("files", [])

                logger.info(f"Pack From Shared 目录文件数量: {len(pack_files)}")
                for f in pack_files:
                    logger.info(
                        f"Pack文件: id={f.get('id')}, name={f.get('name')}, kind={f.get('kind')}, size={f.get('size')}"
                    )
                    if f.get("id") == file_id:
                        logger.info(f"在 Pack From Shared 目录找到目标文件!")
                        return f

                logger.warning(f"在 Pack From Shared 目录未找到 file_id={file_id}")
            else:
                logger.warning("未找到 Pack From Shared 目录")

            # 如果还是找不到，尝试直接获取下载链接来验证文件是否存在
            try:
                download_info = await client.get_download_url(file_id)
                logger.info(f"通过下载链接获取文件信息: file_id={file_id}")
                if isinstance(download_info, dict):
                    return download_info
            except Exception as download_err:
                logger.warning(f"获取下载链接失败: {download_err}")

            raise PikPakError(f"未找到文件: {file_id}")
        except PikPakError:
            raise
        except Exception as e:
            raise PikPakError(f"获取文件信息失败: {str(e)}")

    async def get_file_list(
        self, parent_id: str = "", page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取目录下的文件列表

        Args:
            parent_id: 父目录 ID (空字符串表示根目录)
            page_size: 每页数量

        Returns:
            文件列表
        """
        client = await self._ensure_client()
        try:
            result = await client.file_list(parent_id=parent_id, size=page_size)
            return result.get("files", [])
        except Exception as e:
            raise PikPakError(f"获取文件列表失败: {str(e)}")

    async def get_download_url(self, file_id: str) -> str:
        """
        获取文件下载直链

        Args:
            file_id: 文件 ID

        Returns:
            下载 URL
        """
        client = await self._ensure_client()
        try:
            # PikPakApi.get_download_url 返回文件详情，包含 web_content_link 和 medias
            info = await client.get_download_url(file_id)

            # 优先使用 web_content_link
            url = info.get("web_content_link")
            if not url:
                # 备选 links 中的链接
                links = info.get("links", {})
                for link_info in links.values():
                    if isinstance(link_info, dict) and link_info.get("url"):
                        url = link_info["url"]
                        break

            if not url:
                raise PikPakError("无法获取下载链接")

            return url
        except PikPakError:
            raise
        except Exception as e:
            raise PikPakError(f"获取下载链接失败: {str(e)}")

    async def get_video_files_recursive(
        self, folder_id: str
    ) -> List[Tuple[str, str, int, str]]:
        """
        递归获取文件夹下所有视频文件

        Args:
            folder_id: 文件夹 ID

        Returns:
            [(文件ID, 文件名, 文件大小, 下载链接), ...]
        """
        client = await self._ensure_client()
        video_files: List[Tuple[str, str, int, str]] = []

        async def _scan_folder(parent_id: str):
            files = await self.get_file_list(parent_id)
            for file in files:
                if file.get("kind") == "drive#folder":
                    # 递归扫描子文件夹
                    await _scan_folder(file["id"])
                else:
                    # 检查是否为视频文件
                    name = file.get("name", "")
                    ext = self._get_extension(name)
                    if ext in self.VIDEO_EXTENSIONS:
                        file_id = file["id"]
                        file_size = int(file.get("size", 0))
                        download_url = await self.get_download_url(file_id)
                        video_files.append((file_id, name, file_size, download_url))

        await _scan_folder(folder_id)
        return video_files

    @staticmethod
    def _get_extension(filename: str) -> str:
        """获取文件扩展名 (小写)"""
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""

    async def transfer_share_content(self, share_url: str) -> List[str]:
        """
        转存分享链接内容到自己的网盘

        Returns:
            转存后的文件/文件夹 ID 列表
        """
        logger.info(f"开始转存分享链接: {share_url}")

        # 从 URL 解析 share_id
        share_id = self.parse_share_url(share_url)
        if not share_id:
            raise PikPakError(f"无法从 URL 解析 share_id: {share_url}")
        logger.info(f"从 URL 解析出 share_id: {share_id}")

        client = await self._ensure_client()
        try:
            # 获取分享信息 (返回 files 和 pass_code_token)
            share_info = await client.get_share_info(share_url)

            pass_code_token = share_info.get("pass_code_token", "")
            files = share_info.get("files", [])
            share_status = share_info.get("share_status", "")

            logger.info(
                f"分享信息: share_id={share_id}, status={share_status}, "
                f"pass_code_token={pass_code_token[:8] if pass_code_token else 'None'}..., "
                f"文件数量={len(files)}"
            )

            if share_status != "OK":
                raise PikPakError(f"分享链接状态异常: {share_status}")

            if not files:
                raise PikPakError("分享链接内容为空或已失效 (files 为空)")

            # 记录分享中的原始文件信息
            for f in files:
                logger.info(
                    f"分享文件: id={f.get('id')}, name={f.get('name')}, kind={f.get('kind')}"
                )

            original_ids = [f["id"] for f in files]
            file_names = [f.get("name", "") for f in files]

            # 执行转存
            result = await client.restore(share_id, pass_code_token, original_ids)
            logger.info(f"转存结果: {result}")

            # 返回 (文件名, 原始ID) 元组列表
            # 后续需要用文件名在 Pack From Shared 目录匹配获取真实 ID
            return list(zip(file_names, original_ids))
        except PikPakError:
            raise
        except Exception as e:
            logger.error(f"转存分享失败: {e}", exc_info=True)
            raise PikPakError(f"转存分享失败: {str(e)}")

    async def _find_transferred_files(self, names: List[str]) -> List[str]:
        """
        在 Pack From Shared 目录查找转存后的文件

        Args:
            names: 要查找的文件名列表

        Returns:
            找到的文件 ID 列表
        """
        client = await self._ensure_client()

        # 先找到 Pack From Shared 目录
        root_result = await client.file_list(parent_id="", size=100)
        root_files = root_result.get("files", [])

        pack_folder_id = None
        for f in root_files:
            if f.get("name") == "Pack From Shared" and f.get("kind") == "drive#folder":
                pack_folder_id = f.get("id")
                break

        if not pack_folder_id:
            logger.warning("未找到 Pack From Shared 目录")
            return []

        # 在目录下查找匹配的文件
        pack_result = await client.file_list(parent_id=pack_folder_id, size=500)
        pack_files = pack_result.get("files", [])

        found_ids = []
        for name in names:
            for f in pack_files:
                if f.get("name") == name:
                    found_ids.append(f.get("id"))
                    logger.info(f"找到转存后的文件: name={name}, id={f.get('id')}")
                    break

        return found_ids

    @staticmethod
    def parse_share_url(url: str) -> Optional[str]:
        """
        解析 PikPak 分享链接，提取分享 ID

        Args:
            url: PikPak 分享链接

        Returns:
            分享 ID 或 None
        """
        # https://mypikpak.com/s/XXXX 或 https://mypikpak.com/s/XXX_YYY
        match = re.search(r"mypikpak\.com/s/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def is_magnet_link(url: str) -> bool:
        """判断是否为磁力链接"""
        return url.startswith("magnet:?")

    async def close(self):
        """关闭客户端"""
        # PikPakApi 没有显式的关闭方法
        self._client = None

    async def is_file_ready(
        self, file_id: str, file_name: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        检查文件是否已就绪（存在且非 0 字节）

        如果按 file_id 找不到，会尝试用 file_name 在 Pack From Shared 目录查找。

        Args:
            file_id: 文件 ID
            file_name: 可选的文件名，用于按名查找

        Returns:
            (is_ready, actual_file_id) - 是否就绪，以及实际的文件 ID (如果通过文件名找到)
        """
        try:
            logger.info(f"检查文件就绪状态: file_id={file_id}, file_name={file_name}")

            # 先尝试按 ID 查找
            try:
                file_info = await self.get_file_info(file_id)
                return self._check_file_ready(file_info, file_id)
            except PikPakError as e:
                logger.info(f"按 ID 查找失败: {e}")

            # 如果有文件名，尝试按名查找
            if file_name:
                logger.info(f"尝试按文件名查找: {file_name}")
                found_ids = await self._find_transferred_files([file_name])
                if found_ids:
                    actual_id = found_ids[0]
                    logger.info(f"按文件名找到实际 ID: {file_name} -> {actual_id}")

                    # 再次检查实际文件的就绪状态
                    try:
                        file_info = await self.get_file_info(actual_id)
                        is_ready, _ = self._check_file_ready(file_info, actual_id)
                        return (is_ready, actual_id)
                    except PikPakError:
                        pass

            return (False, None)
        except Exception as e:
            logger.error(f"检查文件就绪状态失败: file_id={file_id}, error={e}")
            return (False, None)

    def _check_file_ready(
        self, file_info: Dict[str, Any], file_id: str
    ) -> tuple[bool, Optional[str]]:
        """检查文件信息判断是否就绪"""
        size = int(file_info.get("size", 0))
        phase = file_info.get("phase", "")
        kind = file_info.get("kind", "")
        name = file_info.get("name", "")

        logger.info(
            f"文件信息: file_id={file_id}, name={name}, "
            f"kind={kind}, size={size}, phase={phase}"
        )

        # 如果是文件夹，视为就绪
        if kind == "drive#folder":
            logger.info(f"文件 {file_id} 是文件夹，视为就绪")
            return (True, file_id)

        is_ready = size > 0 and phase == "PHASE_TYPE_COMPLETE"
        logger.info(f"文件就绪判断: file_id={file_id}, is_ready={is_ready}")
        return (is_ready, file_id)


class PikPakError(Exception):
    """PikPak API 错误"""

    pass


# 单例服务
_pikpak_service: Optional[PikPakService] = None


def get_pikpak_service() -> PikPakService:
    """获取 PikPak 服务单例"""
    global _pikpak_service
    if _pikpak_service is None:
        _pikpak_service = PikPakService()
    return _pikpak_service
