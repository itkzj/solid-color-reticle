# 纯色瞄准

纯色瞄准是《坦克世界》国服准星模组，覆盖街机、狙击和火炮战略模式。V4.4 已在国服 **2.4.1.1** 完成游戏内验收。构建脚本会核对原版准星文件的哈希，请使用匹配的客户端版本。

## 显示内容

- 街机与狙击模式显示装填倒计时、血量、弹药和瞄准点等效装甲。穿透概率为客户端估算值，击穿提示随概率渐变，跳弹显示紫色。普通准星保留游戏内的标记样式设置，狙击倍率显示在顶部。
- 火炮战略模式显示距离、视野高度、炮弹飞行时间、散布点阵和弹震范围。弹道被障碍物截断时，飞行时间按客户端预测的碰撞点计算。
- 中文客户端在装填完成时显示 `Ready`。单发车显示一项装填时间，弹夹车同时显示整夹装填时间和发间装填时间。

## 在 Windows 上构建

准备 Python 3、国服 2.4.1.1 客户端和一个工具目录。按以下相对路径放置构建依赖。

```text
jre/jdk-21.0.13+9-jre/bin/java.exe   Java 21
flex/lib/compc.jar                   Apache Flex SDK 4.16.1
flex/lib/mxmlc.jar
flex/frameworks/
playerglobal32_0.swc                 Flash Player API 编译外部库
extlib/battleCrosshairsApp.swc        与客户端匹配的准星编译外部库
python27/python.exe                  Python 2.7，用于生成游戏加载的字节码
```

在仓库根目录运行下列命令，将前两个参数替换为游戏的 `res/packages` 目录和你的工具目录。请在仓库之外选择一个尚未存在的输出 ZIP 路径。

```powershell
python build_tools/build_local.py "D:/Games/World_of_Tanks_CN/res/packages" "D:/wot-build-tools" "../纯色瞄准V4.4.zip"
```

## 安装与卸载

将生成的 ZIP 解压到游戏根目录，确认 `mods/2.4.1.1/` 下出现 `solid_color_reticle_1.1.0-dev.wotmod`。此版本沿用这个包内文件名，便于覆盖旧构建。若此前安装了 V1.0，请先将 `solid_color_reticle_1.0.wotmod` 移出 `mods` 目录，避免两份模组同时加载。卸载时移除本次安装的 `.wotmod` 文件。

## 许可

本仓库提供源码和本机构建脚本。构建时从玩家本机客户端读取原版 SWF，再加入项目编译的代码。项目源码采用 GPL-3.0-or-later，客户端资源的权利归各自权利人所有。[许可证正文](COPYING)
