import os
import glob
import json
import time
import platform
import shutil
from uuid import uuid4
from loguru import logger
from app.utils import utils
from app.utils import workspace

def open_task_folder(root_dir, task_id):
    """打开任务文件夹
    Args:
        root_dir: 项目根目录
        task_id: 任务ID
    """
    try:
        sys = platform.system()
        path = workspace.task_dir(sub_dir=task_id, create=False, root_dir=root_dir)
        if os.path.exists(path):
            if sys == 'Windows':
                os.system(f'start "" "{path}"')
            if sys == 'Darwin':
                os.system(f'open "{path}"')
            if sys == 'Linux':
                os.system(f'xdg-open "{path}"')
    except Exception as e:
        logger.error(f"打开任务文件夹失败: {e}")

def cleanup_temp_files(temp_dir, max_age=3600):
    """清理临时文件
    Args:
        temp_dir: 临时文件目录
        max_age: 文件最大保存时间(秒)
    """
    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            try:
                if os.path.getctime(file_path) < time.time() - max_age:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    logger.debug(f"已清理临时文件: {file_path}")
            except Exception as e:
                logger.error(f"清理临时文件失败: {file_path}, 错误: {e}")

def get_file_list(directory, file_types=None, sort_by='ctime', reverse=True):
    """获取指定目录下的文件列表
    Args:
        directory: 目录路径
        file_types: 文件类型列表，如 ['.mp4', '.mov']
        sort_by: 排序方式，支持 'ctime'(创建时间), 'mtime'(修改时间), 'size'(文件大小), 'name'(文件名)
        reverse: 是否倒序排序
    Returns:
        list: 文件信息列表
    """
    if not os.path.exists(directory):
        return []
    
    files = []
    if file_types:
        for file_type in file_types:
            files.extend(glob.glob(os.path.join(directory, f"*{file_type}")))
    else:
        files = glob.glob(os.path.join(directory, "*"))
    
    file_list = []
    for file_path in files:
        try:
            file_stat = os.stat(file_path)
            file_info = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": file_stat.st_size,
                "ctime": file_stat.st_ctime,
                "mtime": file_stat.st_mtime
            }
            file_list.append(file_info)
        except Exception as e:
            logger.error(f"获取文件信息失败: {file_path}, 错误: {e}")
    
    # 排序
    if sort_by in ['ctime', 'mtime', 'size', 'name']:
        file_list.sort(key=lambda x: x.get(sort_by, ''), reverse=reverse)
    
    return file_list


def sanitize_filename(filename, default_stem: str = "upload", default_ext: str = ""):
    """生成安全文件名，避免路径穿越和空文件名。"""
    safe_name = os.path.basename(str(filename or "").strip())
    if safe_name:
        return safe_name

    ext = default_ext or ""
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return f"{default_stem}_{uuid4().hex}{ext}"


def build_unique_file_path(save_dir: str, filename: str, default_stem: str = "upload", default_ext: str = "") -> str:
    """在目标目录内生成安全且不冲突的文件路径。"""
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)

    safe_name = sanitize_filename(filename, default_stem=default_stem, default_ext=default_ext)
    save_path = os.path.join(save_dir, safe_name)
    if os.path.exists(save_path):
        file_name, file_extension = os.path.splitext(safe_name)
        timestamp = time.strftime("%Y%m%d%H%M%S")
        save_path = os.path.join(save_dir, f"{file_name}_{timestamp}{file_extension}")
    return save_path


def save_uploaded_file(uploaded_file, save_dir, allowed_types=None, chunk_size: int = 16 * 1024 * 1024, default_stem: str = "upload", default_ext: str = ""):
    """保存上传的文件
    Args:
        uploaded_file: StreamlitUploadedFile对象
        save_dir: 保存目录
        allowed_types: 允许的文件类型列表，如 ['.mp4', '.mov']
    Returns:
        str: 保存后的文件路径，失败返回None
    """
    try:
        safe_name = sanitize_filename(uploaded_file.name, default_stem=default_stem, default_ext=default_ext)
        file_name, file_extension = os.path.splitext(safe_name)

        # 检查文件类型
        if allowed_types and file_extension.lower() not in allowed_types:
            logger.error(f"不支持的文件类型: {file_extension}")
            return None

        save_path = build_unique_file_path(
            save_dir,
            safe_name,
            default_stem=default_stem,
            default_ext=default_ext,
        )

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        with open(save_path, "wb") as f:
            while True:
                chunk = uploaded_file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        logger.info(f"文件保存成功: {save_path}")
        return save_path
    
    except Exception as e:
        logger.error(f"保存上传文件失败: {e}")
        return None


