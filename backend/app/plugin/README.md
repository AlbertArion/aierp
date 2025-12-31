# Python插件系统

## 概述

Python插件系统是AI ERP平台的可扩展开发能力的一部分，支持Python插件的加载、管理和集成，与Java插件系统保持功能对等。

## 核心组件

### 1. 基础接口 (`base.py`)
- `IPlugin`: 插件核心接口
- `PluginMetadata`: 插件元数据
- `PluginContext`: 插件上下文
- `PluginStatus`: 插件状态枚举
- `PluginRegistry`: 插件注册表接口
- `ServiceRegistry`: 服务注册表接口
- `ConfigProvider`: 配置提供者接口

### 2. 插件加载器 (`loader.py`)
- 支持单文件插件（.py文件）
- 支持目录形式插件（包含main.py或__init__.py的目录）
- 使用importlib动态加载模块
- 自动查找实现IPlugin接口的类

### 3. 插件注册表 (`registry.py`)
- 插件注册和查询
- 依赖关系管理
- 拓扑排序计算启动顺序
- 循环依赖检测

### 4. 服务注册表 (`service_registry.py`)
- 插件服务注册和查询
- 主系统服务访问
- 服务类型转换

### 5. 配置提供者 (`config_provider.py`)
- 插件配置的读取和更新
- 配置验证

### 6. 插件管理器 (`manager.py`)
- 插件生命周期管理
- 自动加载和启动插件
- 动态加载和卸载插件

## 快速开始

### 1. 配置插件目录

通过环境变量配置：

```bash
export PLUGIN_DIRECTORY=/opt/ai-erp/plugins
export PLUGIN_AUTO_LOAD=true
```

或在代码中配置：

```python
from app.plugin.manager import PluginManager

plugin_manager = PluginManager(
    app=app,
    plugin_directory="/opt/ai-erp/plugins",
    auto_load=True
)
```

### 2. 开发插件

创建一个实现`IPlugin`接口的类：

```python
from app.plugin.base import IPlugin, PluginMetadata, PluginStatus, PluginContext
from typing import Dict, Any

class MyPlugin(IPlugin):
    def __init__(self):
        self.status = PluginStatus.INSTALLED
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            plugin_id="my-plugin",
            plugin_name="我的插件",
            version="1.0.0",
            plugin_class="MyPlugin"
        )
    
    def initialize(self, context: PluginContext) -> None:
        self.context = context
        self.status = PluginStatus.INITIALIZED
    
    def start(self) -> None:
        self.status = PluginStatus.STARTED
    
    def stop(self) -> None:
        self.status = PluginStatus.STOPPED
    
    def destroy(self) -> None:
        pass
    
    def get_services(self) -> Dict[str, Any]:
        return {}
    
    def get_status(self) -> PluginStatus:
        return self.status
```

### 3. 部署插件

#### 单文件插件
将插件文件保存为`.py`文件，放到插件目录中：

```
~/plugins/
  └── my_plugin.py
```

#### 目录形式插件
创建包含`main.py`或`__init__.py`的目录：

```
~/plugins/
  └── my_plugin/
      ├── main.py
      └── dependencies/
```

### 4. 使用插件服务

```python
# 从FastAPI应用获取插件管理器
plugin_manager = app.state.plugin_manager

# 获取插件服务
service_registry = plugin_manager.service_registry
service = service_registry.get_service("my-plugin:myService", MyServiceType)

# 使用服务
result = service.process_data("input")
```

## 插件开发规范

### 1. 必须实现的方法
- `get_metadata()`: 返回插件元数据
- `initialize(context)`: 初始化插件
- `start()`: 启动插件
- `stop()`: 停止插件
- `destroy()`: 销毁插件
- `get_services()`: 返回提供的服务
- `get_status()`: 返回当前状态

### 2. 生命周期
```
INSTALLED -> INITIALIZED -> STARTED -> STOPPED -> (destroy)
```

### 3. 依赖管理
在元数据中指定依赖：

```python
PluginMetadata(
    plugin_id="my-plugin",
    dependencies=["base-plugin:1.0.0", "another-plugin:2.0.0"]
)
```

## API使用

### 获取插件管理器

```python
plugin_manager = app.state.plugin_manager
```

### 启动/停止插件

```python
# 启动插件
plugin_manager.start_plugin("my-plugin")

# 停止插件
plugin_manager.stop_plugin("my-plugin")

# 卸载插件
plugin_manager.unload_plugin("my-plugin")

# 动态加载插件
plugin_manager.load_plugin("/path/to/plugin.py")
```

### 访问插件服务

```python
service_registry = plugin_manager.service_registry

# 获取插件服务
service = service_registry.get_service("my-plugin:myService", MyServiceType)

# 获取主系统服务
sys_service = service_registry.get_system_service(SystemServiceType)
```

## 注意事项

1. 插件加载失败不会影响系统启动
2. 插件启动失败不会影响其他插件
3. 插件卸载后资源会被正确释放
4. 支持插件依赖关系，自动计算启动顺序
5. 使用独立的模块加载，避免命名冲突

## 示例插件

参考 `example_plugin.py` 查看完整的示例插件实现。

