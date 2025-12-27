"""
设置管理 API 路由
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Config

router = APIRouter(prefix="/settings", tags=["settings"])


class ChannelItem(BaseModel):
    """频道项"""
    id: str  # 频道 ID 或用户名
    name: Optional[str] = None  # 显示名称


class ChannelsResponse(BaseModel):
    """频道列表响应"""
    channels: List[ChannelItem]


class ChannelsUpdate(BaseModel):
    """更新频道列表请求"""
    channels: List[ChannelItem]


class SettingsResponse(BaseModel):
    """设置响应"""
    key: str
    value: str
    description: Optional[str] = None


@router.get("/channels", response_model=ChannelsResponse)
async def get_channels(db: AsyncSession = Depends(get_db)):
    """获取监听的频道列表"""
    result = await db.execute(
        select(Config).where(Config.key == "telegram_channels")
    )
    config = result.scalar_one_or_none()
    
    if not config:
        return ChannelsResponse(channels=[])
    
    try:
        raw_channels = json.loads(config.value)
        channels = []
        for ch in raw_channels:
            if isinstance(ch, dict):
                channels.append(ChannelItem(**ch))
            else:
                channels.append(ChannelItem(id=str(ch)))
        return ChannelsResponse(channels=channels)
    except json.JSONDecodeError:
        return ChannelsResponse(channels=[])


@router.put("/channels", response_model=ChannelsResponse)
async def update_channels(
    data: ChannelsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新监听的频道列表"""
    # 序列化为 JSON
    channels_json = json.dumps(
        [{"id": ch.id, "name": ch.name} for ch in data.channels],
        ensure_ascii=False
    )
    
    # 查找或创建配置
    result = await db.execute(
        select(Config).where(Config.key == "telegram_channels")
    )
    config = result.scalar_one_or_none()
    
    if config:
        config.value = channels_json
    else:
        config = Config(
            key="telegram_channels",
            value=channels_json,
            description="监听的 Telegram 频道列表"
        )
        db.add(config)
    
    await db.commit()
    
    # 通知采集器重载 (通过写入一个标记文件)
    import aiofiles
    from pathlib import Path
    reload_flag = Path("/data/reload_channels")
    async with aiofiles.open(reload_flag, "w") as f:
        await f.write(channels_json)
    
    return ChannelsResponse(channels=data.channels)


@router.post("/channels", response_model=ChannelItem)
async def add_channel(
    channel: ChannelItem,
    db: AsyncSession = Depends(get_db)
):
    """添加新频道"""
    # 获取现有频道
    result = await db.execute(
        select(Config).where(Config.key == "telegram_channels")
    )
    config = result.scalar_one_or_none()
    
    channels = []
    if config:
        try:
            raw = json.loads(config.value)
            for ch in raw:
                if isinstance(ch, dict):
                    channels.append(ch)
                else:
                    channels.append({"id": str(ch)})
        except json.JSONDecodeError:
            pass
    
    # 检查是否已存在
    if any(ch["id"] == channel.id for ch in channels):
        raise HTTPException(status_code=400, detail="频道已存在")
    
    # 添加新频道
    channels.append({"id": channel.id, "name": channel.name})
    
    channels_json = json.dumps(channels, ensure_ascii=False)
    
    if config:
        config.value = channels_json
    else:
        config = Config(
            key="telegram_channels",
            value=channels_json,
            description="监听的 Telegram 频道列表"
        )
        db.add(config)
    
    await db.commit()
    
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除频道"""
    result = await db.execute(
        select(Config).where(Config.key == "telegram_channels")
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="频道不存在")
    
    try:
        raw = json.loads(config.value)
        channels = []
        found = False
        for ch in raw:
            ch_id = ch["id"] if isinstance(ch, dict) else str(ch)
            if ch_id != channel_id:
                channels.append(ch if isinstance(ch, dict) else {"id": ch_id})
            else:
                found = True
        
        if not found:
            raise HTTPException(status_code=404, detail="频道不存在")
        
        config.value = json.dumps(channels, ensure_ascii=False)
        await db.commit()
        
        return {"message": "删除成功"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="配置解析失败")