def save_text_file(content: str, save_dir: str, filename: str, encoding: str = "utf-8", default_stem: str = "text", default_ext: str = ""):
    """以文本形式落盘，并自动处理安全文件名和重名冲突。"""
    try:
        save_path = build_unique_file_path(
            save_dir,
            filename,
            default_stem=default_stem,
            default_ext=default_ext,
        )
        with open(save_path, "w", encoding=encoding) as f:
            f.write(content)
        logger.info(f"文本文件保存成功: {save_path}")
        return save_path
    except Exception as e:
        logger.error(f"保存文本文件失败: {e}")
        return None


def save_json_file(data, save_dir: str, filename: str, ensure_ascii: bool = False, indent: int = 2, default_stem: str = "data", default_ext: str = ".json"):
    """以 JSON 形式落盘，并自动处理安全文件名和重名冲突。"""
    try:
        save_path = build_unique_file_path(
            save_dir,
            filename,
            default_stem=default_stem,
            default_ext=default_ext,
        )
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        logger.info(f"JSON 文件保存成功: {save_path}")
        return save_path
    except Exception as e:
        logger.error(f"保存 JSON 文件失败: {e}")
        return None

def create_temp_file(prefix='tmp', suffix='', directory=None):
    """创建临时文件
    Args:
        prefix: 文件名前缀
        suffix: 文件扩展名
        directory: 临时文件目录，默认使用系统临时目录
    Returns:
        str: 临时文件路径
    """
    try:
        if directory is None:
            directory = utils.temp_dir("webui_files")
        
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        temp_file = os.path.join(directory, f"{prefix}-{str(uuid4())}{suffix}")
        return temp_file
    
    except Exception as e:
        logger.error(f"创建临时文件失败: {e}")
        return None

def get_file_size(file_path, format='MB'):
    """获取文件大小
    Args:
        file_path: 文件路径
        format: 返回格式，支持 'B', 'KB', 'MB', 'GB'
    Returns:
        float: 文件大小
    """
    try:
        size_bytes = os.path.getsize(file_path)
        
        if format.upper() == 'B':
            return size_bytes
        elif format.upper() == 'KB':
            return size_bytes / 1024
        elif format.upper() == 'MB':
            return size_bytes / (1024 * 1024)
        elif format.upper() == 'GB':
            return size_bytes / (1024 * 1024 * 1024)
        else:
            return size_bytes
    
    except Exception as e:
        logger.error(f"获取文件大小失败: {file_path}, 错误: {e}")
        return 0

def ensure_directory(directory):
    """确保目录存在，如果不存在则创建
    Args:
        directory: 目录路径
    Returns:
        bool: 是否成功
    """
    try:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {directory}, 错误: {e}")
        return False

def create_zip(files: list, zip_path: str, base_dir: str = None, folder_name: str = "demo") -> bool:
    """
    创建zip文件
    Args:
        files: 要打包的文件列表
        zip_path: zip文件保存路径
        base_dir: 基础目录，用于保持目录结构
        folder_name: zip解压后的文件夹名称，默认为frames
    Returns:
        bool: 是否成功
    """
    try:
        import zipfile
        
        # 确保目标目录存在
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                if not os.path.exists(file):
                    logger.warning(f"文件不存在，跳过: {file}")
                    continue
                    
                # 计算文件在zip中的路径，添加folder_name作为前缀目录
                if base_dir:
                    arcname = os.path.join(folder_name, os.path.relpath(file, base_dir))
                else:
                    arcname = os.path.join(folder_name, os.path.basename(file))
                
                try:
                    zipf.write(file, arcname)
                except Exception as e:
                    logger.error(f"添加文件到zip失败: {file}, 错误: {e}")
                    continue

        return True
        
    except Exception as e:
        logger.error(f"创建zip文件失败: {e}")
        return False
