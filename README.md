# Mewgenics Cat Workbench · 喵喵的结合自定义猫咪工作台

**Windows 公开测试版 / Public beta — v0.1.0-beta.2**

配置 1～4 只基础属性全 7 的猫咪，挑选技能、部位变异、装备和套装，并把配置关联到实际出征记录。出征人数可以少于配置人数。

This is an unofficial Chinese-language desktop companion for Mewgenics. It edits an offline local save, generates its art/catalogs from your own installation, and records expeditions locally. It is not affiliated with the game or Save Editor authors.

## 能做什么

- 四个主动技能、两个被动技能分别选择职业（含无职业），再从对应职业池挑选，每项均可留空。职业与技能不受存档解锁限制，14 个职业全部可选，未解锁的会标出来。
- 常驻助手「F3 助手」：工作台顶部点按钮启动，托盘常驻，每次游戏保存后自动把 NPC 捐献进度补到目标值（要交猫的委托算已完成，不消耗猫）；按 F3 可立即补一次，再点按钮关掉。不随系统开机启动。
- 顶部「NPC 交猫直接完成」按钮把各 NPC 的捐献进度补到目标值：豆博士这类要交猫的委托会直接算完成，不用真的把猫交出去；只改 NPC 进度，写入前自动备份。
- 顶部「解锁全部职业与技能」按钮把全部职业、主动和被动技能写入存档解锁表；只改解锁表，不动猫咪、装备和进度，写入前自动备份。
- 每个技能位都有「强化」勾选框：勾选后写入强化版（主动用游戏内的 +2 变体，被动写入 2 级），描述里同时显示原效果与强化效果。技能选择面板顶部也有同一个勾选框，带「＋」的条目才有强化版。
- 两个疾病栏并入技能页，在技能列表下方按图片、名称和效果挑选，包括游戏中的疾病与障碍，也可留空。疾病可能按游戏规则影响属性、装备和行为。
- 工作台横条显示职业、方形技能图标和描述；技能选择使用图片网格，装备选择使用图文列表。
- 主动技能描述包含蓝耗、单段基础伤害或治疗量，读取技能模板和变体继承值。条件数值显示公式，最终伤害受猫咪属性、装备、状态及战斗规则影响。
- 复用本机原版编辑器的部位图片选择和整猫预览，并补充变异效果。特殊效果优先，其次正向数值，最后负向数值。
- 头部、面部、颈部、武器、饰品分别选装备；套装选项直接带效果文字。
- 独立的确认清理按钮：清理家中猫咪和已识别的非任务装备。保留任务物品、消耗品、无法识别的物品与猫咪历史。猫身上的任务物品需先卸到仓库。
- 每次写入前自动备份；草稿、可复用配置、出征方案和日记分开保存。
- 日记只记录实际派出的猫，关联它们的自定义配置，并保留出征时和结束时的状态。

## 依赖与安装

这是需要初始化的测试版，**不是免依赖的单文件 EXE**。

