# Image Safety

## 职责

`images/` 将不可信上传转为无元数据、可过期删除的私有临时引用。它是视觉 Provider 之前唯一允许处理原始图片字节的边界。

## 允许依赖

- 可以依赖 Pillow、核心运行配置和标准库。
- 不依赖 FastAPI、SQLAlchemy、Agent 图或任何 Provider SDK。
- 只向上游返回最小化 `ValidatedImageReference`；不得记录或持久化原图、base64、EXIF、文件名或公开 URL。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `schemas.py` | 运行时校验的最小临时图片引用和稳定失败类别。 |
| `repository.py` | 私有临时目录的受控读写与删除。 |
| `service.py` | MIME、字节、真实解码、像素上限、metadata 剥离与过期清理。 |
