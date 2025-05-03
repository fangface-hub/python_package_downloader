# 帮助

## 使用方法

1. 启动 `PythonPackageDownloader`

1. 输入下载信息

    屏幕项目如下：

    | 屏幕项目 | 说明 |
    | ---- | ---- |
    | 下载方法 | 必填项<br>如果未安装 PyPISimple 和 requests，将强制使用 pip。<br>使用 pip：使用下载环境中的 pip 进行 pip download<br>不使用 pip：使用 HTTP 下载软件包 |
    | 选择操作系统 | 选择 Windows、Linux 或 macOS |
    | Python 版本 | 必填项，可多选<br>选择目标 Python 版本 |
    | 软件包列表 | 必填项<br>指定软件包列表（文本文件）的路径<br>格式与 `pip install -r requirements.txt` 中的 `requirements.txt` 相同 |
    | 下载目标 | 必填项<br>指定下载目标文件夹。<br>默认为脚本位置的 downloads 文件夹 |
    | pip 路径 | 使用 pip 时为必填项<br>在下载环境中搜索 pip 并初始显示 |
    | 使用代理<br>用户 ~ 端口 | 可选项<br>如果使用代理，请输入 |
    | 包含源格式 | 可选项<br>如果下载失败，尝试下载 tar.gz 格式 |  
    | 下载依赖项 | 检查已下载软件包的依赖项并递归下载<br>请注意，根据软件包的不同，处理时间可能会增加 |

    > 按"保存设置"按钮保存输入项目

1. 按"开始下载"按钮