1. Windows 10/11 x64，已安装 Mewgenics。当前验证基于游戏 **1.1.21239**。
2. 安装官方 [Python 3.13（Windows）](https://www.python.org/downloads/windows/)，包含 Python Launcher 与 tkinter。此版需要 3.13，以匹配下列编辑器的 Python 字节码。
3. 自行下载并完整解压 [Wawax007 的 Mewgenics Save Editor 4.2.1](https://www.nexusmods.com/mewgenics/mods/20?tab=files)。保留它的 `.exe` 和 `_internal` 文件夹。
4. 如果使用出征日记窗口，安装 [.NET 8 Desktop Runtime（Windows x64）](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)。工作台本身不依赖 .NET。
5. 从本项目 Releases 下载 Windows 测试包，完整解压到可写目录，双击 `Start.cmd`。
6. 第一次运行会在本目录创建虚拟环境、从 PyPI 安装 `requirements.txt` 中的依赖，并让你选择游戏目录、编辑器和要编辑的 `.sav`。
7. 初始化会在你自己的电脑上提取图片、说明和名字池，通常需要十几秒到一分钟。随后打开工作台。

日记窗口的预编译文件放在 Release ZIP 中。直接克隆源码时，需用 .NET 8 SDK 执行：

```powershell
dotnet publish journal/RunJournal.csproj -c Release -o journal
```

更换游戏、编辑器或存档后，可重新配置：

```powershell
.venv\Scripts\python.exe setup_workbench.py --reconfigure
```

默认从游戏原版资源建立目录。使用覆盖技能、物品或套装的模组时，可以指定一个或多个覆盖目录，后者优先：

```powershell
.venv\Scripts\python.exe setup_workbench.py --game "游戏目录" --editor "编辑器目录" --save "存档路径.sav" --overlay "模组数据目录"
```

## 使用流程

1. 在游戏中回家、保存，**退出游戏并关闭存档编辑器**。
2. 打开工作台。左侧勾选本次启用的 1～4 只猫，逐只配置。名字留空会从官方中文名字池抽取。
3. 如需清理，先使用独立清理按钮并确认；生成不会自动清理旧猫。
4. 点击生成。程序备份原存档，在副本上修改、校验，最后替换选中的存档。
5. 生成后打开出征日记，保持日记开启，再进入游戏出征。
6. 游戏自动保存后，日记记录实际队伍及状态。无法可靠区分通关与撤退时显示“待确认”，可以手动标注。

“全 7”指七项**基础属性**；装备和变异仍会按游戏规则产生额外加成。普通移动与普通攻击始终保留；自选被动为 1 级。

升级时完整覆盖程序文件并运行 `Start.cmd`，程序会从本机资源补充疾病目录。旧草稿和方案保留原有两个主动及第一个被动，新增栏位默认留空。

## 限制与验证范围

- 不支持游戏运行时写入；没有游戏注入或内存修改。
- 不会自动设置无限金币、无限食物、家具属性或战斗倍速。鼠标倍速模组不在此公开包中。
- 出征记录需要监控程序开启。中途开启会标注为中途记录；过去未留下数据的完整战报无法补齐。
- 明确读取到全部队员死亡时才标注存档判定团灭；普通回家、回档和间隔缺失会保守标注，不能保证自动区分全部结局。
- 游戏/编辑器更新、非常规存档、其他模组及任务系统可能影响兼容性。先在复制的存档上试用，再用于正式进度。
- 已在副本上验证 1～4 猫、空技能、独立职业技能、变异、五个装备槽、任务库存条目保留、备份、出征关联及 SL 分组。公开版初始化使用干净环境另行验证。未对所有装备/变异组合逐一实战验证。
- 本工具依赖原版编辑器的内部接口，更新它可能需要重新适配。原版编辑器不由本项目维护。

## 本地数据与隐私

正常功能不上传存档、模板、图片、历史或个人路径。首次安装会从 PyPI 下载软件依赖。

`settings.json`、`catalog.json`、`workbench.json`、`images/`、`当前草稿.json`、`方案模板/`、`出征方案/`、`备份/` 与 `journal/记录/` 都是本机生成的数据，不应上传到公开仓库。目录已列入 `.gitignore`。初始化使用你自己存档里的猫作为本机模板，**不要分享生成的 catalog.json**。

卸载前先将需要的备份和记录复制到其他地方，再删除解压目录。它不会修改游戏安装目录。

## Credits / 许可

- 本项目新增的工作台、初始化、保存流程和日记代码：MIT，见 [LICENSE](LICENSE)。
- SWF 图标读取与 GON 解析参考 [MewTree](https://github.com/TotSamiyMorzh/mewgenics-mewtree) 的 MIT 代码；原许可保存在 [vendor/MewTree-LICENSE.txt](vendor/MewTree-LICENSE.txt)。
- 部位选择、整猫预览及存档解析调用使用者自行安装的 **Wawax007 / Mewgenics Save Editor 4.2.1**。本项目没有打包它的程序、Python 字节码或素材，也不声称拥有其版权。
- 游戏图片、文字、名称与数据属于 Mewgenics 及相应权利人；由用户从本机安装提取，不随源码或 Release 分发。
- 本工具在与 Codex 的协作中开发。Please report bugs with reproduction steps and the game/editor versions; do not post your save or generated local data publicly.
