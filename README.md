# JSNU 通知雷达 (Notice Radar)

<p align="center">
  <img src="assets/hero.svg" alt="JSNU 通知雷达" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-brightgreen?style=flat-square" alt="No dependencies" />
  <img src="https://img.shields.io/badge/Schedule-Daily%2009%3A00-blue?style=flat-square" alt="Daily" />
  <img src="https://img.shields.io/badge/Delivery-QQ%20Mail-12B7F5?style=flat-square" alt="QQ Mail" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=flat-square" alt="License" />
</p>

<p align="center">
  <b>每天 9 点，把学校三个网站的竞赛 / 考试 / 报名通知整理成一封邮件</b><br>
  关键词筛选 + 自动去重 + 正文摘要，不点开也知道讲了什么。
</p>

<p align="center"><img src="assets/divider.svg" alt="" width="100%" /></p>

---

## 项目背景

教务处、信息门户、学院网站各发各的通知，一天不看就积一堆。真正要留心的其实只有竞赛、考试、报名那几类，但没法只订阅这一类，只能整页翻。

翻漏过一两次之后，就把这件事交给了脚本：让它每天替我看一遍，只把该看的挑出来。

| 痛点 | 场景描述 | 本项目的解法 |
| --- | --- | --- |
| 一天要翻三个站 | 教务处、信息门户、学院，各有各的栏目 | 三站聚合，一次抓完 |
| 有用信息被淹 | 一页里大半是招标、后勤、教职工通知 | 关键词筛选，只留竞赛 / 考试 / 报名 |
| 重复看同一批 | 昨天看过的今天还在最上面 | 按「标题 + 日期」去重，只推新的 |
| 点开才知道讲什么 | 标题太笼统，点进去发现跟自己无关 | 抓正文前 400 字，直接放在邮件里 |
| 不知道脚本死没死 | 没收到邮件，分不清是没通知还是脚本挂了 | 没有新通知也发一封 |

---

## 核心功能

**1. 三站聚合**
- 教务处通知公告、学校信息门户、学院主页，一次抓完；
- 解析标题、日期、链接，相对链接自动补全；
- 解析逻辑单独成函数，站点改版时换一处就行。

**2. 关键词筛选**
- 保留词、排除词都是文件顶部的两个列表，随手可改；
- 命中「竞赛 / 考试 / 报名 / 四六级 / 考研 / 大创 / 挑战杯」等保留；
- 命中「招标 / 后勤 / 教职工 / 值班」等丢弃。

**3. 自动去重**
- 按「标题 + 日期」算哈希，发过的记进 `sent_state.json`；
- 下次只推没见过的；想重来一遍，删掉这个文件即可。

**4. 正文摘要**
- 进详情页抓正文开头 400 字，自动剥离脚本、样式和标签；
- 容器名不对怎么改，见「常见问题」。

**5. 每天准时，且永远有回音**
- 挂在系统计划任务里，每天 9:00 跑一次；
- 有新增推正文，没新增推一封「今日无新增」。

---

## 效果预览

<p align="center">
  <img src="assets/mail.svg" alt="邮件效果" width="100%" />
</p>

一封邮件里三件事：今天新增几条、每条来自哪个栏目、点开之前就能看正文前 400 字。

---

## 工作原理

<p align="center">
  <img src="assets/flow.svg" alt="工作流程" width="100%" />
</p>

| 环节 | 说明 |
| --- | --- |
| 抓列表 | 三个栏目页，解析标题、日期、链接 |
| 关键词筛选 | 保留词命中即留，排除词命中即丢 |
| 去重 | 标题 + 日期算哈希，发过的记本地 |
| 取摘要 | 进正文页，抓前 400 字 |
| 投递 | QQ 邮箱 SMTP，HTML 邮件 |

首次运行只建立基线、不推正文，否则一上线就是几十条历史通知，直接把人淹了。

---

## 快速开始

### 第 0 步：准备邮箱（QQ 邮箱免费）

**QQ 邮箱注册免费，SMTP 服务也不收费**，个人每天发一封的量远远用不完。只有企业邮箱才涉及付费，这里用不上。

- 邮箱注册：<https://mail.qq.com/> 点「注册新账号」，或走 QQ 账号注册页 <https://ssl.zc.qq.com/v3/index-chs.html>
- **开启 SMTP 服务（这一步是关键）**：登录 QQ 邮箱 → 设置 → 账号 → 找到「POP3/IMAP/SMTP 服务」→ 开启 → 按提示验证 → 拿到 16 位授权码
- 图文步骤看官方帮助：<https://service.mail.qq.com/detail/0/75>

