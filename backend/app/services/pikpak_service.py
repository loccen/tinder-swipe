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
    
    async def transfer_share_content(self, share_url: str) -> List[str]:
        """
        转存分享链接内容到自己的网盘
        
        Returns:
            转存后的文件/文件夹 ID 列表
        """
        logger.info(f"开始转存分享链接: {share_url}")
        client = await self._ensure_client()
        try:
            # 获取分享信息
            share_info = await client.get_share_info(share_url)
            
            # 详细日志
            logger.debug(f"分享信息响应: {share_info}")
            
            share_id = share_info.get("share_id")
            pass_code_token = share_info.get("pass_code_token")
            files = share_info.get("files", [])
            
            logger.info(
                f"分享信息: share_id={share_id}, "
                f"pass_code_token={pass_code_token[:8] if pass_code_token else 'None'}..., "
                f"文件数量={len(files)}"
            )
            
            if not share_id:
                logger.error(f"分享 ID 为空, 响应: {share_info}")
                raise PikPakError("分享链接无效或已失效 (share_id 为空)")
            
            if not files:
                logger.error(
                    f"分享文件列表为空, share_id={share_id}, "
                    f"file_info字段: {share_info.get('file_info')}, "
                    f"next_page_token: {share_info.get('next_page_token')}"
                )
                raise PikPakError("分享链接内容为空或已失效 (files 为空)")
            
            file_ids = [f["id"] for f in files]
            logger.info(f"准备转存 {len(file_ids)} 个文件: {file_ids}")
            
            # 执行转存
            result = await client.restore(share_id, pass_code_token, file_ids)
            logger.info(f"转存结果: {result}")
            
            # 转存通常返回任务 ID，需要稍等片刻让文件出现在网盘
            # 此处返回 file_id 列表
            return file_ids
        except PikPakError:
            raise
        except Exception as e:
            logger.error(f"转存分享失败: {e}", exc_info=True)
            raise PikPakError(f"转存分享失败: {str(e)}")

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
    
    async def is_file_ready(self, file_id: str) -> bool:
        """
        检查文件是否已就绪（存在且非 0 字节）
        
        Args:
            file_id: 文件 ID
            
        Returns:
            True 如果文件已就绪
        """
        try:
            file_info = await self.get_file_info(file_id)
            size = int(file_info.get("size", 0))
            return size > 0
        except Exception:
            return False


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
