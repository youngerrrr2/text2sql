# 数仓 Text2SQL(GL_BALANCES)

对着 Oracle 数仓(BITEST)用自然语言查 **ODS_EBS.GL_BALANCES**(EBS 科目余额表,446 万行)。
中文问题 → 智谱 GLM 生成 Oracle SQL → 只读执行 → 表格 + AI 一句话总结。

## 快速开始

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env   # 填入实际凭证(值不要加引号,密码含 # 没关系)
```

## 用法

### 网页前端(推荐)

双击项目根目录的 `问数.bat` → 浏览器自动打开(Sample: http://localhost:8501),聊天框直接中文提问。

```bash
# 等价命令行方式
.venv/Scripts/python -m streamlit run app.py
```

### 命令行

```bash
# Windows 下务必加 -X utf8(控制台 GBK)
.venv/Scripts/python -X utf8 ask.py "2024年12月 HMPL_PRC 账套各币种的本币月末净余额"
.venv/Scripts/python -X utf8 ask.py "单体8172 2025年2月末的本币资产类净余额" --raw
.venv/Scripts/python -X utf8 ask.py "..." --sql        # 只看生成的 SQL,不执行
```

## 结构

| 文件 | 作用 |
|---|---|
| [ask.py](ask.py) | CLI 入口:问题 → SQL → 执行 → 总结 |
| [db.py](db.py) | Oracle 连接 + 只读执行(拒绝非 SELECT / FOR UPDATE) |
| [llm.py](llm.py) | 智谱 GLM(anthropic 兼容端点)客户端 |
| [schema/gl_balances.md](schema/gl_balances.md) | 喂给 LLM 的表结构 + 业务语义(账套字典、金额口径、科目段) |

## 安全

- 数据库账号本身就是只读(bi_readonly)
- 执行前再校验:只允许 SELECT / WITH,拒绝 FOR UPDATE
- 凭证全部在 .env(gitignore),不进 git

## Roadmap

- [ ] 补全 SEGMENT3–9 的业务含义(找用户确认)后扩充 schema 文档
- [ ] 接入更多表:GL_LEDGERS 全量、凭证表(GL_JE_*)、辅助核算
- [ ] 错误自愈:SQL 报错时把 ORA 错误回传给 LLM 重试
- [ ] 多轮对话 / 查询历史
