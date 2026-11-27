# 纯色瞄准

纯色瞄准是《坦克世界》国服准星模组，覆盖街机、狙击和火炮战略模式。V4.7.0 已在 **2.4.2.0** 完成游戏内验收。构建脚本会核对原版准星文件的哈希，请使用匹配的客户端版本。

## V4.7.0 更新记录

- 在 ModMenu 的「纯色瞄准」里加入六个开关。保存后从下一场战斗生效。安装包附带 Aslain ModMenu 和用于打开设置窗口的 OpenWG Gameface。
- 最小落弹环、穿深计算、发光大十字、射界标尺和火炮溅射范围默认开启。开启「使用游戏默认瞄准环」后，实时环和已启用的最小落弹环都采用原版样式，火炮模式也恢复原版散布点阵。未安装 ModMenu 时，按默认配置运行。
- 「发光大十字大小」可在 5%–200% 之间调节，每档 5 个百分点，默认 100%。「发光大十字离中心距离」可在 0%–100% 之间调节，四道光刃以炮口准星为中心同步向外移动。0% 从炮口准星中心出发，默认 5% 对应原位置。100% 时光刃内端距炮口准星为画面短边的三分之一。调节大小时，每道光刃以内端为支点缩放，内端与炮口准星的距离保持固定。两个滑块保存后都从下一场战斗生效。
- 关闭穿深计算后，发光大十字沿用游戏的穿透提示颜色。关闭火炮溅射范围后仍显示飞行时间和视野高度。
- 优化 HUD 状态同步和动画刷新，稳定帧复用已有动画参数，原版环显示对象采用弱引用去重缓存。

## V4.6.1 更新记录

- 适配《坦克世界》 **2.4.2.0**，更新街机和狙击准星使用的原版资源。
- 狙击模式下，射界标尺两侧箭头的间距随瞄准倍率变化。放大时两侧拉开，各自的极限提示仍按实际炮口方向计算。
- 修复卸载后新建准星面板会重新启动桥接的问题。卸载时恢复仍由本模组占用的 7 处钩子，保留其他模组的挂接。
- 将模组元数据和安装文件名统一为 **4.6.1**，补充安装、旧版移除和卸载说明。

## 显示内容

- 街机与狙击模式显示装填倒计时、血量、弹药和瞄准点等效装甲。穿透概率为客户端估算值，击穿提示随概率渐变，跳弹显示紫色。普通准星保留游戏内的标记样式设置，狙击倍率显示在顶部。
- 火炮战略模式显示距离、视野高度、炮弹飞行时间、散布点阵和弹震范围。弹道被障碍物截断时，飞行时间按客户端预测的碰撞点计算。
- 中文客户端在装填完成时显示 `Ready`。单发车显示一项装填时间，弹夹车同时显示整夹装填时间和发间装填时间。

## 在 Windows 上构建

准备 Python 3、国服 2.4.2.0 客户端和一个工具目录。按以下相对路径放置构建依赖。

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
python build_tools/build_local.py "D:/Games/World_of_Tanks_CN/res/packages" "D:/wot-build-tools" "../纯色瞄准V4.7.0beat.zip"
```

每次构建都会从 GitHub 查询并下载 [Aslain ModMenu](https://github.com/Aslain/modmenu/releases/latest) 最新正式版，同时从 GitLab 下载已验证的 [OpenWG Gameface v1.2.2](https://gitlab.com/openwg/wot.gameface/-/releases/v1.2.2)。构建需要联网，下载或校验失败时会停止生成安装包。如果日后 ModMenu 提高 Gameface 的最低版本要求，需更新构建器固定的 Gameface 版本。

## 安装与卸载

1. 退出游戏。先将旧版 `solid_color_reticle_*.wotmod` 移出 `mods`。整包安装时，也将不同版本的 `aslain.modmenu_*.wotmod` 和 `net.openwg.gameface_*.wotmod` 移出，以便每个模组只加载一个版本。
2. 将 ZIP 解压到游戏根目录并保留 `mods` 目录结构。如果整合包已提供兼容的 ModMenu 和 Gameface，可保留它们，只手动复制 `solid_color_reticle_4.7.0.wotmod` 到 `mods/2.4.2.0/`。
3. 进车库后打开 ModMenu，选择「纯色瞄准」。保存设置后，它们会在下一场战斗生效。

卸载纯色瞄准时，移除 `solid_color_reticle_4.7.0.wotmod`。如果没有其他模组使用 ModMenu 或 Gameface，可同时移除各自的 `.wotmod`。

## 许可

本仓库提供源码和本机构建脚本。构建时从玩家本机客户端读取原版 SWF，再加入项目编译的代码。项目源码采用 GPL-3.0-or-later，客户端资源的权利归各自权利人所有。[许可证正文](COPYING)

安装包原样附带 Aslain 发布的 ModMenu 和 OpenWG 发布的 Gameface。Gameface 的 MIT 许可证随 ZIP 一起提供。[Aslain 分发条款](https://github.com/Aslain/modmenu#license) · [OpenWG 许可证](https://gitlab.com/openwg/wot.gameface/-/blob/v1.2.2/LICENSE)
