# V2 实施说明

当前采用逐步替换：保留原始资料、Python数据读取与现有页面，先替换不成立的业务逻辑。前端暂保留原生JavaScript，没有进行React重写；这不影响材料完整读取、来源绑定及LiveKit真实会话，也避免同时更换界面框架妨碍排查业务问题。

## 实际接入与参考

- **已实际运行**：FastAPI 0.162.0、Haystack 3.4.1、LiveKit Agents 1.8.10、livekit-client 2.23.0。本地LiveKit Server 1.13.11由源码构建，仅用于本机预览。依赖锁见requirements-lock.txt。
- **参考结构、自建适配**：OpenMAIC统一材料解析及任务内容分离；Open Notebook来源绑定的上下文。没有整包移植它们的课堂、数据库或评分接口。
- **未接入**：Docling、向量Embedding、RAGFlow、LangGraph。当前没有需要Docling解析的原始文件，中文检索明确只启用了BM25；不能把这些列成已实现。

## 文件与职责

| 文件 | 职责 |
|---|---|
| knowledge.py | 保留71课完整原字段和原标识，不修改reference |
| materials.py | 原文块、稳定定位与版本hash；真正运行Haystack Pipeline |
| tasks.py | 生成与校验课程任务、动态访前重点；引用必须存在 |
| workflow.py | 持久化两场景、完成任务后评价、重试、原话证据与来源校验 |
| asgi.py | FastAPI、同源检查、Cookie隔离、材料/练习/准备接口 |
| voice_runtime.py | LiveKit房间、Silero VAD、原语音服务STT/TTS适配 |
| web/materials.js | 三类图示与可读正文、原文锚点 |
| web/voice.js | 连续会话、自动播放、麦克风与断开生命周期 |
| app.py | 保留旧HTTP测试适配；正式本地入口改为scripts/run_local.py |

## 材料与任务

课程通过 `/api/courses/{id}`完整读取。参考链接独立列出，未随包提供的原文件明确说明。演练保存material对象及revision，反馈指向该快照，不使用后来变化的课程重建旧评价。

检索接口 `/api/materials/search`只允许服务端生成课程范围过滤条件；额外传入filter不会覆盖范围。中文字符与相邻二元词、英文缩写采用一致分词；仅返回正分命中，不将无关补位行作为证据。当前资料均用于本地课程预览，检索不是正式医学证据审定。

任务生成后，程序验证观察项数量、ID唯一性以及每条材料引用。医生角色的继续/结束决策与段后评价分别调用，期间不向用户显示评价。达到任务、用户主动结束或安全时限时完成。评价的原话从给定发言ID还原；材料ID必须在本次快照内，若观察项指定依据，也必须在该观察项的范围内。坏JSON或不合法引用明确失败，不给默认分数。

生成和引用校验只能保证格式与范围，不能自动证明每一条评价的语义正确。真实测试也发现过角色写反和额外标准，已加强提示与测试；仍需要内容复核及真实用户试用。

## 第二模块边界

不改第二模块。自填context可选择传入weaknesses，每条含topic_id、behavior、evidence、observed_at。本模块只保留与当前课程ID或疾病ID相关、且有原话和时间的记录，不创建长期能力画像。日报目前未在线接入；背景仍来自用户填写。

## 语音运行

LiveKit通过WebRTC连续收音，Silero检测说话边界，适配器把音频送到现有Qwen/Whisper网关，最终转写自动进入与文字相同的Engine.answer；不把中间结果提交为回答。TTS经同一网关合成后由会话自动播放。用户可开始、暂停或结束，无逐句提交按钮。

当前是“连续传输＋按段批处理识别/合成”，不是供应商原生流式ASR/TTS。网关限流、转写延迟和最长语音片段约束仍存在。合成音频测试只能证明音频路径与业务路径相连，不能证明真人交流体验已经合格。

本机启动脚本在runtime/livekit-local.json生成凭证，密钥文件权限0600；不放进源码。凭证只在服务端用于签发限房间、短期令牌。浏览器仅拿房间令牌。生产部署、员工认证与外网网络配置不在本次本机实现范围。

### 其他机器准备

安装Python3.11依赖：

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

已有LiveKit服务时，设置LIVEKIT_URL、LIVEKIT_API_KEY、LIVEKIT_API_SECRET，再运行scripts/run_local.py。自行部署本机服务可从官方LiveKit Server源码按固定版本构建，并放到runtime/bin/livekit-server；官方仓库为 https://github.com/livekit/livekit 。构建时需遵循其go.mod中的Go版本和replace配置，不能直接用go install替代主模块构建。

vendored浏览器SDK附Apache-2.0许可证与版本hash。原始reference未改写；其他框架依赖许可证随安装包保留。
