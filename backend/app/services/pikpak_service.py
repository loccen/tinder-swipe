"""
PikPak API 服务
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from pikpakapi import PikPakApi

from app.core.config import get_settings


class PikPakService:
    """PikPak API 服务"""
    
    # 视频文件扩展名
    VIDEO_EXTENSIONS = {
        ".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv", 
        ".webm", ".m4v", ".rmvb", ".rm", ".ts", ".m2ts"
    }
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        settings = get_settings()
        self.username = username or settings.pikpak_username
        self.password = password or settings.pikpak_password
        self._client: Optional[PikPakApi] = None
    
    async def _ensure_client(self) -> PikPakApi:
        """确保客户端已登录"""
        if self._client is None:
            self._client = PikPakApi(
                username=self.username,
                password=self.password
            )
            await self._client.login()
        return self._client
    
    async def login(self) -> bool:
        """登录 PikPak"""
        try:
            await self._ensure_client()
            return True
        except Exception as e:
            raise PikPakError(f"登录失败: {str(e)}")
    
    async def offline_download(
        self,
        url: str,
        parent_id: str = ""
    ) -> Dict[str, Any]:
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
        
        Args:
            file_id: 文件或文件夹 ID
            
        Returns:
            文件信息
        """
        client = await self._ensure_client()
        try:
            result = await client.get_file_info(file_id)
            return result
        except Exception as e:
            raise PikPakError(f"获取文件信息失败: {str(e)}")
    
    async def get_file_list(
        self,
        parent_id: str = "",
        page_size: int = 100
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
            info = await client.get_file_info(file_id)
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
        self,
        folder_id: str
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
    
    @staticmethod
    def parse_share_url(url: str) -> Optional[str]:
        """
        解析 PikPak 分享链接，提取分享 ID
        
        Args:
            url: PikPak 分享链接
            
        Returns:
            分享 ID 或 None
        """
        # https://mypikpak.com/s/XXXX
        match = re.search(r"mypikpak\.com/s/([A-Za-z0-9]+)", url)
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
