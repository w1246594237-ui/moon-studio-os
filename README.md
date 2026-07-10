# Moon Studio OS

一个使用 Python、Streamlit 和 SQLite 构建的本地个人工作室运营管理系统。

## 运行

1. 安装 Python 3.10 或更高版本。
2. 在项目目录安装依赖：

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. 启动：

   ```powershell
   python -m streamlit run app.py
   ```

   Windows 也可以直接双击 `启动 Moon Studio OS.bat`。

数据会永久保存在项目目录的 `moon_studio.db`。建议定期复制这个文件做备份。

## V1 页面

- 首页 Dashboard
- 任务管理
- 项目管理
- 每日时间规划
- Bree 内容管理
- Moon 内容管理
- 想法池
- 周复盘

## V1.1 优化

- 可折叠的年度/月度系统活跃看板
- 今日 Emoji 状态、自我评价和一句话记录
- 侧边栏每日一语（本地按日期轮换）
- 项目管理支持新建项目
- 新建任务时可直接创建新的项目分类
- 进行中任务支持一键勾选完成

首次启动会自动创建四个默认项目。每天首次打开时间规划或首页时，也会自动创建上午、作品集深度工作和晚上的默认时间块。