> 授权码不是 QQ 密码，别填错。忘了就重新生成一次，旧码立即失效。

想换成 163、Gmail、Outlook 也行，改 `config.json` 里的服务器和端口即可。

### 第 1 步：拿代码

```bash
git clone https://github.com/xm2284/jsnu-notice-radar.git
cd jsnu-notice-radar
```

国内打不开 GitHub 就用镜像：`git clone https://gitee.com/xm2284/jsnu-notice-radar.git`

### 第 2 步：填配置

```bash
cp config.example.json config.json
```

```json
{
  "smtp_server": "smtp.qq.com",
  "smtp_port": 465,
  "sender": "你的QQ号@qq.com",
  "auth_code": "这里填授权码",
  "receiver": "收信邮箱，填自己也行"
}
```

### 第 3 步：先手跑一次

```bash
python daily_notice_radar.py
```

会收到一封「已启动（首次基线建立）」，这是正常的。

### 第 4 步：挂定时任务

Windows，每天 09:00：

```powershell
schtasks /create /tn "通知雷达" /tr "pythonw.exe D:\radar\daily_notice_radar.py" /sc daily /st 09:00
```

Linux / macOS：

```bash
crontab -e
0 9 * * * /usr/bin/python3 /home/you/jsnu-notice-radar/daily_notice_radar.py >> /tmp/radar.log 2>&1
```

---

## 换成自己的学校

改脚本顶部三个地方就够了：

```python
SOURCES = {
    "jwc":    "http://jwc.jsnu.edu.cn/tzgg/",          # 你们学校教务处的通知栏目
    "portal": "http://www.jsnu.edu.cn/xxmhwtzgg/list1.htm",
    "ai":     "http://ai.jsnu.edu.cn/main.htm",
}

INCLUDE_KW = ["竞赛", "比赛", ...]   # 想收什么
EXCLUDE_KW = ["招标", "后勤", ...]   # 不想看什么
```

新站点解析不出来（日志显示「共 0 条」），把那一页 HTML 存下来，说明「这是列表页，要标题、日期、链接」，让 AI 补一个解析函数挂进 `extract_list_items` 即可。

---

## 工程结构

```
jsnu-notice-radar/
├── daily_notice_radar.py       # 主程序，单文件
├── config.example.json         # 配置模板（复制成 config.json 再填）
├── assets/
│   ├── hero.svg
│   ├── flow.svg
│   ├── mail.svg
│   └── divider.svg
├── LICENSE
├── .gitignore                  # 已忽略 config.json / sent_state.json
└── README.md
```

运行时会在同目录生成 `sent_state.json`（已发记录），不要提交它。

---

## 安全与隐私

- 纯本地运行：没有服务器、没有数据库、不上传任何东西；
- 授权码只在本机：`config.json` 已写进 `.gitignore`，不会被提交；
- 只读公开页面：抓的都是学校贴出来给全校看的通知，不登录、不碰任何账号信息；
- 一天一次：对服务器没有任何压力。

---

## 常见问题

**第一次运行没收到正文邮件？**
只发了「已启动」那一封。基线建立后，第二天开始才有正文。

**某天没收到任何邮件？**
先看计划任务有没有真的跑起来。真跑挂了它也发不出信，所以才建议一直开着「无新通知也发信」，收到空邮件就说明它还活着。

**会漏通知吗？**
不会漏新发出来的。但第一次建基线之前就存在的通知会被记为已看，不会再推。想重来就删掉 `sent_state.json`。

**摘要抓到的是导航栏废话？**
正文容器名不对。在 `fetch_summary` 的 class 列表里加上正确的那一个，浏览器里右键「检查」就能看到。

**能不能不发邮件，直接推微信 / 企业微信？**
可以。把 `send_email` 换成对应的 webhook 推送，其余逻辑不动。

---

## 联系作者

- QQ：`2284517861`（小明同学）
- GitHub：[xm2284](https://github.com/xm2284)
- Gitee 镜像：[gitee.com/xm2284/jsnu-notice-radar](https://gitee.com/xm2284/jsnu-notice-radar)

有问题、想加功能、想换成你们学校的站点，直接来找我。

---

## 免责声明

1. 本项目为个人自用的自动化工具，与学校及任何第三方平台无隶属或合作关系；
2. 仅抓取公开发布的通知页面，不涉及账号、个人信息与任何写操作；
3. 请遵守学校网络使用规定，合理设置运行频率；
4. fork 后请勿把自己真实的 `config.json`（含邮箱授权码）提交到公开仓库。

---

## 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
